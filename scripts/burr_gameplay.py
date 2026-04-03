"""Gameplay quality checks: KB, memories, objectives, and agent reasoning."""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_gameplay.py <app_id>", file=sys.stderr)
        sys.exit(1)
    app_id = sys.argv[1]
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    steps = data.get("steps", [])
    if not steps:
        print("No steps found.")
        return

    agent_steps = [
        s
        for s in steps
        if s.get("step_start_log", {}).get("action") == "generate_action"
    ][-25:]
    last_state = {}
    for s in reversed(steps):
        end = s.get("step_end_log")
        if end and end.get("state"):
            last_state = end["state"]
            break
    kb = last_state.get("knowledge_base", "")
    memories = last_state.get("memories_by_location", {})
    objectives = last_state.get("discovered_objectives", [])

    print("=== KNOWLEDGE BASE ===")
    print(kb[:800] if kb else "(empty)")

    mem_total = sum(len(v) for v in memories.values())
    print(f"\n=== MEMORIES ({mem_total} total across {len(memories)} locations) ===")
    for loc_id, mems in list(memories.items())[:8]:
        titles = [m.get("title", "?") for m in mems[:3]]
        print(f"  Location {loc_id}: {titles}")

    print(f"\n=== OBJECTIVES ({len(objectives)}) ===")
    for o in objectives:
        print(f"  - {o}")

    print("\n=== AGENT REASONING (last 10 turns) ===")
    for s in agent_steps[-10:]:
        end = s.get("step_end_log")
        if not end or not end.get("state"):
            continue
        state = end["state"]
        reasoning = state.get("agent_reasoning", "")[:250]
        action = state.get("proposed_action", "?")
        loc = state.get("location_name", "?")
        print(f"  Turn {state.get('turn_count', '?')}: [{loc}] {action}")
        print(f"    Thinking: {reasoning}")
        print()


if __name__ == "__main__":
    main()
