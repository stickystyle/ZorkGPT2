# Prompt Validation: Pre-Deployment Testing Against Recorded Game Data

**Date:** 2026-04-04
**Status:** Approved design

## Problem

The orchestrator's improvement subagent makes prompt changes to fix diagnosed problems, then waits for the next full episode (often an hour) to see if the change helped. If the agent doesn't revisit the specific scenario during that episode, validation is even further delayed. This feedback loop is too slow and too noisy — a full episode introduces many variables beyond the prompt change.

## Solution

Require every prompt change to be validated against real recorded game data before committing. Extract fixture data from the Burr tracker at diagnosis time, replay the problematic turns through the updated prompt, and gate the commit on validation passing.

## Design Decisions

- **Fixture source:** Burr tracker live extraction (option 1). Richest data — captures exactly what the LLM saw. Extracted at diagnosis time while the tracker has the episode data.
- **Scope:** All prompt changes require validation. Any file in `prompts/` triggers the requirement. Config-only changes (`pyproject.toml`) also run validation since threshold/temperature changes affect LLM behavior.
- **Validation criteria:** Hybrid — structural checks (deterministic, fast) plus LLM-as-judge (flexible, assesses quality). Both must pass.
- **Fixture count:** 5-10 turns total. 3-5 problematic turns (the specific cases the change targets) plus 2-3 healthy turns (regression anchors where the system was working correctly).
- **Failure policy:** Hard block. If validation fails, the subagent must iterate on its change or revert. No committing with failures.

## Components

### 1. Fixture Format

Fixtures live in `tests/fixtures/` as JSON files named `{episode_id}_t{turn}_{action_type}.json`.

```json
{
  "meta": {
    "app_id": "app_abc123",
    "episode_id": "ep42",
    "turn": 37,
    "extracted_at": "2026-04-04T14:30:00Z",
    "role": "problem",
    "problem_description": "Agent ignored location memories — proposed 'examine mailbox' despite memory saying mailbox already opened"
  },
  "action_type": "generate_action",
  "state": {
    "formatted_context": "...",
    "rejection_count": 0,
    "critic_justification": "",
    "knowledge_base": "...",
    "turn_count": 37
  },
  "original_output": {
    "proposed_action": "examine mailbox",
    "agent_reasoning": "Let me check what's in the mailbox...",
    "next_steps": "...",
    "new_objective": ""
  }
}
```

The `state` keys captured depend on the `action_type`, matching each action's `reads` list:

| action_type | State keys captured |
|---|---|
| `generate_action` | `formatted_context`, `rejection_count`, `critic_justification`, `knowledge_base`, `turn_count` |
| `evaluate_action` | `proposed_action`, `game_response`, `action_history`, `exits`, `inventory`, `location_name`, `rejection_count`, `in_combat` |
| `record_memory` | `pre_location_id`, `pre_location_name`, `pre_score`, `pre_inventory`, `location_id`, `score`, `inventory`, `game_over`, `game_over_reason`, `game_response`, `action_to_take`, `agent_reasoning`, `action_history`, `memories_by_location`, `episode_id`, `turn_count`, `memory_stats`, `location_summaries` |
| `update_knowledge` | `action_history`, `knowledge_base`, `memories_by_location`, `discovered_objectives`, `completed_objectives`, `score`, `max_score` |
| `extract_info` | `game_response`, `location_name`, `action_to_take` |
| `update_objectives` | `action_history`, `memories_by_location`, `knowledge_base`, `discovered_objectives`, `completed_objectives`, `score`, `location_name` |
| `check_objective_completion` | `action_to_take`, `game_response`, `score`, `pre_score`, `discovered_objectives`, `completed_objectives` |

The `original_output` captures the writes from the same action step, so the judge can compare old vs new.

### 2. Extraction Script — `scripts/extract_fixtures.py`

**Usage:**
```bash
# Extract problem turns
python3 scripts/extract_fixtures.py {app_id} --turns 37,42,45 \
  --action generate_action --role problem \
  --description "Agent ignored location memories at visited locations"

# Extract healthy turns
python3 scripts/extract_fixtures.py {app_id} --turns 12,18 \
  --action generate_action --role healthy
```

**Behavior:**
1. Hits the Burr tracker API (`http://localhost:7241`) to fetch steps for the given `app_id`
2. For each specified turn, finds the step matching `action_type` using the same turn-finding logic as `scripts/burr_turn.py`
3. Extracts the state keys for that action type plus the original output (writes)
4. Resolves the episode_id from the state's `episode_id` field
5. Writes fixture files to `tests/fixtures/{episode_id}_t{turn}_{action_type}.json`
6. Prints the paths of created fixtures to stdout

Uses the existing `_args.py` helpers (`fetch_steps`, `get_state`, `get_action`) for Burr API access.

### 3. Validation Script — `scripts/validate_prompt.py`

**Usage:**
```bash
python3 scripts/validate_prompt.py tests/fixtures/ep42_*.json
```

**Phase 1 — Replay:** For each fixture:
1. Deserialize `state` into a Burr `State` object
2. Create a real LLM client via `create_llm_client(config)` using current config (which reflects any changes the subagent made)
3. Call the actual action's `.run()` method (e.g., `generate_action.run(state, client=client, config=config)`)
4. Capture the new output
5. Log progress: `Replaying ep42_t37 generate_action... done (2.3s)`

**Phase 2 — Judge:** For each fixture, two checks:

