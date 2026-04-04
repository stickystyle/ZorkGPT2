"""Validate prompt changes against recorded game fixtures.

Usage:
  python3 scripts/validate_prompt.py tests/fixtures/ep42_*.json
"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add project root and scripts dir to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from burr.core import State
from extract_fixtures import ACTION_SCHEMA
from zorkburr.llm.client import effective_model, thinking_kwargs


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
        mock_jericho = MagicMock()
        mock_jericho.get_visible_objects.return_value = []
        mock_jericho.get_inventory.return_value = []
        return {"llm": client, "jericho": mock_jericho, "config": config}
    elif action_type == "extract_info":
        mock_jericho = MagicMock()
        mock_jericho.get_visible_objects.return_value = []
        mock_jericho.get_valid_exits.return_value = []
        return {"client": client, "jericho": mock_jericho, "config": config}
    elif action_type in ("update_knowledge", "update_objectives"):
        return {"client": client, "config": config, "use_thinking": False}
    else:
        return {"client": client, "config": config}


def replay_fixture(fixture, client, config):
    """Replay a fixture through the actual action with a live LLM client.

    Returns a dict of the action's output keys, or a dict with _error key on failure.
    """
    action_type = fixture["action_type"]
    schema = ACTION_SCHEMA[action_type]

    state = State(fixture["state"])
    runner = _get_action_runner(action_type)
    kwargs = _build_action_kwargs(action_type, client, config)

    try:
        result, new_state = runner(state, **kwargs)
        output = {}
        for key in schema["output_keys"]:
            output[key] = new_state[key] if key in new_state else None
        return output
    except Exception as e:
        return {"_error": str(e)}


def structural_check(fixture, new_output):
    """Run deterministic structural checks on the replayed output.

    Returns {"passed": bool, "detail": str}.
    """
    action_type = fixture["action_type"]
    role = fixture["meta"]["role"]
    original = fixture["original_output"]

    if new_output.get("_error"):
        return {"passed": False, "detail": f"Replay error: {new_output['_error']}"}

    if action_type == "generate_action":
        proposed = new_output.get("proposed_action", "")
        reasoning = new_output.get("agent_reasoning", "")

        if not proposed:
            return {"passed": False, "detail": "Empty proposed action"}
        if proposed == "look" and "error" in reasoning.lower():
            return {"passed": False, "detail": "Fallback to 'look' due to LLM error"}
        if role == "problem" and proposed == original.get("proposed_action"):
            return {"passed": False, "detail": f"Action unchanged from original: '{proposed}'"}
        return {"passed": True, "detail": f"Action: '{proposed}'"}

    elif action_type == "evaluate_action":
        score = new_output.get("critic_score")
        if score is None or not isinstance(score, (int, float)):
            return {"passed": False, "detail": "Invalid critic score"}
        if role == "problem":
            orig_score = original.get("critic_score", 0)
            if isinstance(orig_score, (int, float)) and score <= orig_score:
                return {"passed": False, "detail": f"Critic score did not improve: {orig_score} -> {score}"}
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
