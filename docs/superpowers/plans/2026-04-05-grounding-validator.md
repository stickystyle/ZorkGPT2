# Grounding Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add binary grounding validation gates after memory and objective generation to reject hallucinated claims not supported by recent game output.

**Architecture:** Two new Burr graph nodes (`validate_memory`, `validate_objectives`) call a shared grounding prompt with type-specific addenda. Existing `record_memory` and `update_objectives` become "propose" steps that write to pending state keys; the new validate nodes become "commit" steps. A kill switch (`enable_grounding_validator`) allows bypassing validation entirely.

**Tech Stack:** Python, Burr, Instructor/Pydantic, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `zorkburr/state.py` | Modify | Add 3 new state keys (`PENDING_MEMORY`, `PENDING_OBJECTIVES`, `PENDING_COMPLETED_OBJECTIVES`) |
| `zorkburr/config.py` | Modify | Add `enable_grounding_validator` config field |
| `pyproject.toml` | Modify | Add `enable_grounding_validator = true` default |
| `zorkburr/llm/models.py` | Modify | Add `GroundingJudgment` and `GroundingValidationResponse` models |
| `prompts/grounding_validator.md` | Create | Shared grounding validation prompt with `{grounding_rules}` placeholder |
| `zorkburr/actions/grounding.py` | Create | `validate_memory`, `validate_objectives` actions and shared `_call_grounding_validator()` |
| `zorkburr/actions/memory.py` | Modify | Change `record_memory` to write to `PENDING_MEMORY` instead of committing directly |
| `zorkburr/actions/objectives.py` | Modify | Change `update_objectives` to write to `PENDING_OBJECTIVES`/`PENDING_COMPLETED_OBJECTIVES` |
| `zorkburr/app.py` | Modify | Wire new nodes into the Burr graph |
| `tests/test_grounding.py` | Create | Unit tests for validation actions |
| `tests/test_app.py` | Modify | Update integration test mock to handle new response model |

---

### Task 1: State Keys and Config

**Files:**
- Modify: `zorkburr/state.py:6-49` (S class) and `zorkburr/state.py:50-93` (create_initial_state)
- Modify: `zorkburr/config.py:82-85` (after critic config)
- Modify: `pyproject.toml` (under `[tool.zorkburr]`)

- [ ] **Step 1: Add state key constants to `S` class**

In `zorkburr/state.py`, add these three lines after `LOCATION_SUMMARIES = "location_summaries"` (line 48):

```python
    PENDING_MEMORY = "pending_memory"
    PENDING_OBJECTIVES = "pending_objectives"
    PENDING_COMPLETED_OBJECTIVES = "pending_completed_objectives"
```

- [ ] **Step 2: Add initial values in `create_initial_state()`**

In the `State({...})` dict in `create_initial_state()`, add after the `S.LOCATION_SUMMARIES: {}` line:

```python
        S.PENDING_MEMORY: None,
        S.PENDING_OBJECTIVES: None,
        S.PENDING_COMPLETED_OBJECTIVES: None,
```

- [ ] **Step 3: Add config field**

In `zorkburr/config.py`, add after the `max_rejections_per_turn` line (line 85):

```python
    # Grounding validator
    enable_grounding_validator: bool = True
```

- [ ] **Step 4: Add pyproject.toml default**

In `pyproject.toml`, under `[tool.zorkburr]`, add:

```toml
enable_grounding_validator = true
```

- [ ] **Step 5: Run existing tests to confirm nothing breaks**

Run: `uv run pytest tests/test_state.py tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add zorkburr/state.py zorkburr/config.py pyproject.toml
git commit -m "feat(grounding): add pending state keys and config flag"
```

---

### Task 2: Pydantic Response Models

**Files:**
- Modify: `zorkburr/llm/models.py:56-66` (after ObjectiveCompletionResponse)

- [ ] **Step 1: Write the failing test**

Create `tests/test_grounding.py`:

```python
"""Tests for grounding validation."""
from zorkburr.llm.models import GroundingJudgment, GroundingValidationResponse


def test_grounding_judgment_accepts():
    j = GroundingJudgment(item="Open the trapdoor", grounded=True, reason="Trapdoor mentioned in game text")
    assert j.grounded is True


def test_grounding_judgment_rejects():
    j = GroundingJudgment(item="Find the screwdriver in forest", grounded=False, reason="Screwdriver was in inventory, not found here")
    assert j.grounded is False


def test_grounding_validation_response_filters():
    resp = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Open trapdoor", grounded=True, reason="ok"),
        GroundingJudgment(item="Use screwdriver", grounded=False, reason="never seen"),
        GroundingJudgment(item="Explore cellar", grounded=True, reason="ok"),
    ])
    accepted = [j for j in resp.judgments if j.grounded]
    assert len(accepted) == 2
    assert accepted[0].item == "Open trapdoor"
    assert accepted[1].item == "Explore cellar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_grounding.py -v`
Expected: FAIL with `ImportError: cannot import name 'GroundingJudgment'`

- [ ] **Step 3: Add models to `models.py`**

In `zorkburr/llm/models.py`, add after the `ObjectiveCompletionResponse` class (after line 66):

```python
class GroundingJudgment(BaseModel):
    item: str = Field(description="Title of memory or text of objective being validated")
    grounded: bool = Field(description="Whether the claim is supported by recent game output")
    reason: str = Field(description="Explanation for the judgment (logged, not shown to agent)")

class GroundingValidationResponse(BaseModel):
    judgments: list[GroundingJudgment] = Field(description="One judgment per candidate")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_grounding.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/llm/models.py tests/test_grounding.py
git commit -m "feat(grounding): add GroundingJudgment and GroundingValidationResponse models"
```

---

### Task 3: Grounding Validator Prompt

**Files:**
- Create: `prompts/grounding_validator.md`

- [ ] **Step 1: Write the prompt**

