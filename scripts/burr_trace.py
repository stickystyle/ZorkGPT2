"""Turn-by-turn trace of a Burr app — aggregates steps into compact per-turn summaries."""
import sys

from _args import parse_args, fetch_steps, get_state, get_action, in_turn_range, trunc


def _format_score(pre, post):
    """Format score with delta."""
    delta = post - pre
    if delta > 0:
        return f"{pre}\u2192{post} (+{delta})"
    elif delta < 0:
        return f"{pre}\u2192{post} ({delta})"
    return f"{post}"


def _format_location(pre_name, post_name, pre_id, post_id):
    """Format location change."""
    if pre_id == post_id or pre_name == post_name:
        return f"{post_name} (STAYED)"
    return f"{pre_name} \u2192 {post_name}"


def _format_inventory(inv_list):
    """Format inventory list, truncated to 80 chars."""
    if not inv_list:
        return "(empty)"
    text = ", ".join(str(item) for item in inv_list)
    if len(text) > 80:
        return text[:77] + "..."
    return text


def build_turns(steps):
    """Walk all steps, group by turn_count using execute_action as anchor.

    Returns dict: turn_number -> {exec_state, extract_state, eval_state}.
    """
    turns = {}

    for i, step in enumerate(steps):
        action = get_action(step)
        state = get_state(step)
        if not state:
            continue
        tc = state.get("turn_count")
        if tc is None:
            continue

        if tc not in turns:
            turns[tc] = {"exec_state": None, "extract_state": None, "eval_states": []}

        if action == "execute_action":
            turns[tc]["exec_state"] = state
        elif action == "extract_info":
            turns[tc]["extract_state"] = state
        elif action == "evaluate_action":
            turns[tc]["eval_states"].append(state)

    return turns


def show_turn(tc, turn_data, verbose):
    """Print a compact summary for one turn."""
    state = turn_data["exec_state"]
    if not state:
        return

    # Action
    action = state.get("action_to_take", "?")

    # Score
    pre_score = state.get("pre_score", 0)
    post_score = state.get("score", 0)
    score_str = _format_score(pre_score, post_score)

    # Location
    pre_loc_name = state.get("pre_location_name", "?")
    post_loc_name = state.get("location_name", "?")
    pre_loc_id = state.get("pre_location_id", 0)
    post_loc_id = state.get("location_id", 0)
    loc_str = _format_location(pre_loc_name, post_loc_name, pre_loc_id, post_loc_id)

    print(f"  T{tc}: {action} | Score: {score_str} | {loc_str}")

    # Game response
    game_resp = state.get("game_response", "")
    if game_resp:
        clean = " ".join(game_resp.strip().split())
        print(f"    Game: \"{trunc(clean, 150)}\"")

    # Critic info — read from execute_action state (persists from evaluate_action)
    critic_score = state.get("critic_score")
    critic_conf = state.get("critic_confidence")
    rejection_count = state.get("rejection_count", 0)
    stagnant = state.get("turns_since_progress", 0)

    # But rejection_count gets reset by record_results, so look at eval_states
    # for the actual rejection count seen during this turn's evaluation
    eval_states = turn_data.get("eval_states", [])
    if eval_states:
        # Use the last evaluate_action's rejection_count (highest for this turn)
        rejection_count = max(s.get("rejection_count", 0) for s in eval_states)
        # Also prefer critic data from eval if available
        last_eval = eval_states[-1]
        if critic_score is None:
            critic_score = last_eval.get("critic_score")
        if critic_conf is None:
            critic_conf = last_eval.get("critic_confidence")

    critic_parts = []
    if critic_score is not None:
        critic_parts.append(f"{critic_score:.2f}")
    else:
        critic_parts.append("?")
    if critic_conf is not None:
        critic_parts.append(f"conf={critic_conf:.2f}")
    critic_str = " ".join(critic_parts)

    print(f"    Critic: {critic_str} | Rej: {rejection_count} | Stagnant: {stagnant} turns")

    # Inventory
    inv = state.get("inventory", [])
    print(f"    Inventory: {_format_inventory(inv)}")

    # Verbose extras
    if verbose:
        ext_state = turn_data.get("extract_state") or state
        exits = ext_state.get("exits", [])
        exit_names = [e if isinstance(e, str) else str(e) for e in exits]
        objects = ext_state.get("visible_objects", [])
        obj_names = [o["name"] if isinstance(o, dict) else str(o) for o in objects]
        combat = ext_state.get("in_combat", False)
        print(
            f"    Exits: {', '.join(exit_names) if exit_names else '(none)'}"
            f" | Objects: {', '.join(obj_names) if obj_names else '(none)'}"
            f" | Combat: {'yes' if combat else 'no'}"
        )

        overridden = state.get("was_overridden", False)
        new_obj = state.get("new_objective", "")
        print(
            f"    Pre: {pre_loc_name} (score {pre_score})"
            f" | Override: {'yes' if overridden else 'no'}"
            f" | New obj: {new_obj if new_obj else '(none)'}"
        )


def main():
    args = parse_args()
    app_id = args["app_id"]
    verbose = args["verbose"]
    turns_filter = args["turns"]

    if not app_id:
        print(
            "Usage: python3 scripts/burr_trace.py <app_id> [--turns START-END] [--verbose]",
            file=sys.stderr,
        )
        sys.exit(1)

    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.", file=sys.stderr)
        sys.exit(1)

    turns = build_turns(steps)
    if not turns:
        print("No turns found.", file=sys.stderr)
        sys.exit(1)

    # Filter turns
    sorted_tcs = sorted(turns.keys())
    if turns_filter:
        sorted_tcs = [tc for tc in sorted_tcs if in_turn_range(tc, turns_filter)]

    # Header
    total_turns = max(turns.keys()) if turns else 0
    range_label = f"turns {turns_filter[0]}-{turns_filter[1]}" if turns_filter else "all turns"
    print(f"=== Trace ({range_label}) | {total_turns} total turns, {len(steps)} steps ===")
    print()

    for tc in sorted_tcs:
        show_turn(tc, turns[tc], verbose)
        print()


if __name__ == "__main__":
    main()
