# Prompt Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require prompt changes to be validated against recorded game data before committing, by extracting Burr turn state into fixtures and replaying through updated prompts.

**Architecture:** Two new scripts — `extract_fixtures.py` pulls turn state from Burr tracker into JSON fixtures, `validate_prompt.py` replays fixtures through the actual Burr actions with a live LLM client and judges results. The orchestrator extracts fixtures at diagnosis time and the improvement subagent runs validation before committing.

**Tech Stack:** Python, Burr State, existing `_args.py` Burr API helpers, Instructor LLM client, Pydantic models

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/extract_fixtures.py` | Extract turn state from Burr tracker into JSON fixture files |
| `scripts/validate_prompt.py` | Replay fixtures through actions, structural checks, LLM judge |
| `tests/fixtures/.gitkeep` | Empty directory marker for fixture storage |
| `tests/test_extract_fixtures.py` | Tests for fixture extraction (mocked Burr API) |
| `tests/test_validate_prompt.py` | Tests for validation logic (mocked LLM) |
| `.claude/commands/zork-orchestrator.md` | Add fixture extraction step, validation requirement, review check |

---

### Task 1: Fixture Directory and Data Schema

**Files:**
- Create: `tests/fixtures/.gitkeep`
- Create: `scripts/extract_fixtures.py` (schema constants only)

- [ ] **Step 1: Create fixtures directory**

```bash
mkdir -p tests/fixtures
touch tests/fixtures/.gitkeep
```

- [ ] **Step 2: Write the state key mapping in extract_fixtures.py**

This is the schema that maps each action type to the state keys it reads and the output keys it writes. This is used by both extraction and validation.

```python
"""Extract turn-state fixtures from the Burr tracker for prompt validation.

Usage:
  python3 scripts/extract_fixtures.py <app_id> --turns 37,42,45 \
    --action generate_action --role problem \
    --description "Agent ignored location memories"
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _args import fetch_steps, get_state, get_action

# Map action_type -> (state keys to capture, output keys to capture)
ACTION_SCHEMA = {
    "generate_action": {
        "state_keys": [
            "formatted_context", "rejection_count", "critic_justification",
            "knowledge_base", "turn_count",
        ],
        "output_keys": [
            "proposed_action", "agent_reasoning", "next_steps", "new_objective",
        ],
    },
    "evaluate_action": {
        "state_keys": [
            "proposed_action", "game_response", "action_history", "exits",
            "inventory", "location_name", "rejection_count", "in_combat",
        ],
        "output_keys": [
            "critic_score", "critic_justification", "critic_confidence",
        ],
    },
    "record_memory": {
        "state_keys": [
            "pre_location_id", "pre_location_name", "pre_score", "pre_inventory",
            "location_id", "score", "inventory", "game_over", "game_over_reason",
            "game_response", "action_to_take", "agent_reasoning", "action_history",
            "memories_by_location", "episode_id", "turn_count", "memory_stats",
            "location_summaries",
        ],
        "output_keys": [
            "memories_by_location", "memory_stats", "location_summaries",
        ],
    },
    "update_knowledge": {
        "state_keys": [
            "knowledge_base", "action_history", "score", "turn_count",
            "memories_by_location",
        ],
        "output_keys": ["knowledge_base"],
    },
    "extract_info": {
        "state_keys": [
            "game_response", "location_name", "location_id", "in_combat",
        ],
        "output_keys": [
            "exits", "in_combat", "is_room_description", "visible_objects",
        ],
    },
    "update_objectives": {
        "state_keys": [
            "discovered_objectives", "completed_objectives", "action_history",
            "game_response", "score", "location_name", "location_id",
            "turn_count", "knowledge_base",
        ],
        "output_keys": ["discovered_objectives", "completed_objectives"],
    },
    "check_objective_completion": {
        "state_keys": [
            "discovered_objectives", "completed_objectives", "game_response",
            "action_to_take", "turn_count", "score", "pre_score",
        ],
        "output_keys": ["discovered_objectives", "completed_objectives"],
    },
}
```

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/.gitkeep scripts/extract_fixtures.py
git commit -m "feat(validation): add fixture directory and action schema constants"
```

---

### Task 2: Fixture Extraction Script

**Files:**
- Modify: `scripts/extract_fixtures.py`
- Test: `tests/test_extract_fixtures.py`

- [ ] **Step 1: Write test for turn-finding logic**

The extraction script needs the same turn-finding logic as `burr_turn.py`. Test that it correctly finds the step for a given action at a given turn.

```python
"""Tests for extract_fixtures.py — fixture extraction from Burr tracker data."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_fixtures import find_action_step, build_fixture, ACTION_SCHEMA


