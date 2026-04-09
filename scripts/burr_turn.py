"""Complete single-turn pipeline inspection — shows every Burr step for one turn with all state fields."""
import sys

from _args import parse_args, fetch_steps, get_state, get_action, trunc


def find_turn_steps(steps, target_turn):
    """Find all steps belonging to a specific turn.

    The tricky part: turn_count is incremented by execute_action, so steps
    BEFORE execute_action (assemble_context, generate_action, evaluate_action)
    still have the PREVIOUS turn's count.

    Approach: find the execute_action step where turn_count == target_turn,
    then walk backwards to find the assemble_context that started this turn,
    and forwards to find the last step before the next assemble_context.
    """
    # Find the execute_action step for this turn
    exec_idx = None
    for i, s in enumerate(steps):
        if get_action(s) == "execute_action" and get_state(s).get("turn_count") == target_turn:
            exec_idx = i
            break

    if exec_idx is None:
        return []

    # Walk backwards from execute_action to find the assemble_context that started this turn
    start_idx = exec_idx
    for i in range(exec_idx - 1, -1, -1):
        action = get_action(steps[i])
        if action == "assemble_context":
            start_idx = i
            break
        elif action in ("generate_action", "evaluate_action"):
            start_idx = i
        else:
            # Hit a step from the previous turn's post-execute pipeline
            break

    # Walk forwards from execute_action to find the end of this turn
    end_idx = exec_idx
    for i in range(exec_idx + 1, len(steps)):
        action = get_action(steps[i])
        if action == "assemble_context":
            # This is the start of the NEXT turn
            break
        end_idx = i

    return steps[start_idx : end_idx + 1]


def diff_memories(prev_mbl, curr_mbl):
    """Diff memories_by_location dicts, return list of (location, new_memories)."""
    results = []
    for loc, mems in curr_mbl.items():
        prev_mems = prev_mbl.get(loc, [])
        if len(mems) > len(prev_mems):
            new_mems = mems[len(prev_mems):]
            results.append((loc, new_mems))
    return results


def diff_objectives(prev_list, curr_list):
    """Return newly added items."""
    prev_set = set(str(o) for o in prev_list)
    return [o for o in curr_list if str(o) not in prev_set]


def diff_inventory(prev_inv, curr_inv):
    """Return (added, removed) item lists."""
    prev_set = set(prev_inv) if prev_inv else set()
    curr_set = set(curr_inv) if curr_inv else set()
    return sorted(curr_set - prev_set), sorted(prev_set - curr_set)


def format_location_change(pre_loc, post_loc, pre_id, post_id):
    """Format location change string."""
    if pre_id == post_id:
        return f"{post_loc} (STAYED)"
    return f"{pre_loc} -> {post_loc} (MOVED)"


