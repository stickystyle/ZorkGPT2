"""Cross-episode comparison from log files. No Burr API needed."""
import glob
import os
import re
import sys

from _args import parse_args

# Regex patterns for parsing log lines
TURN_RE = re.compile(
    r"^TURN\s+(\d+)\s*\|\s*loc=(\S+)\s*\|\s*score=(\d+)/(\d+)\s*\|\s*critic=([\d.]+)\s*\|\s*rejections=(\d+)\s*\|\s*action=(.*)"
)
EPISODE_END_RE = re.compile(
    r"^EPISODE_END\s*\|(.+)"
)
KV_RE = re.compile(r"(\w+)=(\S+)")


def parse_episode_end(line):
    """Parse an EPISODE_END line into a dict of key=value pairs."""
    m = EPISODE_END_RE.match(line.strip())
    if not m:
        return None
    return dict(KV_RE.findall(m.group(1)))


def parse_turn(line):
    """Parse a TURN line into a dict."""
    m = TURN_RE.match(line.strip())
    if not m:
        return None
    return {
        "turn": int(m.group(1)),
        "loc": m.group(2),
        "score": int(m.group(3)),
        "max_score": int(m.group(4)),
        "critic": float(m.group(5)),
        "rejections": int(m.group(6)),
        "action": m.group(7).strip(),
    }


def extract_ep_number(filepath):
    """Extract episode number from a filename like run_log_ep58.txt."""
    m = re.search(r"run_log_ep(\d+)\.txt", filepath)
    return int(m.group(1)) if m else None


def simplify_reason(reason):
    """Simplify end reason strings."""
    if not reason:
        return "running"
    if "death" in reason:
        return "death"
    if "win" in reason:
        return "win"
    return reason  # e.g. max_turns


def parse_log_file(filepath):
    """Parse a single log file, returning episode data dict."""
    ep_num = extract_ep_number(filepath)
    if ep_num is None:
        return None

    turns = []
    episode_end = None

    try:
        with open(filepath, "r") as f:
            for line in f:
                t = parse_turn(line)
                if t:
                    turns.append(t)
                    continue
                e = parse_episode_end(line)
                if e:
                    episode_end = e
    except (OSError, IOError):
        return None

    if not turns:
        return None

    # Compute stats from TURN lines
    critic_scores = [t["critic"] for t in turns]
    avg_critic = sum(critic_scores) / len(critic_scores) if critic_scores else 0.0
    turns_with_rejections = sum(1 for t in turns if t["rejections"] > 0)
    rejection_rate = turns_with_rejections / len(turns) if turns else 0.0

    # First turn where score > 0
    first_score_turn = None
    for t in turns:
        if t["score"] > 0:
            first_score_turn = t["turn"]
            break

    # Last turn info (for death location)
    last_turn = turns[-1] if turns else None

    result = {
        "ep_num": ep_num,
        "avg_critic": avg_critic,
        "rejection_rate": rejection_rate,
        "first_score_turn": first_score_turn,
        "last_turn": last_turn,
        "turn_count": len(turns),
    }

    if episode_end:
        result["turns_total"] = int(episode_end.get("turns", len(turns)))
        score_str = episode_end.get("score", "0/350")
        result["score"] = int(score_str.split("/")[0])
        result["max_score"] = int(score_str.split("/")[1]) if "/" in score_str else 350
        result["locations"] = int(episode_end.get("locations", 0))
        result["reason"] = episode_end.get("reason", "")
        result["finished"] = True
    else:
        # In-progress: derive from turn lines
        result["turns_total"] = len(turns)
        result["score"] = last_turn["score"] if last_turn else 0
        result["max_score"] = last_turn["max_score"] if last_turn else 350
        # Count unique locations from turn data
        result["locations"] = len(set(t["loc"] for t in turns))
        result["reason"] = ""
        result["finished"] = False

    return result


