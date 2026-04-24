"""Resolve a PENDING IMPROVEMENT verdict in both the prose journal and the
structured improvements.jsonl. Keeps the two sources in sync.

Usage:
    python3 scripts/update_verdict.py --from 117 --to 118 \\
        --verdict IMPROVED --score-delta +12 --best-after 101 \\
        --notes "score 89 -> 101, stale-verdict rule fired correctly"

Behavior:
    - Finds the IMPROVEMENT block "## Episode <from> → <to> — IMPROVEMENT" in
      journal.md (falls back to journal_archive.md) and replaces its
      `**Result:** PENDING` line with the new verdict.
    - Finds the jsonl line whose episode_from/episode_to match and updates
      verdict, score_delta, best_score_after.
    - Aborts without writing if either side is missing, so prose and jsonl
      cannot drift out of sync by way of this script.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JOURNAL = REPO / "docs/orchestrator/journal.md"
ARCHIVE = REPO / "docs/orchestrator/journal_archive.md"
JSONL = REPO / "docs/orchestrator/improvements.jsonl"

VALID_VERDICTS = ("IMPROVED", "NEUTRAL", "DEGRADED", "REVERTED", "PARTIAL")


def find_prose_block(path: Path, ep_from: int, ep_to: int):
    """Return (text, start_idx, block_end_idx) if the IMPROVEMENT block is
    found in ``path`` and still has `**Result:** PENDING`. Returns None
    otherwise."""
    if not path.exists():
        return None
    text = path.read_text()
    header = f"## Episode {ep_from} → {ep_to} — IMPROVEMENT"
    start = text.find(header)
    if start == -1:
        return None
    # Block ends at the next "\n---" after the header (entry separator)
    sep = text.find("\n---", start)
    block_end = sep if sep != -1 else len(text)
    block = text[start:block_end]
    if "**Result:** PENDING" not in block:
        return None
    return (text, start, block_end)


def count_prose_headers(path: Path, ep_from: int, ep_to: int) -> int:
    """Count IMPROVEMENT headers for this episode pair in ``path``. Used to
    detect duplicate entries before touching anything."""
    if not path.exists():
        return 0
    header = f"## Episode {ep_from} → {ep_to} — IMPROVEMENT"
    return path.read_text().count(header)


def count_jsonl_matches(ep_from: int, ep_to: int) -> int:
    """Count jsonl entries for this episode pair. Used to detect duplicates."""
    if not JSONL.exists():
        return 0
    n = 0
    for line in JSONL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("episode_from") == ep_from and entry.get("episode_to") == ep_to:
            n += 1
    return n


def write_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(path)


def build_result_line(verdict: str, score_delta, best_after, notes: str) -> str:
    parts = [verdict]
    if score_delta is not None:
        parts.append(f"score_delta {score_delta:+d}")
    if best_after is not None:
        parts.append(f"best_after {best_after}")
    if notes:
        parts.append(notes)
    return " — ".join(parts)


def find_jsonl_index(ep_from: int, ep_to: int):
    """Return (lines, index) for the jsonl entry matching the episode pair,
    or None if not found."""
    if not JSONL.exists():
        return None
    lines = JSONL.read_text().splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("episode_from") == ep_from and entry.get("episode_to") == ep_to:
            return (lines, i, entry)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Resolve an IMPROVEMENT verdict in journal.md + improvements.jsonl.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--from", dest="ep_from", type=int, required=True,
                    help="Episode number the improvement was dispatched from.")
    ap.add_argument("--to", dest="ep_to", type=int, required=True,
                    help="Episode number the improvement first affected.")
    ap.add_argument("--verdict", required=True, choices=VALID_VERDICTS)
    ap.add_argument("--score-delta", type=int, default=None,
                    help="score(ep_to) - score(ep_from); omit if not meaningful.")
    ap.add_argument("--best-after", type=int, default=None,
                    help="Best score observed after this change took effect.")
    ap.add_argument("--notes", default="",
                    help="Appended to the prose Result line (keep it short).")
    args = ap.parse_args()

    # Duplicate check — if the same episode pair appears more than once in
    # either source, resolving "the" entry is ambiguous. Abort so the user
    # disambiguates manually rather than silently updating only the first
    # occurrence. (Duplicates shouldn't happen in normal flow, but can arise
    # from revert+re-dispatch scenarios; silent half-resolution is worse than
    # a hard error.)
    prose_total = (
        count_prose_headers(JOURNAL, args.ep_from, args.ep_to)
        + count_prose_headers(ARCHIVE, args.ep_from, args.ep_to)
    )
    jsonl_total = count_jsonl_matches(args.ep_from, args.ep_to)
    if prose_total > 1 or jsonl_total > 1:
        print(
            f"ERROR: duplicate entries for ep{args.ep_from}→{args.ep_to}: "
            f"prose={prose_total} (journal.md + archive.md), jsonl={jsonl_total}. "
            f"Resolve the duplicate(s) manually (delete the stale one) and re-run.",
            file=sys.stderr,
        )
        return 1

    # Feasibility check — both sides must match before we touch either file.
    prose = find_prose_block(JOURNAL, args.ep_from, args.ep_to)
    prose_path = JOURNAL
    if prose is None:
        prose = find_prose_block(ARCHIVE, args.ep_from, args.ep_to)
        prose_path = ARCHIVE
    if prose is None:
        print(
            f"ERROR: No IMPROVEMENT block for ep{args.ep_from}→{args.ep_to} "
            f"with PENDING Result in {JOURNAL.name} or {ARCHIVE.name}.",
            file=sys.stderr,
        )
        return 1

    jsonl_match = find_jsonl_index(args.ep_from, args.ep_to)
    if jsonl_match is None:
        print(
            f"ERROR: No jsonl entry for ep{args.ep_from}→{args.ep_to} in {JSONL.name}. "
            f"Was the IMPROVEMENT committed before the jsonl convention existed?\n"
            f"If so, append a backfill line and re-run.",
            file=sys.stderr,
        )
        return 1

    # Compute updated content for both files.
    text, start, block_end = prose
    block = text[start:block_end]
    new_result = build_result_line(
        args.verdict, args.score_delta, args.best_after, args.notes
    )
    updated_block = block.replace(
        "**Result:** PENDING", f"**Result:** {new_result}", 1
    )
    new_prose_text = text[:start] + updated_block + text[block_end:]

    lines, idx, entry = jsonl_match
    entry["verdict"] = args.verdict
    if args.score_delta is not None:
        entry["score_delta"] = args.score_delta
    if args.best_after is not None:
        entry["best_score_after"] = args.best_after
    lines[idx] = json.dumps(entry)
    new_jsonl_text = "\n".join(lines) + "\n"

    # Write both. Atomic per-file; cross-file failure is vanishingly unlikely
    # after the feasibility check above.
    write_atomic(prose_path, new_prose_text)
    write_atomic(JSONL, new_jsonl_text)

    print(
        f"OK ep{args.ep_from}→{args.ep_to}: {new_result}\n"
        f"  prose: {prose_path.relative_to(REPO)}\n"
        f"  jsonl: {JSONL.relative_to(REPO)} (line {idx + 1})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