Create `prompts/grounding_validator.md`:

```markdown
You are a grounding validator for an AI playing a text adventure game.

You will receive:
1. **Recent game history**: The last several action/response pairs showing what actually happened.
2. **Current state**: The player's current location and inventory.
3. **Candidates**: One or more claims (memories or objectives) to validate.

Your job: for each candidate, determine if every factual assertion in it is **directly supported** by the game output in the recent history.

## Grounding Rules

A claim is **grounded** if:
- Every item, NPC, location, or mechanic it references appeared explicitly in game text (room descriptions, game responses, parser output).
- Cause-and-effect relationships it describes match what actually happened (the action taken, the response received, any score change).
- Locations it references match where events actually occurred.

A claim is **ungrounded** if:
- It attributes items to locations where they were not found (items in inventory are CARRIED, not native to the room).
- It references entities, items, or locations that never appeared in the game text provided.
- It invents mechanics or puzzle solutions not demonstrated in the game output.
- It infers hidden information from parser prompts (e.g., "What do you want to unlock with?" does not reveal which key works).
- It confuses what the player did (dropped/placed an item) with what was originally in a location.

{grounding_rules}

## Output

For each candidate, provide:
- **item**: The title or text of the candidate (copy it exactly).
- **grounded**: true if the claim is supported, false if not.
- **reason**: Brief explanation of why (1-2 sentences).
```

- [ ] **Step 2: Verify prompt loads**

Run: `uv run python -c "from zorkburr.llm.prompts import load_prompt; p = load_prompt('grounding_validator'); print(f'Loaded {len(p)} chars, has placeholder: {\"{grounding_rules}\" in p}')"`
Expected: `Loaded <N> chars, has placeholder: True`

- [ ] **Step 3: Commit**

```bash
git add prompts/grounding_validator.md
git commit -m "feat(grounding): add shared grounding validator prompt"
```

---

### Task 4: Grounding Actions — `_call_grounding_validator()`

**Files:**
- Create: `zorkburr/actions/grounding.py`
- Test: `tests/test_grounding.py`

- [ ] **Step 1: Write the failing test for the shared validator function**

Append to `tests/test_grounding.py`:

```python
from unittest.mock import MagicMock
from burr.core import State
from zorkburr.state import S, create_initial_state
from zorkburr.config import GameConfig
from zorkburr.llm.models import GroundingJudgment, GroundingValidationResponse
from zorkburr.actions.grounding import _call_grounding_validator


def _make_action_history(entries: list[tuple[str, str]]) -> list[dict]:
    """Helper: build action history from (action, response) pairs."""
    return [{"turn": i + 1, "action": a, "response": r} for i, (a, r) in enumerate(entries)]


def test_call_grounding_validator_returns_judgments():
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Open trapdoor", grounded=True, reason="Trapdoor visible in room"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    history = _make_action_history([("look", "You see a trapdoor."), ("open trapdoor", "The trapdoor opens.")])

    result = _call_grounding_validator(
        client=mock_client,
        config=config,
        candidates=[{"item": "Open trapdoor"}],
        addendum="",
        action_history=history,
        location_name="Living Room",
        location_id=10,
        inventory=["lamp"],
    )
    assert len(result.judgments) == 1
    assert result.judgments[0].grounded is True
    # Verify the prompt was assembled with grounding_rules placeholder filled
    call_args = mock_client.create.call_args
    messages = call_args.kwargs["messages"]
    assert "{grounding_rules}" not in messages[0]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_grounding.py::test_call_grounding_validator_returns_judgments -v`
Expected: FAIL with `ImportError: cannot import name '_call_grounding_validator'`

- [ ] **Step 3: Implement `_call_grounding_validator()` in `grounding.py`**

Create `zorkburr/actions/grounding.py`:

```python
"""Grounding validation: reject hallucinated memories and objectives."""
from __future__ import annotations
import logging

import instructor
from burr.core import State
from langfuse import observe

from zorkburr.actions import action
from zorkburr.actions.episode import persist_memories, persist_summaries
from zorkburr.actions.memory import generate_location_summary
from zorkburr.config import GameConfig
from zorkburr.llm.client import thinking_kwargs
from zorkburr.llm.models import GroundingValidationResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

_grounding_prompt: str | None = None

MEMORY_ADDENDUM = """
## Memory-Specific Rules
- Items listed in the player's inventory are CARRIED by the player. They are NOT native to the current location. Only validate a memory claiming an item is "found here" if the game response explicitly describes the item as present in the room (on a table, in a corner, etc.).
- Mechanics described must match the actual game response. If the game said "The door is locked," the memory should not claim "The door opens easily."
- Score changes must correspond to the action that was actually taken, not an invented cause.
"""

OBJECTIVE_ADDENDUM = """
## Objective-Specific Rules
- Every item, NPC, or location referenced in the objective must have appeared in the recent game text.
- Parser prompts like "What do you want to unlock with?" do NOT reveal which tool to use. Do not validate objectives that name specific tools not yet seen in game output.
- Objectives must describe actions based on observed game state, not inferred puzzle solutions or general game knowledge.
"""


def _get_grounding_prompt() -> str:
    global _grounding_prompt
    if _grounding_prompt is None:
        _grounding_prompt = load_prompt("grounding_validator")
    return _grounding_prompt


def _call_grounding_validator(
    client: instructor.Instructor,
    config: GameConfig,
    candidates: list[dict],
    addendum: str,
    action_history: list[dict],
    location_name: str,
    location_id: int,
    inventory: list[str],
) -> GroundingValidationResponse:
    """Call the grounding validator LLM with the shared prompt + type-specific addendum."""
    prompt = _get_grounding_prompt().replace("{grounding_rules}", addendum)

    recent = action_history[-5:]
    history_lines = []
    for entry in recent:
        history_lines.append(
            f"Turn {entry['turn']}: Action: {entry['action']}\n"
            f"  Response: {entry.get('response', '')[:300]}"
        )

    inv_str = ", ".join(inventory) if inventory else "(empty)"
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(f"- {c['item']}")

    user_content = (
        f"**Current Location:** {location_name} (ID: {location_id})\n"
        f"**Inventory:** {inv_str}\n\n"
        f"**Recent Game History:**\n" + "\n".join(history_lines) + "\n\n"
        f"**Candidates to validate:**\n" + "\n".join(candidate_lines)
    )

    return client.create(
        model=config.critic_model,
        response_model=GroundingValidationResponse,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=512,
        max_retries=2,
        **thinking_kwargs(config, config.critic_model, False),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_grounding.py::test_call_grounding_validator_returns_judgments -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/grounding.py tests/test_grounding.py
git commit -m "feat(grounding): implement shared _call_grounding_validator function"
```

