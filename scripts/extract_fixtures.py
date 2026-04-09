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
            "inventory", "location_name", "rejection_count",
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

# Pre-execute action types — found by walking backwards from execute_action
_PRE_EXECUTE = {"assemble_context", "generate_action", "evaluate_action"}

# Post-execute action types — found by walking forwards from execute_action
_POST_EXECUTE = {
    "record_memory", "update_knowledge",
    "update_objectives", "check_objective_completion",
}

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def find_action_step(steps, target_turn, action_type):
    """Find the state snapshot for a given action at a given turn.

    Turn numbering: execute_action increments turn_count. Steps before
    execute_action (assemble_context, generate_action, evaluate_action) still
    hold the previous turn_count. So for target_turn=N we look for the
    execute_action step where turn_count==N, then walk backwards (pre-execute
    actions) or forwards (post-execute actions) to locate action_type.

    Returns the state dict, or None if not found.
    """
    # Find the index of the execute_action step that transitions INTO target_turn
    exec_index = None
    for i, step in enumerate(steps):
        if get_action(step) == "execute_action":
            state = get_state(step)
            if state.get("turn_count") == target_turn:
                exec_index = i
                break

    if exec_index is None:
        return None

    if action_type == "execute_action":
        return get_state(steps[exec_index])

    if action_type in _PRE_EXECUTE:
        # Walk backwards from exec_index to find the action
        for i in range(exec_index - 1, -1, -1):
            if get_action(steps[i]) == action_type:
                return get_state(steps[i])
        return None

    # Post-execute: walk forwards from exec_index
    for i in range(exec_index + 1, len(steps)):
        step = steps[i]
        if get_action(step) == action_type:
            return get_state(step)
        # Stop searching once we hit the next execute_action
        if get_action(step) == "execute_action":
            break

    return None


def build_fixture(state, action_type, turn, app_id, role, description=""):
    """Build a fixture dict from a Burr state snapshot.

    Uses ACTION_SCHEMA to select which state keys and output keys to capture.
    Returns a dict with keys: meta, action_type, state, original_output.
    """
    schema = ACTION_SCHEMA[action_type]
    captured_state = {k: state[k] for k in schema["state_keys"] if k in state}
    original_output = {k: state[k] for k in schema["output_keys"] if k in state}

    return {
        "meta": {
            "app_id": app_id,
            "episode_id": state.get("episode_id", ""),
            "turn": turn,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "problem_description": description,
        },
        "action_type": action_type,
        "state": captured_state,
        "original_output": original_output,
    }


def parse_extraction_args(argv=None):
    """Parse CLI args for the extraction script.

    Returns: (app_id, turns_list, action_type, role, description)
    """
    if argv is None:
        argv = sys.argv[1:]

    app_id = None
    turns_list = []
    action_type = None
    role = ""
    description = ""

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--turns" and i + 1 < len(argv):
            turns_list = [int(t.strip()) for t in argv[i + 1].split(",")]
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
            if app_id is None:
                app_id = arg
            i += 1
        else:
            i += 1  # skip unknown flags

    return app_id, turns_list, action_type, role, description


def main():
    app_id, turns_list, action_type, role, description = parse_extraction_args()

    if action_type not in ACTION_SCHEMA:
        print(
            f"Error: unknown action type {action_type!r}. "
            f"Valid options: {', '.join(sorted(ACTION_SCHEMA))}",
            file=sys.stderr,
        )
        sys.exit(1)

    steps = fetch_steps(app_id)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    extracted = []
    for turn in turns_list:
        state = find_action_step(steps, target_turn=turn, action_type=action_type)
        if state is None:
            print(f"Warning: no {action_type} found for turn {turn}", file=sys.stderr)
            continue

        fixture = build_fixture(
            state, action_type=action_type, turn=turn,
            app_id=app_id, role=role, description=description,
        )
        episode_id = fixture["meta"]["episode_id"] or app_id
        filename = f"{episode_id}_t{turn}_{action_type}.json"
        out_path = FIXTURES_DIR / filename
        out_path.write_text(json.dumps(fixture, indent=2))
        print(str(out_path))
        extracted.append(out_path)

    if not extracted:
        sys.exit(1)


if __name__ == "__main__":
    main()