*Structural check* (deterministic):
- `generate_action`: output non-empty and not "look" (fallback). If role=problem, action differs from original.
- `evaluate_action`: score is a valid float. If role=problem, score moved in expected direction.
- `record_memory`: response has required fields (category, title, text).
- `update_knowledge`: knowledge base output is non-empty.
- `extract_info`: exits list is present.
- All types: no exception/fallback occurred during replay.

*Quality judgment* (by the improvement subagent — Claude):
The script prints structured comparison output (original vs new) for each fixture. The improvement subagent (which is a Claude Opus instance) reads this output and judges whether the change genuinely addresses the diagnosed problem. This is better than having the local model judge its own output quality.

**Output format:**
```
FIXTURE ep42_t37_generate_action.json [PROBLEM]
  Replaying ep42_t37 generate_action... done (2.3s)
  Structural: PASS (Action: 'go north')
  Comparison:
    Role: PROBLEM
    Problem: Agent ignored location memories
    Original action: examine mailbox
    New action:      go north
    Original reasoning: check the mailbox
    New reasoning:      I recall from prior visits that the mailbox has been opened...

FIXTURE ep42_t12_generate_action.json [HEALTHY]
  Replaying ep42_t12 generate_action... done (1.8s)
  Structural: PASS (Action: 'open window')
  Comparison:
    Role: HEALTHY
    Original action: open window
    New action:      open window
    ...

STRUCTURAL RESULTS: 5/5 passed — all structural checks passed
```

**Exit code:** 0 = all structural checks pass, 1 = any structural failure. The subagent evaluates quality from the comparison output.

**Special case — critic:** `evaluate_action` also uses Jericho for object-tree validation. The validation script passes a mock Jericho that auto-passes object-tree checks (returns `(True, "mock auto-pass")` from `validate_against_object_tree`). This isolates the LLM critic evaluation, which is the part affected by prompt changes. Object-tree validation is deterministic Python code — not affected by prompt edits.

### 4. Orchestrator Integration

Three changes to `.claude/commands/zork-orchestrator.md`:

**A. New Phase 3 step 2.5 — Extract Fixtures**

After identifying the problem and specific turns, before dispatching the subagent:

```bash
# Problem turns (3-5 from the diagnosis)
python3 scripts/extract_fixtures.py {app_id} --turns {problem_turns} \
  --action {action_type} --role problem \
  --description "{problem description}"

# Healthy turns (2-3 with good critic scores, no rejections)
python3 scripts/extract_fixtures.py {app_id} --turns {healthy_turns} \
  --action {action_type} --role healthy
```

The orchestrator selects the action type based on which prompt needs changing:

| Prompt file | Action to extract |
|---|---|
| `agent.md` | `generate_action` |
| `critic.md` | `evaluate_action` |
| `memory_synthesis.md` | `record_memory` |
| `knowledge.md` | `update_knowledge` |
| `extractor.md` | `extract_info` |
| `objective_discovery.md` | `update_objectives` |
| `objective_completion.md` | `check_objective_completion` |

Healthy turns are selected by scanning checkpoint data for turns with critic score > 0.6 and zero rejections.

**B. Updated subagent brief — append validation requirement**

```
VALIDATION REQUIREMENT (HARD BLOCK):
After making your change, you MUST validate it against recorded game data
before committing.

Fixture files have been extracted to tests/fixtures/. Run:

  python3 scripts/validate_prompt.py tests/fixtures/{episode}_*.json

This replays the problematic turns (and healthy regression anchors) through
your updated prompt with a live LLM call, then judges whether the output
improved.

- ALL fixtures must PASS for you to commit.
- If validation fails: iterate on your change and re-run. You have up to
  3 attempts. If all 3 fail, revert your change and report back with the
  full validation output so the orchestrator can reassess.
- Do NOT skip validation. Do NOT commit with failures.
- Include the validation output summary in your journal IMPROVEMENT entry
  as a new field: **Validation:** PASSED (5/5) or FAILED (3/5) — <details>
```

**C. Updated Phase 3 step 5 review checklist — new row**

| Check | What to look for |
|---|---|
| Validation passed | `validate_prompt.py` exited 0 and journal entry shows **Validation: PASSED**. If missing or failed → revert. |

### 5. Fixture Cleanup

At the start of each Phase 3, the orchestrator deletes fixture files from episodes 5+ ago:

```bash
# Remove old fixtures (keep last 5 episodes)
ls tests/fixtures/*.json 2>/dev/null | head -n -35 | xargs rm -f 2>/dev/null
```

This prevents unbounded accumulation. Fixtures are most valuable at the moment of validation — once the change is committed, they've served their purpose.

## What This Does NOT Do

- **Deterministic regression suite.** LLM outputs are non-deterministic. Fixtures capture inputs and problem descriptions, not expected exact outputs. Re-running old fixtures may produce different results. This is a pre-deployment validation gate, not a CI test.
- **Replace episode-level measurement.** The orchestrator still runs full episodes and measures score trends. Fixture validation catches "change doesn't fix the problem" and "change breaks something else" early, but episode-level metrics remain the ground truth for system performance.
- **Test Python code changes.** This validates prompt and config changes. Python pipeline bugs are caught by the existing pytest suite.

## Files to Create/Modify

| File | Action |
|---|---|
| `scripts/extract_fixtures.py` | Create — fixture extraction from Burr tracker |
| `scripts/validate_prompt.py` | Create — replay + structural check + LLM judge |
| `.claude/commands/zork-orchestrator.md` | Modify — add fixture extraction step, validation requirement in subagent brief, review checklist row |
| `tests/fixtures/.gitkeep` | Create — empty directory marker |
