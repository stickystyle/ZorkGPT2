# Grounding Validator for Memories and Objectives

## Problem

The LLMs that generate memories and objectives can hallucinate claims not supported by actual gameplay. Examples:

- **Memory**: "Screwdriver is found in the forest" when the agent just dropped it there — it's not native to that location.
- **Memory**: Inventing mechanics that didn't happen, confusing carried items with room items.
- **Objective**: Referencing items, NPCs, or locations never seen in game text. Generating objectives based on general Zork knowledge rather than observed gameplay.

These ungrounded claims pollute the agent's learning systems and compound over episodes since memories and objectives persist.

## Solution

Add a grounding validation step after memory and objective generation. Two new Burr graph nodes — `validate_memory` and `validate_objectives` — act as binary gates. Each calls a shared grounding prompt that checks whether the candidate is supported by recent game output. Ungrounded candidates are dropped.

## Design

### Shared Grounding Prompt

**File**: `prompts/grounding_validator.md`

A single prompt with a `{grounding_rules}` placeholder. The core prompt teaches the LLM:

- You will receive recent action/response pairs (the ground truth of what happened).
- You will receive one or more candidate claims (memories or objectives).
- For each candidate, determine if the claim is **directly supported** by the game output in the recent turns.
- A claim is grounded if every factual assertion in it traces to something explicitly present in the game text.
- A claim is ungrounded if it attributes items to locations where they weren't found, references entities not seen in game output, invents mechanics not demonstrated, or infers solutions from nothing.

The caller injects type-specific rules via `{grounding_rules}`:

**Memory rules:**
- Items listed in inventory are CARRIED, not native to the current location. Only record an item as "found here" if the game response describes it present in the room.
- Mechanics described in the memory must match what the game response actually showed.
- Score changes must correspond to the action that was taken, not an invented cause.

**Objective rules:**
- Every referenced item, NPC, or location must have appeared in game text.
- Parser prompts ("What do you want to X with?") don't reveal which tool — don't name specific tools not yet seen.
- Objectives must describe actions the player can take based on observed state, not inferred puzzle solutions.

### Response Model

In `zorkburr/llm/models.py`:

```python
class GroundingJudgment(BaseModel):
    item: str        # title of memory or text of objective
    grounded: bool   # accept or reject
    reason: str      # explanation (logged, not shown to agent)

class GroundingValidationResponse(BaseModel):
    judgments: list[GroundingJudgment]
```

Works for a single memory (list of one) or a batch of objectives. Always returns one judgment per candidate.

### Burr Actions

**File**: `zorkburr/actions/grounding.py`

Two actions sharing a common `_call_grounding_validator()` function:

#### `validate_memory`

- **Reads**: `PENDING_MEMORY`, `ACTION_HISTORY`, `LOCATION_NAME`, `LOCATION_ID`, `INVENTORY`, `MEMORIES_BY_LOCATION`, `MEMORY_STATS`, `LOCATION_SUMMARIES`, `PRE_LOCATION_NAME`, `EPISODE_ID`, `TURN_COUNT`
- **Writes**: `MEMORIES_BY_LOCATION`, `MEMORY_STATS`, `LOCATION_SUMMARIES`, `PENDING_MEMORY`
- **Behavior**:
  - If `PENDING_MEMORY` is None/empty, pass through (no LLM call).
  - Otherwise, call the grounding validator with the memory addendum.
  - If grounded: commit the memory to `MEMORIES_BY_LOCATION`, generate location summary, update stats — the same commit logic currently in `record_memory`.
  - If rejected: log the rejection, increment a `grounding_rejected` counter in `MEMORY_STATS`, clear `PENDING_MEMORY`.

#### `validate_objectives`

- **Reads**: `PENDING_OBJECTIVES`, `PENDING_COMPLETED_OBJECTIVES`, `ACTION_HISTORY`, `LOCATION_NAME`, `LOCATION_ID`, `INVENTORY`, `DISCOVERED_OBJECTIVES`, `COMPLETED_OBJECTIVES`, `TURN_COUNT`
- **Writes**: `DISCOVERED_OBJECTIVES`, `COMPLETED_OBJECTIVES`, `PENDING_OBJECTIVES`, `PENDING_COMPLETED_OBJECTIVES`
- **Behavior**:
  - If `PENDING_OBJECTIVES` is None/empty, commit any completed objectives and pass through (no LLM call for validation).
  - Otherwise, call the grounding validator with the objective addendum.
  - Filter to only grounded objectives. Commit those to `DISCOVERED_OBJECTIVES`.
  - Completed objectives (from the discovery response) are always committed — completion is a removal, not an assertion about the world.
  - Clear `PENDING_OBJECTIVES`.