def show_step(idx, step, prev_state, full):
    """Display a single pipeline step with relevant state fields."""
    action = get_action(step)
    state = get_state(step)

    if not state:
        print(f"\n[{idx}] {action}")
        print("  (no state — step may be in-progress or crashed)")
        return

    print(f"\n[{idx}] {action}")

    if action == "assemble_context":
        ctx = state.get("formatted_context", "")
        if full:
            print(f"  Context ({len(ctx)} chars):")
            for line in ctx.splitlines():
                print(f"    {line}")
        else:
            print(f"  Context: {len(ctx)} chars")

    elif action == "generate_action":
        proposed = state.get("proposed_action", "")
        reasoning = state.get("agent_reasoning", "")
        next_steps = state.get("next_steps", "")
        new_obj = state.get("new_objective", "")
        print(f"  Proposed: \"{proposed}\"")
        print(f"  Reasoning: \"{trunc(reasoning, 500, full)}\"")
        if next_steps:
            print(f"  Next steps: \"{trunc(next_steps, 500, full)}\"")
        print(f"  New objective: {new_obj if new_obj else '(none)'}")

    elif action == "evaluate_action":
        score = state.get("critic_score", 0)
        confidence = state.get("critic_confidence", 0)
        justification = state.get("critic_justification", "")
        rejections = state.get("rejection_count", 0)
        overridden = state.get("was_overridden", False)
        # Determine if accepted or rejected: if there's a subsequent generate_action
        # before execute_action, this was a rejection. We show the current state.
        status = "OVERRIDDEN" if overridden else "ACCEPTED" if rejections == 0 or True else "REJECTED"
        # Better heuristic: check if the NEXT step is generate_action (rejected) or execute_action (accepted)
        print(f"  Critic: {score:.2f} (confidence: {confidence:.2f}) | Rejections so far: {rejections}")
        print(f"  Justification: \"{trunc(justification, 500, full)}\"")
        if overridden:
            print(f"  Override: YES (max rejections reached)")

    elif action == "execute_action":
        action_taken = state.get("action_to_take", "")
        response = state.get("game_response", "")
        pre_score = state.get("pre_score", 0)
        post_score = state.get("score", 0)
        delta = post_score - pre_score
        pre_loc = state.get("pre_location_name", "")
        post_loc = state.get("location_name", "")
        pre_loc_id = state.get("pre_location_id", 0)
        post_loc_id = state.get("location_id", 0)
        pre_inv = state.get("pre_inventory", [])
        post_inv = state.get("inventory", [])
        added, removed = diff_inventory(pre_inv, post_inv)

        print(f"  Action: {action_taken}")
        print(f"  Game response: \"{response.strip()}\"")
        delta_str = f" (+{delta})" if delta > 0 else (f" ({delta})" if delta < 0 else "")
        print(f"  Score: {pre_score} -> {post_score}{delta_str}")
        print(f"  Location: {format_location_change(pre_loc, post_loc, pre_loc_id, post_loc_id)}")
        inv_str = f"{pre_inv} -> {post_inv}"
        if added:
            inv_str += f" (ADDED: {', '.join(added)})"
        if removed:
            inv_str += f" (REMOVED: {', '.join(removed)})"
        if not added and not removed:
            inv_str += " (unchanged)"
        print(f"  Inventory: {inv_str}")

    elif action == "record_results":
        tsp = state.get("turns_since_progress", 0)
        visited = state.get("visited_locations", [])
        print(f"  Turns since progress: {tsp}")
        print(f"  Visited locations: {len(visited)} total")

    elif action == "record_memory":
        ms = state.get("memory_stats", {})
        print(f"  Memory stats: {ms}")
        # Diff memories
        curr_mbl = state.get("memories_by_location", {})
        prev_mbl = prev_state.get("memories_by_location", {}) if prev_state else {}
        new_memories = diff_memories(prev_mbl, curr_mbl)
        if new_memories:
            for loc, mems in new_memories:
                for m in mems:
                    cat = m.get("category", "?")
                    title = m.get("title", "?")
                    loc_name = m.get("location_name", loc)
                    print(f"  New memory: [{cat}] \"{title}\" at {loc_name}")
        else:
            print("  (no new memories this turn)")

    elif action == "check_objective_completion":
        curr_disc = state.get("discovered_objectives", [])
        curr_comp = state.get("completed_objectives", [])
        prev_disc = prev_state.get("discovered_objectives", []) if prev_state else []
        prev_comp = prev_state.get("completed_objectives", []) if prev_state else []
        new_disc = diff_objectives(prev_disc, curr_disc)
        new_comp = diff_objectives(prev_comp, curr_comp)
        if new_disc:
            for o in new_disc:
                print(f"  New objective discovered: {o}")
        if new_comp:
            for o in new_comp:
                print(f"  Objective completed: {o}")
        if not new_disc and not new_comp:
            print("  (no objective changes)")

    elif action == "update_objectives":
        curr_disc = state.get("discovered_objectives", [])
        curr_comp = state.get("completed_objectives", [])
        prev_disc = prev_state.get("discovered_objectives", []) if prev_state else []
        prev_comp = prev_state.get("completed_objectives", []) if prev_state else []
        new_disc = diff_objectives(prev_disc, curr_disc)
        new_comp = diff_objectives(prev_comp, curr_comp)
        print(f"  Objectives: {len(curr_disc)} discovered, {len(curr_comp)} completed")
        if new_disc:
            for o in new_disc:
                print(f"  NEW: {o}")
        if new_comp:
            for o in new_comp:
                print(f"  COMPLETED: {o}")
        if not new_disc and not new_comp:
            print("  (no changes)")

    elif action == "update_knowledge":
        kb = state.get("knowledge_base", "")
        print(f"  Knowledge base: {len(kb)} chars")
        if full:
            for line in kb.splitlines():
                print(f"    {line}")

    else:
        print(f"  (unknown step type)")


def main():
    args = parse_args()
    app_id = args["app_id"]
    full = args["full"]

    if not app_id or not args["extra"]:
        print(
            "Usage: python3 scripts/burr_turn.py <app_id> <turn_number> [--full]",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        target_turn = int(args["extra"][0])
    except (ValueError, IndexError):
        print(
            "Usage: python3 scripts/burr_turn.py <app_id> <turn_number> [--full]",
            file=sys.stderr,
        )
        sys.exit(1)

    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.", file=sys.stderr)
        sys.exit(1)

    turn_steps = find_turn_steps(steps, target_turn)
    if not turn_steps:
        # Find max turn_count to give helpful error
        max_turn = 0
        for s in steps:
            tc = get_state(s).get("turn_count", 0)
            if isinstance(tc, int) and tc > max_turn:
                max_turn = tc
        print(
            f"Turn {target_turn} not found. Available turns: 1-{max_turn}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"=== Turn {target_turn} — Full Pipeline ===")

    prev_state = {}
    for i, step in enumerate(turn_steps, 1):
        show_step(i, step, prev_state, full)
        st = get_state(step)
        if st:
            prev_state = st


if __name__ == "__main__":
    main()