def main():
    args = parse_args()
    last_n = args["last"] if args["last"] is not None else 10

    # Find log files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    log_pattern = os.path.join(project_root, "docs", "orchestrator", "run_log_ep*.txt")
    log_files = glob.glob(log_pattern)

    if not log_files:
        print("No log files found.", file=sys.stderr)
        sys.exit(1)

    # Parse all episodes
    episodes = []
    for f in log_files:
        ep = parse_log_file(f)
        if ep:
            episodes.append(ep)

    # Sort by episode number
    episodes.sort(key=lambda e: e["ep_num"])

    # Limit to last N
    if last_n and len(episodes) > last_n:
        episodes = episodes[-last_n:]

    if not episodes:
        print("No valid episodes found.", file=sys.stderr)
        sys.exit(1)

    # Build table
    print(f"\n=== Episode Comparison (last {last_n}) ===\n")
    print("| Episode | Turns | Score | vs Prev | Best | 1st Score | Locations | Avg Critic | Rej% | End Reason |")
    print("|---------|-------|-------|---------|------|-----------|-----------|------------|------|------------|")

    running_best = 0
    prev_score = None
    score_trend = []
    critic_trend = []
    rejection_trend = []
    death_locations = []

    for ep in episodes:
        score = ep["score"]
        turns = ep["turns_total"]
        reason_raw = ep["reason"]
        reason = simplify_reason(reason_raw)
        if not ep["finished"]:
            reason = "running"

        # vs Prev
        if prev_score is not None:
            delta = score - prev_score
            vs_prev = f"{delta:+d}" if delta != 0 else "0"
        else:
            vs_prev = "-"
        prev_score = score

        # Running best
        if score > running_best:
            running_best = score
        best = running_best

        # First score turn
        fst = str(ep["first_score_turn"]) if ep["first_score_turn"] is not None else "-"

        locations = ep["locations"]
        avg_critic = ep["avg_critic"]
        rej_pct = ep["rejection_rate"] * 100

        # Collect trends
        score_trend.append((ep["ep_num"], score))
        critic_trend.append((ep["ep_num"], avg_critic))
        rejection_trend.append((ep["ep_num"], rej_pct))

        # Death locations
        if "death" in reason and ep["last_turn"]:
            death_locations.append((ep["ep_num"], ep["last_turn"]["loc"]))

        suffix = " *" if not ep["finished"] else ""
        rej_str = f"{rej_pct:.0f}%"
        print(
            f"| ep{ep['ep_num']:<4} | {turns:<5} | {score:<5} | {vs_prev:<7} | {best:<4} "
            f"| {fst:<9} | {locations:<9} | {avg_critic:<10.2f} | {rej_str:<4} | {reason + suffix:<10} |"
        )

    # Trends
    print("\n=== Trends ===")

    # Score trend
    scores_str = " -> ".join(str(s) for _, s in score_trend)
    best_score = max(score_trend, key=lambda x: x[1])
    print(f"  Score: {scores_str} (best={best_score[1]} at ep{best_score[0]})")

    # Critic trend
    critics_str = " -> ".join(f"{c:.2f}" for _, c in critic_trend)
    if len(critic_trend) >= 2:
        first_c = critic_trend[0][1]
        last_c = critic_trend[-1][1]
        direction = "trending up" if last_c > first_c else "trending down" if last_c < first_c else "stable"
    else:
        direction = "n/a"
    print(f"  Avg critic: {critics_str} ({direction})")

    # Rejection trend
    rejs_str = " -> ".join(f"{r:.0f}%" for _, r in rejection_trend)
    if len(rejection_trend) >= 2:
        first_r = rejection_trend[0][1]
        last_r = rejection_trend[-1][1]
        direction = "trending up" if last_r > first_r else "trending down" if last_r < first_r else "stable"
    else:
        direction = "n/a"
    print(f"  Rejection rate: {rejs_str} ({direction})")

    # Death locations
    print("\n=== Death Locations ===")
    if death_locations:
        for ep_num, loc in death_locations:
            print(f"  ep{ep_num}: {loc}")
    else:
        print("  (none)")

    print()


if __name__ == "__main__":
    main()