#### `_call_grounding_validator()`

Shared function used by both actions:

- **Inputs**: `client`, `config`, `candidates` (list of dicts with `item` key), `addendum` (string), `action_history` (last 5), `location_name`, `location_id`, `inventory`
- **Output**: `GroundingValidationResponse`
- **Model**: `config.critic_model`
- **Temperature**: 0.0 (deterministic judgment)
- **Max tokens**: 512

### State Changes

Two new transient state keys on the `S` class:

- `S.PENDING_MEMORY = "pending_memory"` — dict or None. Set by `record_memory` when it synthesizes a memory (instead of committing directly). Contains the full Memory dict plus `supersedes_titles` (list of titles to mark as SUPERSEDED on commit) and `loc_key` (the location ID string). Cleared by `validate_memory`.
- `S.PENDING_OBJECTIVES = "pending_objectives"` — list of dicts or None. Set by `update_objectives` for new objectives. Cleared by `validate_objectives`.
- `S.PENDING_COMPLETED_OBJECTIVES = "pending_completed_objectives"` — list of strings or None. Completions identified by `update_objectives`. Passed through without validation.

Initial values: all None in `create_initial_state()`.

### Changes to Existing Actions

#### `record_memory` (memory.py)

When `should_remember` is true and the memory passes dedup:
- Instead of committing to `MEMORIES_BY_LOCATION` directly, write the candidate to `PENDING_MEMORY` (the full Memory dict plus any supersession info).
- The location summary generation and stats update move to `validate_memory`.
- The dedup guard (exact title match) stays in `record_memory` — no point validating a duplicate.

#### `update_objectives` (objectives.py)

- Instead of committing new objectives directly to `DISCOVERED_OBJECTIVES`, write them to `PENDING_OBJECTIVES`.
- Completed objectives go to `PENDING_COMPLETED_OBJECTIVES`.
- The location ID resolution stays in `update_objectives` (it's pre-processing, not validation).

### Graph Changes

Current flow:
```
record_memory -> check_objective_completion -> [update_objectives] -> assemble_context
```

New flow:
```
record_memory -> validate_memory -> check_objective_completion -> [update_objectives -> validate_objectives] -> assemble_context
```

Transition details:

```python
("record_memory", "validate_memory"),
("validate_memory", "check_objective_completion"),
("check_objective_completion", "update_objectives",
 expr(f"turn_count > 0 and turn_count % {obj_interval} == 0 and game_over == False")),
("check_objective_completion", "turn_complete", when(**{S.GAME_OVER: True})),
("check_objective_completion", "assemble_context", default),
("update_objectives", "validate_objectives"),
("validate_objectives", "assemble_context", default),
```

Both validate nodes are always traversed but short-circuit (no LLM call) when there's nothing pending.

### Config

In `GameConfig` (`pyproject.toml`):

```toml
[tool.zorkburr]
enable_grounding_validator = true
```

```python
enable_grounding_validator: bool = True
```

When disabled, both validate nodes pass through and commit unconditionally (same as current behavior). Mirrors the `enable_critic` pattern.

### LLM Call Budget

- `validate_memory`: 0-1 calls per turn (only when memory synthesized — score change, location change, or death).
- `validate_objectives`: 0-1 calls per N turns (only when `update_objectives` fires and produces new objectives).
- Both use `critic_model`.
- Typical episode: ~5-10 memory validations, ~3-5 objective validations out of ~100 turns.

### Logging

Both validators log at INFO level:
- Accepted: `"Grounding accepted memory: '{title}'"`
- Rejected: `"Grounding rejected memory: '{title}' — {reason}"`
- Same pattern for objectives.

Rejection reasons are stored in stats for orchestrator visibility but not exposed to the agent.

### Testing

- Unit tests for `_call_grounding_validator()` with mocked LLM responses.
- Unit tests for `validate_memory` and `validate_objectives` actions verifying:
  - Pass-through when no pending candidate.
  - Commit on acceptance.
  - Drop on rejection (state unchanged except stats).
  - Stats counters increment correctly.
- Integration test: full graph traversal with a memory that should be rejected (carried item attributed to room).