def _make_step(action_name, state_dict):
    """Build a minimal Burr step structure."""
    return {
        "step_start_log": {"action": action_name},
        "step_end_log": {"state": state_dict},
    }


def test_find_action_step_generate_action():
    steps = [
        _make_step("assemble_context", {"turn_count": 0, "formatted_context": "ctx"}),
        _make_step("generate_action", {"turn_count": 0, "proposed_action": "look", "agent_reasoning": "look around", "next_steps": "", "new_objective": ""}),
        _make_step("evaluate_action", {"turn_count": 0, "critic_score": 0.7}),
        _make_step("execute_action", {"turn_count": 1}),
        _make_step("assemble_context", {"turn_count": 1, "formatted_context": "ctx2"}),
        _make_step("generate_action", {"turn_count": 1, "proposed_action": "north", "agent_reasoning": "go north", "next_steps": "explore", "new_objective": ""}),
        _make_step("evaluate_action", {"turn_count": 1, "critic_score": 0.8}),
        _make_step("execute_action", {"turn_count": 2}),
    ]
    state = find_action_step(steps, target_turn=2, action_type="generate_action")
    assert state is not None
    assert state["proposed_action"] == "north"


def test_find_action_step_missing_turn():
    steps = [
        _make_step("execute_action", {"turn_count": 1}),
    ]
    state = find_action_step(steps, target_turn=99, action_type="generate_action")
    assert state is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_extract_fixtures.py -v
```
Expected: FAIL — `find_action_step` not yet implemented.

- [ ] **Step 3: Implement find_action_step and build_fixture**

Add these functions to `scripts/extract_fixtures.py` below the `ACTION_SCHEMA`:

```python
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def find_action_step(steps, target_turn, action_type):
    """Find the state from a specific action at a specific turn.

    Turn numbering: turn_count is incremented by execute_action. Steps before
    execute_action (assemble_context, generate_action, evaluate_action) have
    the PREVIOUS turn's count. So for target_turn=N, we find execute_action
    where turn_count==N, then walk backwards to find the requested action.
    """
    # Find the execute_action step for this turn
    exec_idx = None
    for i, s in enumerate(steps):
        if get_action(s) == "execute_action" and get_state(s).get("turn_count") == target_turn:
            exec_idx = i
            break

    if exec_idx is None:
        return None

    # Walk backwards from execute_action to find the requested action type
    for i in range(exec_idx - 1, -1, -1):
        action_name = get_action(steps[i])
        if action_name == action_type:
            return get_state(steps[i])
        # Stop if we hit a step from a previous turn's post-execute pipeline
        if action_name in ("execute_action", "record_results", "record_memory",
                           "check_objective_completion", "update_objectives",
                           "update_knowledge"):
            break

    # For post-execute actions (record_memory, update_knowledge, etc.),
    # walk forwards from execute_action
    for i in range(exec_idx, len(steps)):
        action_name = get_action(steps[i])
        if action_name == action_type:
            return get_state(steps[i])
        if action_name == "assemble_context" and i > exec_idx:
            break  # hit next turn

    return None


def build_fixture(state, action_type, turn, app_id, role, description=""):
    """Build a fixture dict from a Burr state snapshot."""
    schema = ACTION_SCHEMA[action_type]
    fixture_state = {k: state.get(k) for k in schema["state_keys"]}
    original_output = {k: state.get(k) for k in schema["output_keys"]}

    episode_id = state.get("episode_id", "unknown")
    return {
        "meta": {
            "app_id": app_id,
            "episode_id": episode_id,
            "turn": turn,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "problem_description": description,
        },
        "action_type": action_type,
        "state": fixture_state,
        "original_output": original_output,
    }
