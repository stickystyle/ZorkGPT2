"""Score stagnation diagnosis: why score is stuck, what's been tried, what opportunities exist."""
import sys
from collections import Counter

from _args import parse_args, fetch_steps, get_state, get_action, last_state


def find_inventory_at_score_change(steps, target_turn):
    """Walk Burr steps to find inventory at (or just after) the target turn.

    Looks for execute_action steps where turn_count matches the target.
    Falls back to the closest step with valid state near that turn.
    """
    # First pass: look for execute_action at the target turn
    for step in steps:
        if get_action(step) != "execute_action":
            continue
        st = get_state(step)
        if not st:
            continue
        tc = st.get("turn_count")
        if tc == target_turn:
            return list(st.get("inventory", []))

    # Second pass: look for any step at the target turn
    for step in steps:
        st = get_state(step)
        if not st:
            continue
        tc = st.get("turn_count")
        if tc == target_turn:
            inv = st.get("inventory")
            if inv is not None:
                return list(inv)

    return None


def find_score_delta_at_turn(action_history, target_turn):
    """Find the score delta at the turn where score last changed."""
    for entry in action_history:
        turn = entry.get("turn")
        if turn == target_turn:
            before = entry.get("score_before", 0)
            after = entry.get("score_after", 0)
            if before is not None and after is not None:
                return after - before
    return None


def main():
    args = parse_args()
    app_id = args["app_id"]
    if not app_id:
        print(
            "Usage: python3 scripts/burr_stagnation.py <app_id>",
            file=sys.stderr,
        )
        sys.exit(1)

    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.", file=sys.stderr)
        sys.exit(1)

    state = last_state(steps)
    if not state:
        print("No valid state found.", file=sys.stderr)
        sys.exit(1)

    turns_since_progress = state.get("turns_since_progress", 0)
    last_score_turn = state.get("last_score_change_turn", 0)
    score = state.get("score", 0)
    max_score = state.get("max_score", 350)
    turn_count = state.get("turn_count", 0)
    current_inventory = list(state.get("inventory", []))
    action_history = state.get("action_history", [])
    visited_locations = state.get("visited_locations", [])
    knowledge_base = state.get("knowledge_base", "")
    discovered_objectives = state.get("discovered_objectives", [])

    # --- Early exit if not stagnating ---
    if turns_since_progress < 3:
        print(
            f"No significant stagnation (last score change was "
            f"{turns_since_progress} turn{'s' if turns_since_progress != 1 else ''} ago)"
        )
        sys.exit(0)

    # --- Stagnation header ---
    score_delta = find_score_delta_at_turn(action_history, last_score_turn)
    delta_str = f" (+{score_delta})" if score_delta and score_delta > 0 else ""

    print("=== Stagnation Diagnosis ===")
    print(f"  Current: Turn {turn_count} | Score: {score}/{max_score}")
    if last_score_turn > 0:
        print(f"  Last score change: Turn {last_score_turn}{delta_str}")
    else:
        print(f"  Last score change: never (score has always been 0)")
    print(f"  Stagnant for: {turns_since_progress} turns")
    print()

    # --- Activity since stagnation ---
    stagnation_start = last_score_turn  # entries after this turn
    recent_entries = [
        e for e in action_history if e.get("turn", 0) > stagnation_start
    ]

    total_actions = len(recent_entries)
    unique_actions = len(set(e.get("action", "") for e in recent_entries))
    novelty_pct = (unique_actions / total_actions * 100) if total_actions else 0

    recent_locations = set()
    for e in recent_entries:
        loc = e.get("location_name") or e.get("location_id")
        if loc:
            recent_locations.add(loc)

    rejection_turns = sum(
        1 for e in recent_entries if e.get("rejection_count", 0) > 0
    )
    rejection_pct = (rejection_turns / total_actions * 100) if total_actions else 0

    range_label = (
        f"turns {stagnation_start + 1}-{turn_count}"
        if stagnation_start > 0
        else f"turns 1-{turn_count}"
    )

    print(f"=== Activity Since Stagnation ({range_label}) ===")
    print(
        f"  Actions taken: {total_actions} total, {unique_actions} unique "
        f"({novelty_pct:.0f}% novelty)"
    )
    print(f"  Locations visited: {len(recent_locations)} unique")
    print(
        f"  Rejections: {rejection_turns} of {total_actions} turns "
        f"({rejection_pct:.0f}%)"
    )
    print()

    # --- Inventory delta ---
    old_inventory = find_inventory_at_score_change(steps, last_score_turn)

    # Fallback: try to get inventory from action_history near that turn
    if old_inventory is None and last_score_turn > 0:
        # Walk action_history to find the entry and check if there's an inventory field
        for e in action_history:
            if e.get("turn") == last_score_turn:
                inv = e.get("inventory")
                if inv is not None:
                    old_inventory = list(inv)
                break

    if old_inventory is not None:
        old_set = set(old_inventory)
        cur_set = set(current_inventory)
        added = sorted(cur_set - old_set)
        removed = sorted(old_set - cur_set)

        print("=== Inventory Delta ===")
        print(
            f"  At last score (T{last_score_turn}): "
            f"{', '.join(old_inventory) if old_inventory else '(empty)'}"
        )
        print(
            f"  Current (T{turn_count}): "
            f"{', '.join(current_inventory) if current_inventory else '(empty)'}"
        )
        print(f"  Added: {', '.join(added) if added else '(none)'}")
        print(f"  Removed: {', '.join(removed) if removed else '(none)'}")
        print()
    else:
        print("=== Inventory Delta ===")
        print(
            f"  Current (T{turn_count}): "
            f"{', '.join(current_inventory) if current_inventory else '(empty)'}"
        )
        print(f"  (could not determine inventory at T{last_score_turn})")
        print()

    # --- Repeated actions ---
    action_location_counts = Counter()
    for e in recent_entries:
        act = e.get("action", "?")
        loc = e.get("location_name") or e.get("location_id", "?")
        action_location_counts[(act, loc)] += 1

    repeated = [
        (count, act, loc)
        for (act, loc), count in action_location_counts.items()
        if count >= 3
    ]
    repeated.sort(key=lambda x: -x[0])

    if repeated:
        print("=== Repeated Actions (3+ times since stagnation) ===")
        for count, act, loc in repeated:
            print(f'  "{act}" at {loc}: {count} times')
        print()
    else:
        print("=== Repeated Actions (3+ times since stagnation) ===")
        print("  (none)")
        print()

    # --- Active objectives ---
    if discovered_objectives:
        print(f"=== Active Objectives (potentially scoring) ===")
        for obj in discovered_objectives:
            if isinstance(obj, dict):
                text = obj.get("text") or obj.get("objective") or str(obj)
            else:
                text = str(obj)
            print(f"  - {text}")
        print()
    else:
        print("=== Active Objectives ===")
        print("  (none discovered)")
        print()


if __name__ == "__main__":
    main()
