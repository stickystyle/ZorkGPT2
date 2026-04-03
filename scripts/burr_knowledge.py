"""Show accumulated knowledge base, memories, and objectives."""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_knowledge.py <app_id>", file=sys.stderr)
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
    kb = last_state.get("knowledge_base", "none")
    memories = last_state.get("memories_by_location", {})
    objectives = last_state.get("discovered_objectives", [])
    print("=== Knowledge Base ===")
    print(kb[:500] if kb else "empty")
    print(f"\n=== Memories ({len(memories)} locations) ===")
    for loc, mem in list(memories.items())[:5]:
        print(f"  {loc}: {str(mem)[:150]}")
    print(f"\n=== Objectives ({len(objectives)}) ===")
    for o in objectives:
        print(f"  - {o}")


if __name__ == "__main__":
    main()