```

- [ ] **Step 4: Write test for build_fixture**

Add to `tests/test_extract_fixtures.py`:

```python
def test_build_fixture_captures_correct_keys():
    state = {
        "formatted_context": "You are at the house.",
        "rejection_count": 0,
        "critic_justification": "",
        "knowledge_base": "some kb",
        "turn_count": 5,
        "proposed_action": "look",
        "agent_reasoning": "exploring",
        "next_steps": "",
        "new_objective": "",
        "episode_id": "ep42",
        # Extra keys that should NOT be captured
        "score": 10,
        "location_name": "House",
    }
    fixture = build_fixture(
        state, action_type="generate_action", turn=5,
        app_id="app123", role="problem",
        description="Agent ignored memories",
    )
    assert fixture["meta"]["episode_id"] == "ep42"
    assert fixture["meta"]["role"] == "problem"
    assert fixture["action_type"] == "generate_action"
    assert fixture["state"]["formatted_context"] == "You are at the house."
    assert fixture["state"]["knowledge_base"] == "some kb"
    assert "score" not in fixture["state"]
    assert fixture["original_output"]["proposed_action"] == "look"
    assert fixture["original_output"]["agent_reasoning"] == "exploring"
```

- [ ] **Step 5: Run tests to verify both pass**

```bash
uv run pytest tests/test_extract_fixtures.py -v
```
Expected: all PASS.

- [ ] **Step 6: Implement the CLI main function**

Add to `scripts/extract_fixtures.py`:

```python
def parse_extraction_args(argv=None):
    """Parse extract_fixtures-specific CLI args."""
    if argv is None:
        argv = sys.argv[1:]

    app_id = None
    turns = []
    action_type = "generate_action"
    role = "problem"
    description = ""

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--turns" and i + 1 < len(argv):
            turns = [int(t.strip()) for t in argv[i + 1].split(",")]
            i += 2
        elif arg == "--action" and i + 1 < len(argv):
            action_type = argv[i + 1]
            i += 2
        elif arg == "--role" and i + 1 < len(argv):
            role = argv[i + 1]
            i += 2
        elif arg == "--description" and i + 1 < len(argv):
            description = argv[i + 1]
            i += 2
        elif not arg.startswith("-"):
            app_id = arg
            i += 1
        else:
            i += 1

    return app_id, turns, action_type, role, description


def main():
    app_id, turns, action_type, role, description = parse_extraction_args()

    if not app_id or not turns:
        print(
            "Usage: python3 scripts/extract_fixtures.py <app_id> "
            "--turns 37,42,45 --action generate_action --role problem "
            '--description "problem description"',
            file=sys.stderr,
        )
        sys.exit(1)

    if action_type not in ACTION_SCHEMA:
        print(f"Unknown action type: {action_type}", file=sys.stderr)
        print(f"Valid types: {', '.join(ACTION_SCHEMA.keys())}", file=sys.stderr)
        sys.exit(1)

    steps = fetch_steps(app_id)
    if not steps:
        print(f"No steps found for app_id={app_id}", file=sys.stderr)
        sys.exit(1)

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    created = []

    for turn in turns:
        state = find_action_step(steps, turn, action_type)
        if state is None:
            print(f"WARNING: Turn {turn} / {action_type} not found, skipping.", file=sys.stderr)
            continue

        fixture = build_fixture(state, action_type, turn, app_id, role, description)
        episode_id = fixture["meta"]["episode_id"]
        filename = f"{episode_id}_t{turn}_{action_type}.json"
        filepath = FIXTURES_DIR / filename
        filepath.write_text(json.dumps(fixture, indent=2, default=str))
        created.append(str(filepath))
        print(f"Extracted: {filepath}")

    if not created:
        print("ERROR: No fixtures extracted.", file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(created)} fixtures written to {FIXTURES_DIR}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run all tests**

