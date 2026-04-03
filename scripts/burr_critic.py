"""Show critic evaluations: proposed actions, scores, and justifications."""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/burr_critic.py <app_id>", file=sys.stderr)
        sys.exit(1)
    app_id = sys.argv[1]
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    steps = data.get("steps", [])
    for s in steps[-30:]:
        end = s.get("step_end_log") or {}
        state = end.get("state", {})
        action_name = s.get("step_start_log", {}).get("action", "")
        if action_name == "evaluate_action":
            print(f"--- Turn {state.get('turn_count', '?')} ---")
            print(f"  Proposed: {state.get('proposed_action', '?')}")
            print(f"  Critic score: {state.get('critic_score', '?')}")
            print(f"  Critic says: {state.get('critic_justification', '?')[:200]}")
            print(f"  Rejections so far: {state.get('rejection_count', 0)}")
            print()


if __name__ == "__main__":
    main()
