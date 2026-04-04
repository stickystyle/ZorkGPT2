"""Show accumulated knowledge base, memories, objectives, and stats."""
import sys

from _args import parse_args, fetch_steps, last_state, trunc


def main():
    args = parse_args()
    if not args["app_id"]:
        print("Usage: python3 scripts/burr_knowledge.py <app_id> [--full] [--location LOC_ID]", file=sys.stderr)
        sys.exit(1)

    app_id = args["app_id"]
    full = args["full"]
    loc_filter = args["location"]

    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.")
        return

    state = last_state(steps)
    if not state:
        print("No state found in steps.")
        return

    # --- Knowledge Base ---
    kb = state.get("knowledge_base", "") or ""
    print(f"=== Knowledge Base ({len(kb)} chars) ===")
    print(trunc(kb, 2000, full) if kb else "empty")

    # --- Memory Stats ---
    mem_stats = state.get("memory_stats", {})
    if mem_stats:
        parts = []
        for key in ("new", "dedup_rejected", "superseded", "ephemeral_pruned", "mem_consolidated", "total"):
            if key in mem_stats:
                label = key.replace("_", " ").capitalize()
                parts.append(f"{label}: {mem_stats[key]}")
        print("\n=== Memory Stats ===")
        print(f"  {' | '.join(parts)}")

    # --- Memories ---
    memories = state.get("memories_by_location", {})
    map_data = state.get("map_data", {}) or {}
    rooms = map_data.get("rooms", {}) if isinstance(map_data, dict) else {}

    # Build quality summary
    all_mems = []
    for loc_id, mem_list in memories.items():
        if not isinstance(mem_list, list):
            continue
        for m in mem_list:
            if isinstance(m, dict):
                all_mems.append(m)

    cat_counts = {}
    status_counts = {}
    active_count = 0
    for m in all_mems:
        cat = m.get("category", "UNKNOWN")
        status = m.get("status", "UNKNOWN")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "ACTIVE":
            active_count += 1

    loc_count = len(memories)
    print(f"\n=== Memory Quality ===")
    print(f"  Total: {active_count} active across {loc_count} locations")
    if cat_counts:
        cat_str = " ".join(f"{k}={v}" for k, v in sorted(cat_counts.items(), key=lambda x: -x[1]))
        print(f"  By category: {cat_str}")
    if status_counts:
        status_str = " ".join(f"{k}={v}" for k, v in sorted(status_counts.items(), key=lambda x: -x[1]))
        print(f"  By status: {status_str}")

    # Filter locations
    if loc_filter:
        filtered = {k: v for k, v in memories.items() if str(k) == str(loc_filter)}
    else:
        filtered = memories

    print(f"\n=== Memories ({len(filtered)} locations) ===")
    for loc_id, mem_list in sorted(filtered.items(), key=lambda x: str(x[0])):
        if not isinstance(mem_list, list):
            continue
        room_name = rooms.get(str(loc_id), "")
        header = f"Location {loc_id}"
        if room_name:
            header += f" [{room_name}]"
        print(f"  --- {header} ({len(mem_list)} memories) ---")
        for m in mem_list:
            if not isinstance(m, dict):
                continue
            cat = m.get("category", "?")
            status = m.get("status", "?")
            title = m.get("title", "untitled")
            ep = m.get("episode", "?")
            turn = m.get("turn", "?")
            text = m.get("text", "")
            print(f"    [{cat}|{status}] \"{title}\" (ep{ep}, T{turn})")
            if text:
                print(f"      Text: {trunc(text, 500, full)}")

    # --- Discovered Objectives ---
    objectives = state.get("discovered_objectives", [])
    print(f"\n=== Discovered Objectives ({len(objectives)}) ===")
    for o in objectives:
        print(f"  - {o}")

    # --- Completed Objectives ---
    completed = state.get("completed_objectives", [])
    print(f"\n=== Completed Objectives ({len(completed)}) ===")
    for o in completed:
        print(f"  - {o}")

    # --- Visited Locations ---
    visited = state.get("visited_locations", [])
    print(f"\n=== Visited Locations ({len(visited)}) ===")
    if visited:
        loc_strs = [str(v) for v in visited]
        print(f"  {', '.join(loc_strs)}")


if __name__ == "__main__":
    main()