```bash
uv run pytest tests/test_extract_fixtures.py -v
```
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/extract_fixtures.py tests/test_extract_fixtures.py
git commit -m "feat(validation): implement fixture extraction from Burr tracker"
```

---

### Task 3: Validation Script — Replay Engine

**Files:**
- Create: `scripts/validate_prompt.py`
- Test: `tests/test_validate_prompt.py`

This task implements Phase 1 (replay through real actions) and the structural checks.

- [ ] **Step 1: Write test for state deserialization and action dispatch**

```python
"""Tests for validate_prompt.py — replay and validation logic."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _make_fixture(action_type="generate_action", role="problem", **state_overrides):
    """Build a minimal fixture dict for testing."""
    base_state = {
        "formatted_context": "You are at the house.",
        "rejection_count": 0,
        "critic_justification": "",
        "knowledge_base": "",
        "turn_count": 5,
    }
    base_state.update(state_overrides)
    return {
        "meta": {
            "app_id": "test",
            "episode_id": "ep01",
            "turn": 5,
            "extracted_at": "2026-04-04T00:00:00Z",
            "role": role,
            "problem_description": "Agent did something bad" if role == "problem" else "",
        },
        "action_type": action_type,
        "state": base_state,
        "original_output": {
            "proposed_action": "examine mailbox",
            "agent_reasoning": "check the mailbox",
            "next_steps": "",
            "new_objective": "",
        },
    }


def test_replay_generate_action():
    from validate_prompt import replay_fixture
    from zorkburr.llm.models import AgentResponse

    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="I should go north", action="north", next_steps="", new_objective=""
    )
    mock_config = MagicMock(
        agent_model="test", default_temperature=1.0, default_max_tokens=4096,
        use_local_models=False,
    )

    fixture = _make_fixture()
    new_output = replay_fixture(fixture, client=mock_client, config=mock_config)

    assert new_output is not None
    assert new_output["proposed_action"] == "north"
    assert "go north" in new_output["agent_reasoning"]


def test_structural_check_problem_action_changed():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "go north", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is True


def test_structural_check_problem_action_same():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="problem")
    # Same action as original — structural fail for problem fixtures
    new_output = {"proposed_action": "examine mailbox", "agent_reasoning": "check", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is False


def test_structural_check_healthy_allows_same_action():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="healthy")
    new_output = {"proposed_action": "examine mailbox", "agent_reasoning": "check", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is True


def test_structural_check_fallback_fails():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="healthy")
    new_output = {"proposed_action": "look", "agent_reasoning": "LLM error: timeout", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_validate_prompt.py -v
```
Expected: FAIL — `validate_prompt` module not found.

- [ ] **Step 3: Implement replay_fixture and structural_check**

Create `scripts/validate_prompt.py`:

```python
"""Validate prompt changes against recorded game fixtures.

Usage:
  python3 scripts/validate_prompt.py tests/fixtures/ep42_*.json
"""
import json
import sys
import time
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.client import create_llm_client


# Action imports — lazy to avoid import errors when testing individual functions
def _get_action_runner(action_type):
    """Import and return the .run() method for an action type."""
    if action_type == "generate_action":
        from zorkburr.actions.agent import generate_action
        return generate_action.run
    elif action_type == "evaluate_action":
        from zorkburr.actions.critic import evaluate_action
        return evaluate_action.run
    elif action_type == "record_memory":
        from zorkburr.actions.memory import record_memory
        return record_memory.run
    elif action_type == "update_knowledge":
        from zorkburr.actions.knowledge import update_knowledge
        return update_knowledge.run
    elif action_type == "extract_info":
        from zorkburr.actions.extract import extract_info
        return extract_info.run
    elif action_type == "update_objectives":
        from zorkburr.actions.objectives import update_objectives
        return update_objectives.run
    elif action_type == "check_objective_completion":
        from zorkburr.actions.objectives import check_objective_completion
        return check_objective_completion.run
    else:
        raise ValueError(f"Unknown action type: {action_type}")


def _build_action_kwargs(action_type, client, config):
    """Build the keyword arguments for an action's .run() method."""
    if action_type == "generate_action":
        return {"client": client, "config": config, "use_thinking": False}
    elif action_type == "evaluate_action":
        # Mock Jericho — auto-pass object tree validation
        from unittest.mock import MagicMock
        mock_jericho = MagicMock()
        mock_jericho.get_visible_objects.return_value = []
        mock_jericho.get_inventory.return_value = []
        return {"llm": client, "jericho": mock_jericho, "config": config}
    elif action_type == "record_memory":
        return {"client": client, "config": config}
    elif action_type == "update_knowledge":
        return {"client": client, "config": config, "use_thinking": False}
    elif action_type == "extract_info":
        from unittest.mock import MagicMock
        mock_jericho = MagicMock()
        mock_jericho.get_visible_objects.return_value = []
        mock_jericho.get_valid_exits.return_value = []
        return {"client": client, "jericho": mock_jericho, "config": config}
    elif action_type in ("update_objectives", "check_objective_completion"):
        return {"client": client, "config": config}
    else:
        return {"client": client, "config": config}