---

### Task 5: `validate_memory` Action

**Files:**
- Modify: `zorkburr/actions/grounding.py`
- Test: `tests/test_grounding.py`

- [ ] **Step 1: Write failing tests for `validate_memory`**

Append to `tests/test_grounding.py`:

```python
from zorkburr.actions.grounding import validate_memory


def _base_state_with_pending_memory() -> State:
    """Build a state with a pending memory ready for validation."""
    state = create_initial_state(episode_id="test-ep")
    return state.update(**{
        S.ACTION_HISTORY: _make_action_history([
            ("open mailbox", "Opening the small mailbox reveals a leaflet."),
        ]),
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.PRE_LOCATION_NAME: "West of House",
        S.INVENTORY: ["lamp"],
        S.TURN_COUNT: 5,
        S.PENDING_MEMORY: {
            "memory": {
                "category": "DISCOVERY",
                "title": "Leaflet in Mailbox",
                "text": "Open mailbox to find a leaflet inside.",
                "episode": "test-ep",
                "turn": 5,
                "persistence": "permanent",
                "status": "ACTIVE",
                "superseded_by": "",
            },
            "supersedes_titles": [],
            "loc_key": "10",
        },
    })


def test_validate_memory_pass_through_when_no_pending():
    """No pending memory -> no LLM call, state unchanged."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep")

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is False
    assert result["reason"] == "no_pending"
    mock_client.create.assert_not_called()


def test_validate_memory_accepted():
    """Grounded memory gets committed to MEMORIES_BY_LOCATION."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Leaflet in Mailbox", grounded=True, reason="Mailbox opened, leaflet found"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is True
    assert new_state[S.PENDING_MEMORY] is None
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems
    assert mems["10"][-1]["title"] == "Leaflet in Mailbox"
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_validate_memory_rejected():
    """Ungrounded memory gets dropped, stats updated."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Leaflet in Mailbox", grounded=False, reason="Leaflet was carried, not found here"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is False
    assert result["reason"] == "ungrounded"
    assert new_state[S.PENDING_MEMORY] is None
    # Memory NOT committed
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert mems.get("10", []) == []
    assert new_state[S.MEMORY_STATS]["grounding_rejected"] == 1


def test_validate_memory_disabled():
    """When grounding validator is disabled, commits unconditionally."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key", enable_grounding_validator=False)
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is True
    mock_client.create.assert_not_called()
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grounding.py::test_validate_memory_pass_through_when_no_pending tests/test_grounding.py::test_validate_memory_accepted tests/test_grounding.py::test_validate_memory_rejected tests/test_grounding.py::test_validate_memory_disabled -v`
Expected: FAIL with `ImportError: cannot import name 'validate_memory'`

- [ ] **Step 3: Implement `validate_memory`**

Append to `zorkburr/actions/grounding.py`:

```python
def _commit_memory(state: State, pending: dict, config: GameConfig, client: instructor.Instructor) -> tuple[dict, State]:
    """Commit a validated pending memory to state. Handles supersession, stats, summaries."""
    mem_dict = pending["memory"]
    loc_key = pending["loc_key"]
    supersedes_titles = pending.get("supersedes_titles", [])

    all_mems = dict(state[S.MEMORIES_BY_LOCATION])
    loc_list = list(all_mems.get(loc_key, []))

    # Process supersession
    superseded_count = 0
    for old_title in supersedes_titles:
        for m in loc_list:
            if m.get("title") == old_title and m.get("status") != "SUPERSEDED":
                m["status"] = "SUPERSEDED"
                m["superseded_by"] = mem_dict["title"]
                logger.info(f"Superseded memory '{old_title}' with '{mem_dict['title']}' at location {loc_key}")
                superseded_count += 1
                break

    loc_list.append(mem_dict)
    all_mems[loc_key] = loc_list
    persist_memories(all_mems, config)

    # Regenerate location summary
    summaries = dict(state[S.LOCATION_SUMMARIES])
    summary = generate_location_summary(
        loc_key, state[S.PRE_LOCATION_NAME], loc_list, client, config,
    )
    if summary:
        summaries[loc_key] = summary
        persist_summaries(summaries, config)

    stats = dict(state[S.MEMORY_STATS])
    stats["new"] = stats.get("new", 0) + 1
    stats["superseded"] = stats.get("superseded", 0) + superseded_count

    new_state = state.update(**{
        S.MEMORIES_BY_LOCATION: all_mems,
        S.MEMORY_STATS: stats,
        S.LOCATION_SUMMARIES: summaries,
        S.PENDING_MEMORY: None,
    })
    return {"validated": True, "memory_title": mem_dict["title"]}, new_state


@action(
    reads=[S.PENDING_MEMORY, S.ACTION_HISTORY, S.LOCATION_NAME, S.LOCATION_ID,
           S.INVENTORY, S.MEMORIES_BY_LOCATION, S.MEMORY_STATS,
           S.LOCATION_SUMMARIES, S.PRE_LOCATION_NAME, S.EPISODE_ID, S.TURN_COUNT],
    writes=[S.MEMORIES_BY_LOCATION, S.MEMORY_STATS, S.LOCATION_SUMMARIES, S.PENDING_MEMORY],
)
@observe()
def validate_memory(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    """Validate a pending memory against recent game output. Accept or drop."""
    pending = state[S.PENDING_MEMORY]
    if not pending:
        return {"validated": False, "reason": "no_pending"}, state

    # If validator disabled, commit unconditionally
    if not config.enable_grounding_validator:
        return _commit_memory(state, pending, config, client)

    mem_dict = pending["memory"]
    try:
        response = _call_grounding_validator(
            client=client,
            config=config,
            candidates=[{"item": mem_dict["title"]}],
            addendum=MEMORY_ADDENDUM,
            action_history=state[S.ACTION_HISTORY],
            location_name=state[S.LOCATION_NAME],
            location_id=state[S.LOCATION_ID],
            inventory=state[S.INVENTORY],
        )
        if response.judgments and response.judgments[0].grounded:
            logger.info(f"Grounding accepted memory: '{mem_dict['title']}'")
            return _commit_memory(state, pending, config, client)
        else:
            reason = response.judgments[0].reason if response.judgments else "no judgment returned"
            logger.info(f"Grounding rejected memory: '{mem_dict['title']}' — {reason}")
            stats = dict(state[S.MEMORY_STATS])
            stats["grounding_rejected"] = stats.get("grounding_rejected", 0) + 1
            return (
                {"validated": False, "reason": "ungrounded"},
                state.update(**{S.PENDING_MEMORY: None, S.MEMORY_STATS: stats}),
            )
    except Exception as e:
        logger.warning(f"Grounding validation failed for memory '{mem_dict['title']}': {e}")
        # On error, commit anyway (fail open)
        return _commit_memory(state, pending, config, client)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grounding.py -k "validate_memory" -v`
