"""Show critic evaluations: proposed actions, scores, and justifications."""
import sys

from _args import parse_args, fetch_steps, get_state, get_action, trunc, in_turn_range


def main():
    args = parse_args()
    app_id = args["app_id"]
    if not app_id:
        print("Usage: python3 scripts/burr_critic.py <app_id> [--turns START-END] [--full]", file=sys.stderr)
        sys.exit(1)

    full = args["full"]
    turns_filter = args["turns"]

    steps = fetch_steps(app_id)

    # Collect all evaluate_action entries within the turn range
    entries = []
    for s in steps:
        if get_action(s) != "evaluate_action":
            continue
        state = get_state(s)
        turn = state.get("turn_count")
        if turn is None:
            continue
        if not in_turn_range(turn, turns_filter):
            continue
        entries.append(state)

    if not entries:
        print("No evaluate_action steps found.", file=sys.stderr)
        sys.exit(0)

    # Determine range label
    if turns_filter:
        range_label = f"turns {turns_filter[0]}-{turns_filter[1]}"
    else:
        first_turn = entries[0].get("turn_count", "?")
        last_turn = entries[-1].get("turn_count", "?")
        range_label = f"turns {first_turn}-{last_turn}"

    print(f"=== Critic Report ({range_label}) ===")
    print()

    # Track stats
    scores = []
    confidences = []
    turns_with_rejection = set()
    override_count = 0
    worst = []  # (score, turn, action)

    seen_turns = {}  # turn -> count of evals seen for that turn

    for state in entries:
        turn = state.get("turn_count", "?")
        score = state.get("critic_score", "?")
        confidence = state.get("critic_confidence", "?")
        proposed = state.get("proposed_action", "?")
        justification = state.get("critic_justification", "")
        rejection_count = state.get("rejection_count", 0)
        was_overridden = state.get("was_overridden", False)
        reasoning = state.get("agent_reasoning", "")
        location = state.get("location_name", "?")

        # Track whether this is a retry for the same turn
        if turn not in seen_turns:
            seen_turns[turn] = 0
        seen_turns[turn] += 1
        retry_label = f" (retry)" if seen_turns[turn] > 1 else ""

        # Determine accepted/rejected
        if isinstance(score, (int, float)):
            verdict = "REJECTED" if score < 0 else "ACCEPTED"
        else:
            verdict = "?"

        # Format confidence
        if isinstance(confidence, (int, float)):
            conf_str = f"{confidence:.2f}"
        else:
            conf_str = str(confidence)

        # Format score
        if isinstance(score, (int, float)):
            score_str = f"{score:.2f}"
        else:
            score_str = str(score)

        print(f"--- Turn {turn}{retry_label} [{location}] ---")
        print(f"  Proposed: {proposed}")
        print(f"  Agent thinking: \"{trunc(reasoning, 300, full)}\"")
        print(f"  Critic: {score_str} (confidence: {conf_str}) | {verdict}")
        print(f"  Says: \"{trunc(justification, 500, full)}\"")
        print(f"  Rejections so far: {rejection_count}")
        print()

        # Stats collection
        if isinstance(score, (int, float)):
            scores.append(score)
            worst.append((score, turn, proposed))
        if isinstance(confidence, (int, float)):
            confidences.append(confidence)
        if rejection_count > 0:
            turns_with_rejection.add(turn)
        if was_overridden:
            override_count += 1

    # Summary
    unique_turns = len(seen_turns)
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    rejection_pct = (len(turns_with_rejection) / unique_turns * 100) if unique_turns else 0

    # 3 worst
    worst.sort(key=lambda x: x[0])
    worst_3 = worst[:3]
    worst_strs = [f"T{t} ({s:.2f}, \"{a}\")" for s, t, a in worst_3]

    print("=== Summary ===")
    print(f"  Turns evaluated: {unique_turns} | Avg critic: {avg_score:.2f} | Avg confidence: {avg_conf:.2f}")
    print(f"  Rejections: {len(turns_with_rejection)}/{unique_turns} turns ({rejection_pct:.0f}%) | Overrides: {override_count}")
    if worst_strs:
        print(f"  Lowest: {', '.join(worst_strs)}")
    print()


if __name__ == "__main__":
    main()