# Import ACTION_SCHEMA from extract_fixtures
from extract_fixtures import ACTION_SCHEMA


def replay_fixture(fixture, client, config):
    """Replay a fixture through the actual action with a live LLM client.

    Returns a dict of the action's output keys, or None on error.
    """
    action_type = fixture["action_type"]
    schema = ACTION_SCHEMA[action_type]

    # Build Burr State from fixture
    state = State(fixture["state"])

    # Get the action runner and kwargs
    runner = _get_action_runner(action_type)
    kwargs = _build_action_kwargs(action_type, client, config)

    try:
        result, new_state = runner(state, **kwargs)
        # Extract output keys from the new state
        output = {}
        for key in schema["output_keys"]:
            output[key] = new_state[key] if key in new_state else None
        return output
    except Exception as e:
        return {"_error": str(e)}


def structural_check(fixture, new_output):
    """Run deterministic structural checks on the new output.

    Returns {"passed": bool, "detail": str}.
    """
    action_type = fixture["action_type"]
    role = fixture["meta"]["role"]
    original = fixture["original_output"]

    # Check for LLM error / fallback
    if new_output.get("_error"):
        return {"passed": False, "detail": f"Replay error: {new_output['_error']}"}

    if action_type == "generate_action":
        proposed = new_output.get("proposed_action", "")
        reasoning = new_output.get("agent_reasoning", "")

        # Fallback detection
        if proposed == "look" and "error" in reasoning.lower():
            return {"passed": False, "detail": "Fallback to 'look' due to LLM error"}
        if not proposed:
            return {"passed": False, "detail": "Empty proposed action"}

        # Problem fixtures: action must differ from original
        if role == "problem" and proposed == original.get("proposed_action"):
            return {
                "passed": False,
                "detail": f"Action unchanged from original: '{proposed}'",
            }

        return {"passed": True, "detail": f"Action: '{proposed}'"}

    elif action_type == "evaluate_action":
        score = new_output.get("critic_score")
        if score is None or not isinstance(score, (int, float)):
            return {"passed": False, "detail": "Invalid critic score"}

        if role == "problem":
            orig_score = original.get("critic_score", 0)
            if isinstance(orig_score, (int, float)) and score <= orig_score:
                return {
                    "passed": False,
                    "detail": f"Critic score did not improve: {orig_score} -> {score}",
                }

        return {"passed": True, "detail": f"Critic score: {score:.2f}"}

    elif action_type == "record_memory":
        mbl = new_output.get("memories_by_location", {})
        if role == "problem" and not any(mbl.values()):
            return {"passed": False, "detail": "No memories produced"}
        return {"passed": True, "detail": "Memory output present"}

    elif action_type == "update_knowledge":
        kb = new_output.get("knowledge_base", "")
        if not kb:
            return {"passed": False, "detail": "Empty knowledge base output"}
        return {"passed": True, "detail": f"KB: {len(kb)} chars"}

    elif action_type == "extract_info":
        return {"passed": True, "detail": "Extract info completed"}

    elif action_type in ("update_objectives", "check_objective_completion"):
        return {"passed": True, "detail": "Objectives step completed"}

    return {"passed": True, "detail": "No structural checks for this action type"}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_validate_prompt.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_prompt.py tests/test_validate_prompt.py