Expected: All 4 PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/grounding.py tests/test_grounding.py
git commit -m "feat(grounding): implement validate_memory action"
```

---

### Task 6: `validate_objectives` Action

**Files:**
- Modify: `zorkburr/actions/grounding.py`
- Test: `tests/test_grounding.py`

- [ ] **Step 1: Write failing tests for `validate_objectives`**

Append to `tests/test_grounding.py`:

```python
from zorkburr.actions.grounding import validate_objectives


def _base_state_with_pending_objectives() -> State:
    """Build a state with pending objectives ready for validation."""
    state = create_initial_state(episode_id="test-ep")
    return state.update(**{
        S.ACTION_HISTORY: _make_action_history([
            ("look", "You are west of a white house. There is a mailbox here."),
            ("open mailbox", "Opening the small mailbox reveals a leaflet."),
        ]),
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.INVENTORY: ["lamp"],
        S.TURN_COUNT: 10,
        S.PENDING_OBJECTIVES: [
            {"text": "Read the leaflet", "location_id": 10, "location_name": "West of House"},
            {"text": "Find the golden key in the attic", "location_id": 0, "location_name": ""},
        ],
        S.PENDING_COMPLETED_OBJECTIVES: ["Open the mailbox"],
    })


def test_validate_objectives_pass_through_when_no_pending():
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep")

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 0
    mock_client.create.assert_not_called()


def test_validate_objectives_filters_ungrounded():
    """Only grounded objectives get committed; ungrounded ones are dropped."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Read the leaflet", grounded=True, reason="Leaflet found in mailbox"),
        GroundingJudgment(item="Find the golden key in the attic", grounded=False, reason="No attic or key seen"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_objectives()

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 1
    assert result["rejected"] == 1
    assert new_state[S.PENDING_OBJECTIVES] is None
    assert new_state[S.PENDING_COMPLETED_OBJECTIVES] is None
    # Only grounded objective committed
    obj_texts = [o["text"] if isinstance(o, dict) else o for o in new_state[S.DISCOVERED_OBJECTIVES]]
    assert "Read the leaflet" in obj_texts
    assert "Find the golden key in the attic" not in obj_texts
    # Completed objectives always committed
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1
    assert new_state[S.COMPLETED_OBJECTIVES][0]["objective"] == "Open the mailbox"


def test_validate_objectives_completions_committed_without_pending():
    """Completed objectives are committed even when no new objectives are pending."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.TURN_COUNT: 10,
        S.PENDING_OBJECTIVES: None,
        S.PENDING_COMPLETED_OBJECTIVES: ["Explore the house"],
    })

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    mock_client.create.assert_not_called()
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1


