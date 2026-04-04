"""Shared argument parsing for Burr diagnostic scripts."""
import sys


def parse_args(argv=None):
    """Parse common CLI flags from sys.argv (or provided list).

    Returns dict with keys:
        app_id   - first positional arg (str or None)
        turns    - (from, to) tuple or None
        full     - bool
        verbose  - bool
        turn     - int or None (single turn)
        location - str or None
        last     - int or None
        extra    - list of unrecognised positional args
    """
    if argv is None:
        argv = sys.argv[1:]
    result = {
        "app_id": None,
        "turns": None,
        "full": False,
        "verbose": False,
        "turn": None,
        "location": None,
        "last": None,
        "extra": [],
    }
    i = 0
    positionals = []
    while i < len(argv):
        arg = argv[i]
        if arg == "--turns" and i + 1 < len(argv):
            parts = argv[i + 1].split("-", 1)
            result["turns"] = (int(parts[0]), int(parts[1]))
            i += 2
        elif arg == "--full":
            result["full"] = True
            i += 1
        elif arg == "--verbose":
            result["verbose"] = True
            i += 1
        elif arg == "--turn" and i + 1 < len(argv):
            result["turn"] = int(argv[i + 1])
            i += 2
        elif arg == "--location" and i + 1 < len(argv):
            result["location"] = argv[i + 1]
            i += 2
        elif arg == "--last" and i + 1 < len(argv):
            result["last"] = int(argv[i + 1])
            i += 2
        elif not arg.startswith("-"):
            positionals.append(arg)
            i += 1
        else:
            i += 1  # skip unknown flags
    if positionals:
        result["app_id"] = positionals[0]
        result["extra"] = positionals[1:]
    return result


def fetch_steps(app_id):
    """Fetch all steps from the Burr tracker for an app."""
    import json
    import urllib.request
    url = f"http://localhost:7241/api/v0/default/{app_id}/__none__/apps"
    data = json.loads(urllib.request.urlopen(url).read())
    return data.get("steps", [])


def get_state(step):
    """Extract state dict from a step, or empty dict."""
    end = step.get("step_end_log") or {}
    return end.get("state", {})


def get_action(step):
    """Extract the Burr action name from a step."""
    return step.get("step_start_log", {}).get("action", "")


def in_turn_range(turn_count, turns_filter):
    """Check if a turn_count is within the (from, to) filter. None means all."""
    if turns_filter is None:
        return True
    return turns_filter[0] <= turn_count <= turns_filter[1]


def trunc(text, limit, full=False):
    """Truncate text to limit chars unless full=True."""
    if not text:
        return ""
    if full or len(text) <= limit:
        return text
    return text[:limit] + "..."


def last_state(steps):
    """Get the state from the last step with valid state."""
    for s in reversed(steps):
        st = get_state(s)
        if st:
            return st
    return {}