git commit -m "feat(validation): implement replay engine and structural checks"
```

---

### Task 4: Validation Script — LLM Judge

**Files:**
- Modify: `scripts/validate_prompt.py`
- Modify: `tests/test_validate_prompt.py`

- [ ] **Step 1: Write test for LLM judge**

Add to `tests/test_validate_prompt.py`:

```python
def test_judge_problem_pass():
    from validate_prompt import judge_fixture

    mock_client = MagicMock()
    # Simulate a raw completion response (judge uses raw client, not instructor)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "PASS: The new output addresses the memory issue."
    mock_client.client.chat.completions.create.return_value = mock_response

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "I recall this area", "next_steps": "", "new_objective": ""}
    mock_config = MagicMock(analysis_model="test", use_local_models=False, local_model="test", llm_request_timeout=60)

    result = judge_fixture(fixture, new_output, client=mock_client, config=mock_config)
    assert result["passed"] is True


def test_judge_problem_fail():
    from validate_prompt import judge_fixture

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "FAIL: The agent still ignores location memories."
    mock_client.client.chat.completions.create.return_value = mock_response

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "go north", "next_steps": "", "new_objective": ""}
    mock_config = MagicMock(analysis_model="test", use_local_models=False, local_model="test", llm_request_timeout=60)

    result = judge_fixture(fixture, new_output, client=mock_client, config=mock_config)
    assert result["passed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_validate_prompt.py::test_judge_problem_pass -v
```
Expected: FAIL — `judge_fixture` not found.

- [ ] **Step 3: Implement judge_fixture**

Add to `scripts/validate_prompt.py`, before the `structural_check` function:

```python
from zorkburr.llm.client import effective_model, thinking_kwargs


JUDGE_SYSTEM_PROMPT = """\
You are evaluating whether a prompt change improved an AI game agent's output.

You will be given:
- PROBLEM DESCRIPTION: What was wrong with the original output
- ORIGINAL OUTPUT: What the agent produced before the prompt change
- NEW OUTPUT: What the agent produced after the prompt change
- ROLE: "problem" (this turn was broken and should improve) or "healthy" (this turn was fine and should not degrade)

For PROBLEM turns: Did the new output address the diagnosed problem? Is it meaningfully better?
For HEALTHY turns: Is the new output at least as good as the original? Did quality degrade?

Respond with exactly one line starting with PASS or FAIL, followed by a colon and a brief justification (one sentence).
Examples:
  PASS: The new output references location memories and avoids redundant exploration.
  FAIL: The agent still ignores available memories despite the prompt change.
"""


def judge_fixture(fixture, new_output, client, config):
    """Use an LLM to judge whether the new output is better than the original.

    Returns {"passed": bool, "detail": str}.
    """
    meta = fixture["meta"]
    original = fixture["original_output"]

    user_msg = (
        f"ROLE: {meta['role']}\n\n"
        f"PROBLEM DESCRIPTION: {meta.get('problem_description', 'N/A')}\n\n"
        f"ORIGINAL OUTPUT:\n{json.dumps(original, indent=2, default=str)}\n\n"
        f"NEW OUTPUT:\n{json.dumps(new_output, indent=2, default=str)}"
    )

    try:
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=effective_model(config, config.analysis_model),
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=128,
            timeout=config.llm_request_timeout,
            **thinking_kwargs(config, False),
        )
        verdict = (response.choices[0].message.content or "").strip()
        passed = verdict.upper().startswith("PASS")
        return {"passed": passed, "detail": verdict}
    except Exception as e:
        return {"passed": False, "detail": f"Judge error: {e}"}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_validate_prompt.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_prompt.py tests/test_validate_prompt.py
