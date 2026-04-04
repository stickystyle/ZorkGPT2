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


def format_comparison(fixture, new_output):
    """Format original vs new output for human/LLM review.

    Returns a readable string the calling subagent (Claude) can evaluate.
    """
    meta = fixture["meta"]
    original = fixture["original_output"]
    action_type = fixture["action_type"]

    lines = [
        f"  Role: {meta['role'].upper()}",
    ]
    if meta.get("problem_description"):
        lines.append(f"  Problem: {meta['problem_description']}")

    # Show the most relevant fields based on action type
    if action_type == "generate_action":
        lines.append(f"  Original action: {original.get('proposed_action', '?')}")
        lines.append(f"  New action:      {new_output.get('proposed_action', '?')}")
        orig_reason = (original.get("agent_reasoning") or "")[:300]
        new_reason = (new_output.get("agent_reasoning") or "")[:300]
        lines.append(f"  Original reasoning: {orig_reason}")
        lines.append(f"  New reasoning:      {new_reason}")
    elif action_type == "evaluate_action":
        lines.append(f"  Original score: {original.get('critic_score', '?')}")
        lines.append(f"  New score:      {new_output.get('critic_score', '?')}")
        lines.append(f"  Original justification: {(original.get('critic_justification') or '')[:200]}")
        lines.append(f"  New justification:      {(new_output.get('critic_justification') or '')[:200]}")
    elif action_type == "record_memory":
        lines.append(f"  Original memories: {json.dumps(original.get('memories_by_location', {}), default=str)[:300]}")
        lines.append(f"  New memories:      {json.dumps(new_output.get('memories_by_location', {}), default=str)[:300]}")
    elif action_type == "update_knowledge":
        orig_kb = (original.get("knowledge_base") or "")[:300]
        new_kb = (new_output.get("knowledge_base") or "")[:300]
        lines.append(f"  Original KB ({len(original.get('knowledge_base', ''))} chars): {orig_kb}")
        lines.append(f"  New KB ({len(new_output.get('knowledge_base', ''))} chars):      {new_kb}")
    else:
        lines.append(f"  Original: {json.dumps(original, default=str)[:300]}")
        lines.append(f"  New:      {json.dumps(new_output, default=str)[:300]}")

    return "\n".join(lines)


def validate_fixtures(fixture_paths, client, config):
    """Run replay + structural check on all fixtures, print comparison output.

    Returns (results_list, all_structural_passed).
    """
    results = []

    for path in fixture_paths:
        fixture = json.loads(Path(path).read_text())
        meta = fixture["meta"]
        action_type = fixture["action_type"]
        role = meta["role"].upper()

        print(f"\nFIXTURE {Path(path).name} [{role}]")

        # Phase 1: Replay
        start = time.time()
        print(f"  Replaying {meta['episode_id']}_t{meta['turn']} {action_type}...", end=" ", flush=True)
        new_output = replay_fixture(fixture, client, config)
        elapsed = time.time() - start
        print(f"done ({elapsed:.1f}s)")

        if new_output.get("_error"):
            print(f"  Replay: FAILED — {new_output['_error']}")
            results.append({"fixture": path, "role": role, "structural_passed": False, "detail": new_output["_error"]})
            continue

        # Phase 2: Structural check
        struct = structural_check(fixture, new_output)
        status = "PASS" if struct["passed"] else "FAIL"
        print(f"  Structural: {status} ({struct['detail']})")

        # Phase 3: Comparison output for subagent evaluation
        comparison = format_comparison(fixture, new_output)
        print(f"  Comparison:\n{comparison}")

        results.append({
            "fixture": path,
            "role": role,
            "structural_passed": struct["passed"],
            "detail": struct["detail"],
        })

    return results


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 scripts/validate_prompt.py tests/fixtures/ep42_*.json",
            file=sys.stderr,
        )
        sys.exit(1)

    fixture_paths = sys.argv[1:]

    for p in fixture_paths:
        if not Path(p).exists():
            print(f"ERROR: Fixture not found: {p}", file=sys.stderr)
            sys.exit(1)

    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client

    config = GameConfig()
    client = create_llm_client(config)

    print(f"Validating {len(fixture_paths)} fixtures...")
    results = validate_fixtures(fixture_paths, client, config)

    # Summary
    struct_passed = sum(1 for r in results if r["structural_passed"])
    total = len(results)
    failed = [r for r in results if not r["structural_passed"]]

    print(f"\nSTRUCTURAL RESULTS: {struct_passed}/{total} passed", end="")
    if failed:
        print(f", {len(failed)} FAILED")
        for r in failed:
            print(f"  FAILED: {Path(r['fixture']).name} [{r['role']}] — {r['detail']}")
        sys.exit(1)
    else:
        print(" — all structural checks passed")
        print("\nReview the comparison output above to judge whether the prompt change")
        print("genuinely addresses the diagnosed problem and doesn't degrade healthy turns.")
        sys.exit(0)


if __name__ == "__main__":
    main()
