"""Show the formatted context the agent sees (from the last generate_action step)."""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_context.py <app_id>", file=sys.stderr)
        sys.exit(1)
    app_id = sys.argv[1]
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    steps = data.get("steps", [])
    for s in reversed(steps):
        if s.get("step_start_log", {}).get("action") == "generate_action":
            end = s.get("step_end_log")
            if not end or not end.get("state"):
                continue  # skip in-progress or crashed steps
            state = end["state"]
            ctx = state.get("formatted_context", "")
            print("=== FORMATTED CONTEXT (what the agent sees) ===")
            print(ctx[:2000])
            print(f"\n... ({len(ctx)} chars total)")
            return
    print("No generate_action step with valid state found.")


if __name__ == "__main__":
    main()
