"""Pathfinding trace: map graph, exit failures, and navigation analysis."""
import json
import sys
import urllib.request

DIR_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up", "d": "down", "ne": "northeast", "nw": "northwest",
    "se": "southeast", "sw": "southwest",
}

MOVE_COMMANDS = {
    "north", "south", "east", "west", "up", "down",
    "northeast", "northwest", "southeast", "southwest",
    "n", "s", "e", "w", "ne", "nw", "se", "sw",
    "go north", "go south", "go east", "go west", "go up", "go down",
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_pathfinding.py <app_id>", file=sys.stderr)
        sys.exit(1)
    app_id = sys.argv[1]
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    steps = data.get("steps", [])
    if not steps:
        print("No steps found.")
        return

    last_state = {}
    for s in reversed(steps):
        end = s.get("step_end_log")
        if end and end.get("state"):
            last_state = end["state"]
            break
    map_data = last_state.get("map_data", {})
    rooms = map_data.get("rooms", {})
    connections = map_data.get("connections", {})
    failures = map_data.get("failures", {})

    conn_total = sum(len(v) for v in connections.values())
    print(f"=== MAP GRAPH ({len(rooms)} rooms, {conn_total} connections) ===")
    for room_id, name in sorted(rooms.items(), key=lambda x: int(x[0])):
        exits = connections.get(room_id, {})
        exit_strs = [
            f"{d}->{rooms.get(str(dest), '?')}" for d, dest in exits.items()
        ]
        print(
            f"  R{room_id} [{name}]:"
            f" {' | '.join(exit_strs) if exit_strs else '(no exits)'}"
        )

    if failures:
        print(f"\n=== EXIT FAILURES ({len(failures)} recorded) ===")
        for key, count in sorted(failures.items(), key=lambda x: -x[1]):
            room_id, direction = key.split(":", 1)
            room_name = rooms.get(room_id, "?")
            print(f"  {room_name} ({room_id}) {direction}: failed {count}x")

    print("\n=== PATHFINDING TRACE (last 25 turns) ===")
    gen_steps = [
        s for s in steps
        if s.get("step_start_log", {}).get("action") == "generate_action"
    ][-25:]
    exec_steps = [
        s for s in steps
        if s.get("step_start_log", {}).get("action") == "execute_action"
    ][-25:]

    for i, gs in enumerate(gen_steps):
        gstate = (gs.get("step_end_log") or {}).get("state", {})
        turn = gstate.get("turn_count", "?")
        action = gstate.get("proposed_action", "?")
        next_steps = gstate.get("next_steps", "")[:150]
        pre_loc = gstate.get("location_name", "?")
        pre_loc_id = gstate.get("location_id", "?")
        post_loc = pre_loc
        post_loc_id = pre_loc_id
        if i < len(exec_steps):
            estate = (exec_steps[i].get("step_end_log") or {}).get("state", {})
            post_loc = estate.get("location_name", pre_loc)
            post_loc_id = estate.get("location_id", pre_loc_id)
        moved = "MOVED" if str(pre_loc_id) != str(post_loc_id) else "STAYED"
        action_lower = action.lower().strip()
        is_move = action_lower in MOVE_COMMANDS
        map_valid = ""
        if is_move and str(pre_loc_id) in connections:
            from_exits = connections[str(pre_loc_id)]
            norm_dir = action_lower.replace("go ", "")
            norm_dir = DIR_ALIASES.get(norm_dir, norm_dir)
            if norm_dir in from_exits:
                expected_dest = str(from_exits[norm_dir])
                if str(post_loc_id) == expected_dest:
                    map_valid = "MAP_CORRECT"
                else:
                    map_valid = (
                        f"MAP_MISMATCH(expected R{expected_dest},"
                        f" got R{post_loc_id})"
                    )
            else:
                fail_key = f"{pre_loc_id}:{norm_dir}"
                if fail_key in failures:
                    map_valid = f"KNOWN_FAILURE({failures[fail_key]}x)"
                else:
                    map_valid = "NOT_IN_MAP"
        print(
            f'  T{turn}: [{pre_loc}] {action} -> {moved} [{post_loc}]'
            f' plan="{next_steps}" {map_valid}'
        )


if __name__ == "__main__":
    main()
