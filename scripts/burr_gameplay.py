"""Gameplay quality checks: KB, memories, objectives, and agent reasoning."""
import sys
from _args import parse_args, fetch_steps, get_state, get_action, in_turn_range, trunc, last_state


def main():
    args = parse_args()
    if not args["app_id"]:
        print("Usage: python3 scripts/burr_gameplay.py <app_id> [--turns START-END] [--full]", file=sys.stderr)
        sys.exit(1)

    steps = fetch_steps(args["app_id"])
    if not steps:
        print("No steps found.")
        return

    full = args["full"]
    turns_filter = args["turns"]
    final = last_state(steps)

    # --- Knowledge Base ---
    kb = final.get("knowledge_base", "")
    print("=== KNOWLEDGE BASE ===")
    print(kb if kb else "(empty)")

    # --- Memories ---
    memories = final.get("memories_by_location", {})
    mem_total = sum(len(v) for v in memories.values())
    print(f"\n=== MEMORIES ({mem_total} total across {len(memories)} locations) ===")
    for loc_id, mems in memories.items():
        # Try to get a location name from the first memory or fall back to ID
        loc_label = f"Location {loc_id}"
        print(f"  {loc_label} ({len(mems)} memories):")
        for m in mems:
            cat = m.get("category", "?")
            title = m.get("title", "?")
            text = trunc(m.get("text", ""), 300, full)
            print(f'    [{cat}] "{title}": {text}')

    # --- Discovered Objectives ---
    objectives = final.get("discovered_objectives", [])
    print(f"\n=== DISCOVERED OBJECTIVES ({len(objectives)}) ===")
    for o in objectives:
        print(f"  - {o}")

    # --- Completed Objectives ---
    completed = final.get("completed_objectives", [])
    print(f"\n=== COMPLETED OBJECTIVES ({len(completed)}) ===")
    for o in completed:
        print(f"  - {o}")

    # --- Agent Gameplay (per-turn) ---
    # Use execute_action steps — state persists all fields from generate_action
    exec_steps = [s for s in steps if get_action(s) == "execute_action"]
    # Filter by turn range or take last 25
    filtered = []
    for s in exec_steps:
        st = get_state(s)
        tc = st.get("turn_count")
        if tc is None:
            continue
        if turns_filter:
            if in_turn_range(tc, turns_filter):
                filtered.append(s)
        else:
            filtered.append(s)

    if not turns_filter:
        filtered = filtered[-25:]

    if filtered:
        first_tc = get_state(filtered[0]).get("turn_count", "?")
        last_tc = get_state(filtered[-1]).get("turn_count", "?")
        print(f"\n=== AGENT GAMEPLAY (turns {first_tc}-{last_tc}) ===")
    else:
        print("\n=== AGENT GAMEPLAY (no matching turns) ===")

    for s in filtered:
        st = get_state(s)
        tc = st.get("turn_count", "?")
        loc = st.get("location_name", "?")
        action = st.get("proposed_action") or st.get("action_to_take", "?")
        reasoning = trunc(st.get("agent_reasoning", ""), 600, full)
        next_steps = trunc(st.get("next_steps", ""), 200, full)
        game_resp = trunc(st.get("game_response", ""), 200, full)
        inventory = st.get("inventory", [])
        inv_str = ", ".join(inventory) if isinstance(inventory, list) else str(inventory)

        print(f'  Turn {tc}: [{loc}] "{action}"')
        if reasoning:
            print(f"    Thinking: {reasoning}")
        if next_steps:
            print(f"    Plan: {next_steps}")
        if game_resp:
            print(f"    Game says: \"{game_resp}\"")
        if inv_str:
            print(f"    Inventory: {inv_str}")
        print()


if __name__ == "__main__":
    main()