git commit -m "feat(validation): implement LLM judge for fixture evaluation"
```

---

### Task 5: Validation Script — CLI Runner and Output

**Files:**
- Modify: `scripts/validate_prompt.py`

- [ ] **Step 1: Implement the CLI main function**

Add to `scripts/validate_prompt.py`:

```python
def validate_fixtures(fixture_paths, client, config):
    """Run full validation (replay + structural + judge) on a list of fixtures.

    Returns (results_list, all_passed).
    """
    results = []

    for path in fixture_paths:
        fixture = json.loads(Path(path).read_text())
        meta = fixture["meta"]
        action_type = fixture["action_type"]
        label = f"{meta['episode_id']}_t{meta['turn']}_{action_type}"
        role = meta["role"].upper()

        print(f"\nFIXTURE {Path(path).name} [{role}]")

        # Phase 1: Replay
        start = time.time()
        print(f"  Replaying {label}...", end=" ", flush=True)
        new_output = replay_fixture(fixture, client, config)
        elapsed = time.time() - start
        print(f"done ({elapsed:.1f}s)")

        if new_output.get("_error"):
            print(f"  Replay: FAILED — {new_output['_error']}")
            results.append({"fixture": path, "role": role, "passed": False, "detail": new_output["_error"]})
            continue

        # Phase 2a: Structural check
        struct = structural_check(fixture, new_output)
        status = "PASS" if struct["passed"] else "FAIL"
        print(f"  Structural: {status} ({struct['detail']})")

        if not struct["passed"]:
            results.append({"fixture": path, "role": role, "passed": False, "detail": f"Structural: {struct['detail']}"})
            continue

        # Phase 2b: LLM judge
        print(f"  Judging...", end=" ", flush=True)
        start = time.time()
        judge = judge_fixture(fixture, new_output, client, config)
        elapsed = time.time() - start
        status = "PASS" if judge["passed"] else "FAIL"
        print(f"{status} ({elapsed:.1f}s)")
        print(f"  Judge: {judge['detail']}")

        results.append({"fixture": path, "role": role, "passed": judge["passed"], "detail": judge["detail"]})

    return results


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 scripts/validate_prompt.py tests/fixtures/ep42_*.json",
            file=sys.stderr,
        )
        sys.exit(1)

    fixture_paths = sys.argv[1:]

    # Verify all fixture files exist
    for p in fixture_paths:
        if not Path(p).exists():
            print(f"ERROR: Fixture not found: {p}", file=sys.stderr)
            sys.exit(1)

    config = GameConfig()
    client = create_llm_client(config)

    print(f"Validating {len(fixture_paths)} fixtures...")
    results = validate_fixtures(fixture_paths, client, config)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = [r for r in results if not r["passed"]]

    print(f"\nRESULT: {passed}/{total} PASSED", end="")
    if failed:
        print(f", {len(failed)} FAILED — validation BLOCKED")
        for r in failed:
            print(f"  FAILED: {Path(r['fixture']).name} [{r['role']}] — {r['detail']}")
        sys.exit(1)
    else:
        print(" — validation successful")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

