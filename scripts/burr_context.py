"""Show the formatted context the agent sees, with section-by-section breakdown."""
import re
import sys

from _args import parse_args, fetch_steps, get_state, get_action, trunc


def parse_sections(ctx):
    """Split formatted context on **Bold Header** patterns.

    Returns list of (section_name, section_text) tuples.
    """
    parts = re.split(r"(\*\*[^*]+\*\*)", ctx)
    # parts is [text_before, header1, text1, header2, text2, ...]
    sections = []
    for i in range(1, len(parts) - 1, 2):
        header = parts[i].strip("* ")
        # Remove trailing colon if present
        header = header.rstrip(":")
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((header, body))
    return sections


def find_context_for_turn(steps, target_turn):
    """Find the formatted_context for a specific turn.

    Strategy: find the execute_action step where turn_count == target_turn,
    then read formatted_context from its state (it persists from assemble_context).
    """
    for s in steps:
        if get_action(s) == "execute_action":
            state = get_state(s)
            if state.get("turn_count") == target_turn:
                return state
    return None


def find_latest_context(steps):
    """Find the most recent generate_action step with formatted_context."""
    for s in reversed(steps):
        if get_action(s) == "generate_action":
            state = get_state(s)
            if state.get("formatted_context"):
                return state
    return None


def main():
    args = parse_args()
    app_id = args["app_id"]
    if not app_id:
        print(
            "Usage: python3 scripts/burr_context.py <app_id> [--turn N] [--full]",
            file=sys.stderr,
        )
        sys.exit(1)

    full = args["full"]
    target_turn = args["turn"]
    limit = 5000

    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.", file=sys.stderr)
        sys.exit(1)

    # Find the right state
    if target_turn is not None:
        state = find_context_for_turn(steps, target_turn)
        if not state:
            # Find max turn for helpful error
            max_turn = 0
            for s in steps:
                tc = get_state(s).get("turn_count", 0)
                if isinstance(tc, int) and tc > max_turn:
                    max_turn = tc
            print(
                f"Turn {target_turn} not found. Available turns: 1-{max_turn}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        state = find_latest_context(steps)
        if not state:
            print("No generate_action step with formatted_context found.", file=sys.stderr)
            sys.exit(1)

    ctx = state.get("formatted_context", "")
    turn_count = state.get("turn_count", "?")
    location = state.get("location_name", "?")

    if not ctx:
        print(f"Turn {turn_count}: formatted_context is empty.", file=sys.stderr)
        sys.exit(1)

    # Header
    print(f"=== Formatted Context — Turn {turn_count} [{location}] ({len(ctx)} chars total) ===")
    print()

    # Section breakdown
    sections = parse_sections(ctx)
    if sections:
        print("Section sizes:")
        for name, body in sections:
            # Total section size includes header markup + body
            print(f"  {name}: {len(body.strip())} chars")
        print()

    # Full context
    print("--- Full Context ---")
    print(trunc(ctx, limit, full))
    if not full and len(ctx) > limit:
        print(f"\n... truncated at {limit}/{len(ctx)} chars (use --full to see all)")


if __name__ == "__main__":
    main()