def test_validate_objectives_disabled():
    """When grounding validator is disabled, commits all objectives unconditionally."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key", enable_grounding_validator=False)
    state = _base_state_with_pending_objectives()

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 2
    mock_client.create.assert_not_called()
    obj_texts = [o["text"] if isinstance(o, dict) else o for o in new_state[S.DISCOVERED_OBJECTIVES]]
    assert "Read the leaflet" in obj_texts
    assert "Find the golden key in the attic" in obj_texts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grounding.py -k "validate_objectives" -v`
Expected: FAIL with `ImportError: cannot import name 'validate_objectives'`

- [ ] **Step 3: Implement `validate_objectives`**

Append to `zorkburr/actions/grounding.py`:

```python
def _commit_completed_objectives(state: State) -> State:
    """Commit pending completed objectives to state."""
    pending_completed = state[S.PENDING_COMPLETED_OBJECTIVES]
    if not pending_completed:
        return state.update(**{S.PENDING_COMPLETED_OBJECTIVES: None})
    completed = set(pending_completed)
    existing_objs = state[S.DISCOVERED_OBJECTIVES]
    remaining = [o for o in existing_objs if (o["text"] if isinstance(o, dict) else str(o)) not in completed]
    records = list(state[S.COMPLETED_OBJECTIVES])
    for obj_text in completed:
        records.append({"objective": obj_text, "completed_turn": state[S.TURN_COUNT]})
    return state.update(**{
        S.DISCOVERED_OBJECTIVES: remaining,
        S.COMPLETED_OBJECTIVES: records,
        S.PENDING_COMPLETED_OBJECTIVES: None,
    })


@action(
    reads=[S.PENDING_OBJECTIVES, S.PENDING_COMPLETED_OBJECTIVES, S.ACTION_HISTORY,
           S.LOCATION_NAME, S.LOCATION_ID, S.INVENTORY,
           S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.TURN_COUNT],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES,
            S.PENDING_OBJECTIVES, S.PENDING_COMPLETED_OBJECTIVES],
)
@observe()
def validate_objectives(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    """Validate pending objectives against recent game output. Accept grounded, drop ungrounded."""
    pending = state[S.PENDING_OBJECTIVES]

    # Always commit completions (they're removals, not assertions)
    state = _commit_completed_objectives(state)

    if not pending:
        return {"validated": 0, "rejected": 0, "reason": "no_pending"}, state.update(**{S.PENDING_OBJECTIVES: None})

    # If validator disabled, commit all
    if not config.enable_grounding_validator:
        existing = list(state[S.DISCOVERED_OBJECTIVES])
        existing_texts = {o["text"] if isinstance(o, dict) else str(o) for o in existing}
        for obj in pending:
            if obj["text"] not in existing_texts:
                existing.append(obj)
                existing_texts.add(obj["text"])
        existing = existing[:15]
        return (
            {"validated": len(pending), "rejected": 0},
            state.update(**{S.DISCOVERED_OBJECTIVES: existing, S.PENDING_OBJECTIVES: None}),
        )

    # Validate with LLM
    candidates = [{"item": obj["text"]} for obj in pending]
    try:
        response = _call_grounding_validator(
            client=client,
            config=config,
            candidates=candidates,
            addendum=OBJECTIVE_ADDENDUM,
            action_history=state[S.ACTION_HISTORY],
            location_name=state[S.LOCATION_NAME],
            location_id=state[S.LOCATION_ID],
            inventory=state[S.INVENTORY],
        )
        # Build lookup of grounded items
        grounded_items = {j.item for j in response.judgments if j.grounded}
        rejected_items = {j.item for j in response.judgments if not j.grounded}

        for j in response.judgments:
            if j.grounded:
                logger.info(f"Grounding accepted objective: '{j.item}'")
            else:
                logger.info(f"Grounding rejected objective: '{j.item}' — {j.reason}")

        # Commit only grounded objectives
        accepted = [obj for obj in pending if obj["text"] in grounded_items]
        existing = list(state[S.DISCOVERED_OBJECTIVES])
        existing_texts = {o["text"] if isinstance(o, dict) else str(o) for o in existing}
        for obj in accepted:
            if obj["text"] not in existing_texts:
                existing.append(obj)
                existing_texts.add(obj["text"])
        existing = existing[:15]

        return (
            {"validated": len(accepted), "rejected": len(rejected_items)},
            state.update(**{S.DISCOVERED_OBJECTIVES: existing, S.PENDING_OBJECTIVES: None}),
        )
    except Exception as e:
        logger.warning(f"Grounding validation failed for objectives: {e}")
        # Fail open: commit all
        existing = list(state[S.DISCOVERED_OBJECTIVES])
        existing_texts = {o["text"] if isinstance(o, dict) else str(o) for o in existing}
        for obj in pending:
            if obj["text"] not in existing_texts:
                existing.append(obj)
                existing_texts.add(obj["text"])
        existing = existing[:15]
        return (
            {"validated": len(pending), "rejected": 0},
            state.update(**{S.DISCOVERED_OBJECTIVES: existing, S.PENDING_OBJECTIVES: None}),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grounding.py -k "validate_objectives" -v`
Expected: All 4 PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/grounding.py tests/test_grounding.py
git commit -m "feat(grounding): implement validate_objectives action"
```

---

### Task 7: Modify `record_memory` to Write Pending

**Files:**
- Modify: `zorkburr/actions/memory.py:92-194`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_grounding.py`:

```python
from zorkburr.actions.memory import record_memory


def test_record_memory_writes_pending_instead_of_committing():
    """record_memory should set PENDING_MEMORY instead of writing to MEMORIES_BY_LOCATION."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True,
        reasoning="Score changed",
        category="SUCCESS",
        memory_title="Mailbox Leaflet Found",
        memory_text="Open mailbox to find leaflet.",
        persistence="permanent",
        status="ACTIVE",
        supersedes_titles=[],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.PRE_LOCATION_ID: 10,
        S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0,
        S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10,
        S.SCORE: 10,  # Score changed -> triggers synthesis
        S.INVENTORY: [],
        S.GAME_OVER: False,
        S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox",
        S.AGENT_REASONING: "Check the mailbox",
        S.ACTION_HISTORY: _make_action_history([("open mailbox", "Opening the mailbox reveals a leaflet.")]),
        S.TURN_COUNT: 5,
    })

    result, new_state = record_memory.run(state, client=mock_client, config=config)
    assert result["synthesized"] is True
    # Memory should be in PENDING_MEMORY, NOT in MEMORIES_BY_LOCATION
    assert new_state[S.PENDING_MEMORY] is not None
    assert new_state[S.PENDING_MEMORY]["memory"]["title"] == "Mailbox Leaflet Found"
    assert new_state[S.PENDING_MEMORY]["loc_key"] == "10"
    # MEMORIES_BY_LOCATION should be unchanged (empty)
    assert new_state[S.MEMORIES_BY_LOCATION] == {}