```bash
uv run pytest tests/test_validate_prompt.py tests/test_extract_fixtures.py -v
```
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_prompt.py
git commit -m "feat(validation): add CLI runner with summary output and exit codes"
```

---

### Task 6: Orchestrator Integration

**Files:**
- Modify: `.claude/commands/zork-orchestrator.md`

This task adds the three orchestrator changes: fixture extraction step, validation requirement in subagent brief, and review checklist row.

- [ ] **Step 1: Read the current orchestrator file to identify exact insertion points**

Read `.claude/commands/zork-orchestrator.md` and locate:
1. Phase 3 step 2 ("Identify the specific problem") — new step 2.5 goes after it
2. Phase 3 step 3 subagent brief — validation requirement appended to the brief
3. Phase 3 step 5 review checklist table — new row added

- [ ] **Step 2: Add Phase 3 step 2.5 — Extract Fixtures**

Insert after the Phase 3 step 2 block (after the `burr_turn.py` usage) and before step 3. Add this text:

```markdown
2.5. **Extract validation fixtures** — Before dispatching the subagent, extract turn state for the problematic turns plus 2-3 healthy turns. Select the action type based on which prompt needs changing:

   | Prompt file | Action to extract |
   |---|---|
   | `agent.md` | `generate_action` |
   | `critic.md` | `evaluate_action` |
   | `memory_synthesis.md` | `record_memory` |
   | `knowledge.md` | `update_knowledge` |
   | `extractor.md` | `extract_info` |
   | `objective_discovery.md` | `update_objectives` |
   | `objective_completion.md` | `check_objective_completion` |

   ```bash
   # Problem turns (3-5 from your diagnosis — the specific turns exhibiting the problem)
   python3 scripts/extract_fixtures.py {app_id} --turns {problem_turns} \
     --action {action_type} --role problem \
     --description "{one-line problem description}"

   # Healthy turns (2-3 turns with critic score > 0.6 and zero rejections)
   python3 scripts/extract_fixtures.py {app_id} --turns {healthy_turns} \
     --action {action_type} --role healthy
   ```

   Verify extraction succeeded (fixture files printed to stdout). If Burr tracker is down or turns are missing, you MUST get fixtures before dispatching — restart Burr or use a different episode's data.

   **Fixture cleanup:** Before extracting, remove fixtures from old episodes:
   ```bash
   find tests/fixtures -name "*.json" -mtime +7 -delete 2>/dev/null
   ```
```

- [ ] **Step 3: Append validation requirement to the subagent brief**

In Phase 3 step 3, after the existing brief text (after `Return a 2-3 sentence summary...`) but still inside the brief template, add:

```markdown

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
     full validation output so the orchestrator can reassess the diagnosis.
   - Do NOT skip validation. Do NOT commit with failures.
   - Include the validation output summary in your journal IMPROVEMENT entry
     as a new field:
       **Validation:** PASSED (5/5) or FAILED (3/5) — <details>
```

- [ ] **Step 4: Add validation row to the review checklist**

In Phase 3 step 5, add a new row to the review checklist table:

```markdown
   | Validation passed | `validate_prompt.py` exited 0 and journal entry shows **Validation: PASSED**. If validation missing or failed → revert and re-dispatch. |
```

- [ ] **Step 5: Verify the orchestrator file is well-formed**

Read through the modified sections to ensure markdown formatting is correct, no broken tables, and the new content flows logically.

- [ ] **Step 6: Commit**

```bash
git add .claude/commands/zork-orchestrator.md
git commit -m "feat(orchestrator): require fixture validation before committing prompt changes"
```

---

### Task 7: Integration Smoke Test

**Files:**
- None (manual verification)

- [ ] **Step 1: Verify extract_fixtures.py runs without import errors**

```bash
uv run python3 scripts/extract_fixtures.py --help 2>&1 || true
```
Expected: prints usage message (Burr not needed for this check).

- [ ] **Step 2: Verify validate_prompt.py runs without import errors**

```bash
uv run python3 scripts/validate_prompt.py 2>&1 || true
```
Expected: prints usage message.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest tests/test_extract_fixtures.py tests/test_validate_prompt.py -v
```
Expected: all PASS.

- [ ] **Step 4: Verify .gitkeep exists**

```bash
ls tests/fixtures/.gitkeep
```
Expected: file exists.

- [ ] **Step 5: Run a dry-run extraction against a live Burr instance (if available)**

Only if Burr tracker is running with recent episode data:
```bash
# List recent apps
curl -s 'http://localhost:7241/api/v0/default/__none__/apps?limit=1' | python3 -m json.tool
# Extract a single fixture
python3 scripts/extract_fixtures.py {app_id_from_above} --turns 1 --action generate_action --role healthy
# Check the output
cat tests/fixtures/*.json | python3 -m json.tool | head -20
```
Expected: valid JSON fixture with populated state keys.

- [ ] **Step 6: Final commit if any fixups were needed**

```bash
git add -A
git status
# Only commit if there are changes
git diff --cached --quiet || git commit -m "fix(validation): integration smoke test fixups"
```
