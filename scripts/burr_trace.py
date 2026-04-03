"""Show the last 10 steps from a Burr app trace with action, score, location, critic."""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_trace.py <app_id>", file=sys.stderr)
        sys.exit(1)
    app_id = sys.argv[1]
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    steps = data.get("steps", [])
    print(f"Total steps: {len(steps)}")
    for s in steps[-10:]:
        end = s.get("step_end_log") or {}
        state = end.get("state", {})
        action = s.get("step_start_log", {}).get("action", "?")
        print(
            f"  {action}: score={state.get('score', '?')}"
            f" loc={state.get('location_name', '?')}"
            f" critic={state.get('critic_score', '?')}"
        )


if __name__ == "__main__":
    main()