```

Add this import at the top of the test file alongside the other model imports:

```python
from zorkburr.llm.models import MemorySynthesisResponse
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_grounding.py::test_record_memory_writes_pending_instead_of_committing -v`
Expected: FAIL — `PENDING_MEMORY` is None because `record_memory` still commits directly

- [ ] **Step 3: Modify `record_memory` to write to `PENDING_MEMORY`**

In `zorkburr/actions/memory.py`, replace the `record_memory` action (lines 92-194). The key changes:

1. Add `S.PENDING_MEMORY` to the `writes` list.
2. Remove `S.LOCATION_SUMMARIES` from `writes` (moved to `validate_memory`).
3. After the dedup guard, instead of committing to `MEMORIES_BY_LOCATION`, write to `PENDING_MEMORY`.
4. Remove the summary generation, stats update, and `persist_memories` call — these move to `validate_memory`.

Replace the `@action` decorator and function body:

```python
@action(
    reads=[S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME, S.PRE_SCORE, S.PRE_INVENTORY,
           S.LOCATION_ID, S.SCORE, S.INVENTORY, S.GAME_OVER, S.GAME_OVER_REASON,
           S.GAME_RESPONSE, S.ACTION_TO_TAKE, S.AGENT_REASONING, S.ACTION_HISTORY,
           S.MEMORIES_BY_LOCATION, S.EPISODE_ID, S.TURN_COUNT, S.MEMORY_STATS],
    writes=[S.PENDING_MEMORY, S.MEMORY_STATS],
)
@observe()
def record_memory(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    location_changed = state[S.LOCATION_ID] != state[S.PRE_LOCATION_ID]
    died = state[S.GAME_OVER] and state[S.GAME_OVER_REASON] == "death"

    if not should_synthesize(score_delta, location_changed, died):
        return {"synthesized": False}, state

    pre_inv = state[S.PRE_INVENTORY]
    inv_str = ", ".join(pre_inv) if pre_inv else "(empty)"
    context = (
        f"Location: {state[S.PRE_LOCATION_NAME]} (ID: {state[S.PRE_LOCATION_ID]})\n"
        f"Inventory (items agent was CARRYING, not found here): {inv_str}\n"
        f"Action: {state[S.ACTION_TO_TAKE]}\n"
        f"Agent reasoning: {state[S.AGENT_REASONING]}\n"
        f"Response: {state[S.GAME_RESPONSE][:500]}\n\n"
        f"Score change: {score_delta}\nLocation changed: {location_changed}\nDied: {died}\n"
    )

    loc_key = str(state[S.PRE_LOCATION_ID])
    existing = state[S.MEMORIES_BY_LOCATION].get(loc_key, [])
    if existing:
        mem_lines = [f"  - [{m['title']}]: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
        context += f"\nExisting memories at this location:\n" + "\n".join(mem_lines)

    try:
        response: MemorySynthesisResponse = client.create(
            model=config.memory_model,
            response_model=MemorySynthesisResponse,
            messages=[
                {"role": "system", "content": _get_synthesis_prompt()},
                {"role": "user", "content": context},
            ],
            temperature=0.5, max_tokens=512, max_retries=2,
            **thinking_kwargs(config, config.memory_model, False),
        )
        if response.should_remember:
            # Dedup guard: reject exact title matches against non-superseded memories
            existing_titles = {m.get("title") for m in existing if m.get("status") != "SUPERSEDED"}
            if response.memory_title in existing_titles:
                logger.info(f"Rejected duplicate memory title: '{response.memory_title}' at location {loc_key}")
                stats = dict(state[S.MEMORY_STATS])
                stats["dedup_rejected"] = stats.get("dedup_rejected", 0) + 1
                return {"synthesized": False, "reason": "duplicate_title"}, state.update(**{S.MEMORY_STATS: stats})

            mem = Memory(
                category=response.category, title=response.memory_title,
                text=response.memory_text, episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT], persistence=response.persistence,
                status=response.status,
            )
            pending = {
                "memory": mem.to_dict(),
                "supersedes_titles": response.supersedes_titles,
                "loc_key": loc_key,
            }
            return (
                {"synthesized": True, "memory_title": mem.title},
                state.update(**{S.PENDING_MEMORY: pending}),
            )
    except Exception as e:
        logger.warning(f"Memory synthesis failed: {e}")

    return {"synthesized": False}, state
```

Also remove the `persist_memories`, `persist_summaries` imports from memory.py since they're no longer used there (they're now only in `grounding.py`). Remove this import line:

```python
from zorkburr.actions.episode import persist_memories, persist_summaries
```

And remove `S.LOCATION_SUMMARIES` from the reads list as well.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_grounding.py::test_record_memory_writes_pending_instead_of_committing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/memory.py tests/test_grounding.py
git commit -m "refactor(memory): record_memory writes to PENDING_MEMORY instead of committing directly"
```

---

### Task 8: Modify `update_objectives` to Write Pending

**Files:**
- Modify: `zorkburr/actions/objectives.py:60-119`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_grounding.py`:

```python
from zorkburr.actions.objectives import update_objectives
from zorkburr.llm.models import ObjectiveDiscoveryResponse, Objective


def test_update_objectives_writes_pending():
    """update_objectives should set PENDING_OBJECTIVES instead of committing directly."""
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=[Objective(text="Read the leaflet", location_id=10, location_name="West of House")],
        completed=["Open the mailbox"],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.ACTION_HISTORY: _make_action_history([("open mailbox", "Opening reveals a leaflet.")]),
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.SCORE: 10,
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.TURN_COUNT: 10,
        S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {"rooms": {"10": "West of House"}},
        S.DISCOVERED_OBJECTIVES: [{"text": "Open the mailbox", "location_id": 10, "location_name": "West of House"}],
    })

    result, new_state = update_objectives.run(state, client=mock_client, config=config, use_thinking=False)
    assert result["new_count"] == 1
    # New objectives should be PENDING, not committed
    assert new_state[S.PENDING_OBJECTIVES] is not None
    assert len(new_state[S.PENDING_OBJECTIVES]) == 1
    assert new_state[S.PENDING_OBJECTIVES][0]["text"] == "Read the leaflet"
    # Completions should be pending too
    assert new_state[S.PENDING_COMPLETED_OBJECTIVES] == ["Open the mailbox"]
    # DISCOVERED_OBJECTIVES should be unchanged (still has the old one)
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 1
    assert new_state[S.DISCOVERED_OBJECTIVES][0]["text"] == "Open the mailbox"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_grounding.py::test_update_objectives_writes_pending -v`
Expected: FAIL — objectives still committed directly to `DISCOVERED_OBJECTIVES`

- [ ] **Step 3: Modify `update_objectives`**

In `zorkburr/actions/objectives.py`, update the `update_objectives` action:

1. Add `S.PENDING_OBJECTIVES` and `S.PENDING_COMPLETED_OBJECTIVES` to `writes`.
2. Remove `S.COMPLETED_OBJECTIVES` from `writes` (moved to `validate_objectives`).
3. Instead of committing, write to pending state keys.

Replace the `@action` decorator and function body:

```python
@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.ACTION_HISTORY,
           S.GAME_RESPONSE, S.SCORE, S.LOCATION_NAME, S.LOCATION_ID, S.TURN_COUNT, S.KNOWLEDGE_BASE,
           S.MAP_DATA],
    writes=[S.PENDING_OBJECTIVES, S.PENDING_COMPLETED_OBJECTIVES],
)
@observe()
def update_objectives(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent_actions = state[S.ACTION_HISTORY][-10:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:200]}" for a in recent_actions
    )
    current_objectives = state[S.DISCOVERED_OBJECTIVES]
    current_texts = [_obj_text(o) for o in current_objectives]
    kb_content = state[S.KNOWLEDGE_BASE] or ""
    kb_section = f"\n\nStrategic Knowledge (accumulated from prior episodes):\n{kb_content}" if kb_content else ""
    user_msg = (
        f"Current location: {state[S.LOCATION_NAME]} (ID: {state[S.LOCATION_ID]})\nScore: {state[S.SCORE]}\n"
        f"Current objectives: {current_texts}\n\nRecent gameplay:\n{action_summary}"
        f"{kb_section}"
    )
    try:
        response: ObjectiveDiscoveryResponse = client.create(
            model=config.analysis_model,
            response_model=ObjectiveDiscoveryResponse,
            messages=[{"role": "system", "content": _get_discovery_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=512, max_retries=2,
            **thinking_kwargs(config, config.analysis_model, use_thinking),
        )
        # Resolve location_id from location_name using map data
        map_data = state[S.MAP_DATA]
        rooms = map_data.get("rooms", {})
        cur_loc_name = state[S.LOCATION_NAME]
        cur_loc_id = state[S.LOCATION_ID]
        for obj in response.objectives:
            if obj.location_id == 0 and obj.location_name:
                resolved = _resolve_location_id(obj.location_name, cur_loc_name, cur_loc_id, rooms)
                if resolved != 0:
                    obj.location_id = resolved
                    logger.debug(f"Resolved objective location '{obj.location_name}' -> ID {resolved}")

        # Filter to truly new objectives
        existing_texts = {_obj_text(o) for o in current_objectives}
        new_objectives = []
        for obj in response.objectives:
            if obj.text not in existing_texts:
                new_objectives.append({"text": obj.text, "location_id": obj.location_id, "location_name": obj.location_name})
                existing_texts.add(obj.text)

        return (
            {"new_count": len(new_objectives)},
            state.update(**{
                S.PENDING_OBJECTIVES: new_objectives if new_objectives else None,
                S.PENDING_COMPLETED_OBJECTIVES: list(response.completed) if response.completed else None,
            }),
        )
    except Exception as e:
        logger.warning(f"Objective update failed: {e}")
    return {"new_count": 0}, state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_grounding.py::test_update_objectives_writes_pending -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/objectives.py tests/test_grounding.py
git commit -m "refactor(objectives): update_objectives writes to PENDING_OBJECTIVES instead of committing directly"
```

---

### Task 9: Wire Into Burr Graph

**Files:**
- Modify: `zorkburr/app.py`

- [ ] **Step 1: Update imports in `app.py`**

Add the grounding imports. After the existing objectives import line, add:

```python
from zorkburr.actions.grounding import validate_memory, validate_objectives
```

- [ ] **Step 2: Update the builder actions and transitions**

In `build_turn_app()`, add the new actions to `.with_actions()` and update transitions.

Add to `.with_actions()`:

```python
            validate_memory=validate_memory.bind(client=client, config=config),
            validate_objectives=validate_objectives.bind(client=client, config=config),
```

Replace the transitions block (the `.with_transitions(...)` call) with:

```python
        .with_transitions(
            # Core loop
            ("assemble_context", "generate_action"),
            ("generate_action", "evaluate_action"),
            # Accepted: score >= threshold
            ("evaluate_action", "execute_action", expr(f"critic_score >= {threshold}")),
            # Max rejections reached — force accept
            ("evaluate_action", "execute_action", expr(f"rejection_count >= {max_rejections}")),
            # Rejected — retry
            ("evaluate_action", "generate_action", default),
            # Post-execution pipeline
            ("execute_action", "extract_info"),
            ("extract_info", "record_results"),
            ("record_results", "record_memory"),
            ("record_memory", "validate_memory"),
            ("validate_memory", "check_objective_completion"),
            # Periodic updates (conditional)
            ("check_objective_completion", "update_objectives",
             expr(f"turn_count > 0 and turn_count % {obj_interval} == 0 and game_over == False")),
            ("check_objective_completion", "turn_complete", when(**{S.GAME_OVER: True})),
            ("check_objective_completion", "assemble_context", default),
            ("update_objectives", "validate_objectives"),
            ("validate_objectives", "assemble_context", default),
        )
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL — the mock LLM doesn't handle `GroundingValidationResponse` yet

- [ ] **Step 4: Update test mock in `test_app.py`**

In `tests/test_app.py`, add the import:

```python
from zorkburr.llm.models import GroundingValidationResponse, GroundingJudgment
```

Then update `_mock_llm_side_effect` to handle the new model. Add this case before the `return MagicMock()` fallback:

```python
    elif model == GroundingValidationResponse:
        # Auto-accept all grounding validations in tests
        return GroundingValidationResponse(judgments=[])
```

Also update `side_effect_with_rejection` in `test_turn_graph_with_critic` with the same case.

- [ ] **Step 5: Run integration tests again**

Run: `uv run pytest tests/test_app.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/ --ignore=tests/test_llm_client.py --ignore=tests/test_llm_llama_server.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add zorkburr/app.py tests/test_app.py
git commit -m "feat(grounding): wire validate_memory and validate_objectives into Burr graph"
```

---

### Task 10: End-to-End Test

**Files:**
- Test: `tests/test_grounding.py`

- [ ] **Step 1: Write end-to-end test verifying the full pipeline**

Append to `tests/test_grounding.py`:

```python
from zorkburr.actions.memory import record_memory, should_synthesize
from zorkburr.actions.grounding import validate_memory


def test_memory_pipeline_propose_then_validate():
    """Full pipeline: record_memory proposes -> validate_memory accepts or rejects."""
    # Step 1: record_memory produces a pending memory
    synth_client = MagicMock()
    synth_client.create.return_value = MemorySynthesisResponse(
        should_remember=True,
        reasoning="Score changed, important",
        category="SUCCESS",
        memory_title="Trapdoor Opened",
        memory_text="Push rug then open trapdoor to access cellar.",
        persistence="permanent",
        status="ACTIVE",
        supersedes_titles=[],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="e2e-test").update(**{
        S.PRE_LOCATION_ID: 20,
        S.PRE_LOCATION_NAME: "Living Room",
        S.PRE_SCORE: 0,
        S.PRE_INVENTORY: ["lamp"],
        S.LOCATION_ID: 20,
        S.SCORE: 5,
        S.INVENTORY: ["lamp"],
        S.GAME_OVER: False,
        S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "The rug moves aside revealing a trapdoor. You open it.",
        S.ACTION_TO_TAKE: "open trapdoor",
        S.AGENT_REASONING: "Try opening the trapdoor",
        S.ACTION_HISTORY: _make_action_history([
            ("push rug", "The rug moves aside revealing a trapdoor."),
            ("open trapdoor", "The rug moves aside revealing a trapdoor. You open it."),
        ]),
        S.TURN_COUNT: 8,
    })

    _, state_after_record = record_memory.run(state, client=synth_client, config=config)
    assert state_after_record[S.PENDING_MEMORY] is not None

    # Step 2: validate_memory accepts the grounded memory
    val_client = MagicMock()
    val_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Trapdoor Opened", grounded=True, reason="Trapdoor seen in game text"),
    ])

    result, final_state = validate_memory.run(state_after_record, client=val_client, config=config)
    assert result["validated"] is True
    assert final_state[S.PENDING_MEMORY] is None
    assert "20" in final_state[S.MEMORIES_BY_LOCATION]
    assert final_state[S.MEMORIES_BY_LOCATION]["20"][-1]["title"] == "Trapdoor Opened"


def test_memory_pipeline_propose_then_reject():
    """Full pipeline: record_memory proposes -> validate_memory rejects hallucination."""
    synth_client = MagicMock()
    synth_client.create.return_value = MemorySynthesisResponse(
        should_remember=True,
        reasoning="Found item",
        category="DISCOVERY",
        memory_title="Screwdriver in Forest",
        memory_text="Screwdriver is found on the forest path.",
        persistence="permanent",
        status="ACTIVE",
        supersedes_titles=[],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="e2e-test").update(**{
        S.PRE_LOCATION_ID: 30,
        S.PRE_LOCATION_NAME: "Forest Path",
        S.PRE_SCORE: 0,
        S.PRE_INVENTORY: ["screwdriver"],  # Agent was CARRYING the screwdriver
        S.LOCATION_ID: 31,
        S.SCORE: 0,
        S.INVENTORY: ["screwdriver"],
        S.GAME_OVER: False,
        S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "You walk along the forest path.",
        S.ACTION_TO_TAKE: "drop screwdriver",
        S.AGENT_REASONING: "Drop screwdriver here",
        S.ACTION_HISTORY: _make_action_history([
            ("drop screwdriver", "Dropped."),
        ]),
        S.TURN_COUNT: 12,
    })

    _, state_after_record = record_memory.run(state, client=synth_client, config=config)
    assert state_after_record[S.PENDING_MEMORY] is not None

    # Validator correctly rejects — screwdriver was carried, not found here
    val_client = MagicMock()
    val_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(
            item="Screwdriver in Forest",
            grounded=False,
            reason="Screwdriver was in inventory (carried), agent dropped it — not native to this location",
        ),
    ])

    result, final_state = validate_memory.run(state_after_record, client=val_client, config=config)
    assert result["validated"] is False
    assert final_state[S.PENDING_MEMORY] is None
    assert final_state[S.MEMORIES_BY_LOCATION].get("30", []) == []
    assert final_state[S.MEMORY_STATS]["grounding_rejected"] == 1
```

- [ ] **Step 2: Run end-to-end tests**

Run: `uv run pytest tests/test_grounding.py -k "pipeline" -v`
Expected: All 2 PASS

- [ ] **Step 3: Run full test suite one final time**

Run: `uv run pytest tests/ --ignore=tests/test_llm_client.py --ignore=tests/test_llm_llama_server.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_grounding.py
git commit -m "test(grounding): add end-to-end pipeline tests for propose-then-validate flow"
```
