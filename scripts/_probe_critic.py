"""Direct probe: call critic LLM against extracted fixtures with a candidate model.

Loads one or more evaluate_action fixtures, reconstructs the same user context
that critic.py builds in production, and calls a candidate model directly with
the critic prompt. Prints the candidate's output side-by-side with the original
(Ministral) output for comparison.

Usage:
    uv run python scripts/_probe_critic.py <fixture.json> [<fixture.json> ...] \
        [--model MODEL]

    # Probe all ep96 critic fixtures against gemini-3-flash-preview (default):
    uv run python scripts/_probe_critic.py tests/fixtures/ep96_*_evaluate_action.json

    # Override candidate model:
    uv run python scripts/_probe_critic.py tests/fixtures/ep96_t23_evaluate_action.json \
        --model remote/anthropic/claude-haiku-4.5
"""
import glob
import json
import sys
from typing import Any

from zorkburr.config import GameConfig
from zorkburr.llm.client import create_llm_client, thinking_kwargs
from zorkburr.llm.models import CriticResponse
from zorkburr.llm.prompts import load_prompt


DEFAULT_CANDIDATE = "remote/google/gemini-3-flash-preview"


def build_user_content(state: dict) -> str:
    """Reconstruct the critic's user context from fixture state.

    Mirrors zorkburr/actions/critic.py evaluate_action() lines 131-155.
    """
    history = state.get("action_history", []) or []
    recent = history[-3:]
    recent_lines = []
    for entry in recent:
        recent_lines.append(
            f"  Turn {entry['turn']}: {entry['action']} -> {entry.get('response', '')[:200]}"
        )

    exits = state.get("exits") or []
    inventory = state.get("inventory") or []

    context_parts = [
        f"**Game State:** {state.get('game_response', '')[:500]}",
        f"**Location:** {state.get('location_name', '')}",
        f"**Available Exits:** {', '.join(exits) if exits else 'unknown'}",
        f"**Inventory:** {', '.join(inventory) if inventory else '(empty)'}",
    ]
    if recent_lines:
        context_parts.append("**Recent Actions:**\n" + "\n".join(recent_lines))
    context_parts.append(f"\n**Proposed Action:** {state.get('proposed_action', '')}")
    return "\n".join(context_parts)


def call_critic(client: Any, model: str, user_content: str, config: GameConfig) -> dict:
    """Call the critic LLM with the given user content. Returns dict or error dict."""
    system_prompt = load_prompt("critic")
    try:
        response: CriticResponse = client.create(
            model=model,
            response_model=CriticResponse,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_retries=2,
            max_tokens=256,
            **thinking_kwargs(config, model, False),
        )
        return {
            "score": response.score,
            "justification": response.justification,
            "confidence": response.confidence,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def probe_one(path: str, client: Any, model: str, config: GameConfig) -> dict:
    """Run one fixture through the candidate critic. Returns a comparison dict."""
    with open(path) as f:
        fixture = json.load(f)

    state = fixture["state"]
    original = fixture["original_output"]
    meta = fixture["meta"]

    user_content = build_user_content(state)
    candidate = call_critic(client, model, user_content, config)

    return {
        "path": path,
        "turn": meta.get("turn"),
        "role": meta.get("role"),
        "description": meta.get("problem_description", ""),
        "location": state.get("location_name", "").strip(),
        "proposed_action": state.get("proposed_action"),
        "rejection_count": state.get("rejection_count"),
        "inventory_count": len(state.get("inventory") or []),
        "original": {
            "score": original.get("critic_score"),
            "confidence": original.get("critic_confidence"),
            "justification": original.get("critic_justification", ""),
        },
        "candidate": candidate,
        "user_content": user_content,
    }


def print_comparison(result: dict, model_name: str, verbose: bool = False) -> None:
    """Print one fixture's comparison in human-readable form."""
    role = result["role"] or "?"
    turn = result["turn"] or "?"
    loc = result["location"]
    proposed = result["proposed_action"]
    rej = result["rejection_count"]

    print("=" * 80)
    print(f"[{role.upper():8s}] turn {turn} — {loc}")
    print(f"  proposed: {proposed!r}  (rejection_count at start: {rej})")
    if result["description"]:
        print(f"  problem:  {result['description']}")
    print()

    orig = result["original"]
    cand = result["candidate"]

    # Ministral original
    orig_verdict = "REJECT" if orig["score"] < 0.3 else "ACCEPT"
    print(f"  Ministral (original):  score={orig['score']:+.2f}  "
          f"conf={orig['confidence']:.2f}  [{orig_verdict}]")
    print(f"    justification: {orig['justification']}")
    print()

    # Candidate
    if "error" in cand:
        print(f"  {model_name} (candidate):  ERROR — {cand['error']}")
    else:
        cand_verdict = "REJECT" if cand["score"] < 0.3 else "ACCEPT"
        print(f"  {model_name} (candidate):  score={cand['score']:+.2f}  "
              f"conf={cand['confidence']:.2f}  [{cand_verdict}]")
        print(f"    justification: {cand['justification']}")

        # Agreement analysis
        if orig_verdict == cand_verdict:
            tag = "AGREE"
        elif orig_verdict == "REJECT" and cand_verdict == "ACCEPT":
            tag = "FLIP: reject -> accept"
        else:
            tag = "FLIP: accept -> reject"
        print()
        print(f"  verdict delta: {tag}  (score delta: {cand['score'] - orig['score']:+.2f})")

    if verbose:
        print()
        print("  --- USER CONTENT SENT ---")
        for line in result["user_content"].splitlines():
            print(f"    {line}")
    print()


def print_summary(results: list[dict], model_name: str) -> None:
    """Print a summary table at the end."""
    print("=" * 80)
    print(f"SUMMARY — candidate: {model_name}")
    print("=" * 80)
    print(f"{'role':8s} {'turn':5s} {'proposed':24s} {'orig':>8s} {'cand':>8s} {'verdict':24s}")
    print("-" * 80)

    flip_count = 0
    agree_count = 0
    for r in results:
        turn = r["turn"] or "?"
        role = (r["role"] or "?")[:8]
        proposed = (r["proposed_action"] or "")[:24]
        orig_score = r["original"]["score"]
        cand = r["candidate"]
        if "error" in cand:
            cand_str = "ERR"
            verdict = f"ERROR"
        else:
            cand_score = cand["score"]
            cand_str = f"{cand_score:+.2f}"
            orig_v = "REJECT" if orig_score < 0.3 else "ACCEPT"
            cand_v = "REJECT" if cand_score < 0.3 else "ACCEPT"
            if orig_v == cand_v:
                verdict = f"AGREE ({orig_v})"
                agree_count += 1
            else:
                verdict = f"FLIP ({orig_v}->{cand_v})"
                flip_count += 1
        print(f"{role:8s} t{str(turn):<4s} {proposed:24s} {orig_score:+.2f}   {cand_str:>7s} {verdict:24s}")

    print("-" * 80)
    total = len(results)
    errors = total - flip_count - agree_count
    print(f"total={total}  agree={agree_count}  flip={flip_count}  error={errors}")

    # For problem fixtures, a FLIP from REJECT to ACCEPT is the win signal
    # For healthy fixtures, AGREE (both ACCEPT) is the regression-safety signal
    problem_flips = sum(
        1 for r in results
        if r["role"] == "problem"
        and "error" not in r["candidate"]
        and r["original"]["score"] < 0.3
        and r["candidate"]["score"] >= 0.3
    )
    problem_total = sum(1 for r in results if r["role"] == "problem")
    healthy_agrees = sum(
        1 for r in results
        if r["role"] == "healthy"
        and "error" not in r["candidate"]
        and r["original"]["score"] >= 0.3
        and r["candidate"]["score"] >= 0.3
    )
    healthy_total = sum(1 for r in results if r["role"] == "healthy")

    print()
    print(f"PROBLEM fixtures (want REJECT->ACCEPT flips): {problem_flips}/{problem_total}")
    print(f"HEALTHY fixtures (want preserved ACCEPTs):    {healthy_agrees}/{healthy_total}")


def main() -> int:
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return 1

    # Parse --model flag
    model = DEFAULT_CANDIDATE
    verbose = False
    fixture_paths: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--model":
            model = args[i + 1]
            i += 2
        elif arg in ("-v", "--verbose"):
            verbose = True
            i += 1
        else:
            # Expand globs
            matched = sorted(glob.glob(arg))
            fixture_paths.extend(matched if matched else [arg])
            i += 1

    if not fixture_paths:
        print("Error: no fixture paths provided")
        return 1

    config = GameConfig()
    client = create_llm_client(config)

    print(f"CRITIC PROBE — candidate model: {model}")
    print(f"Fixtures: {len(fixture_paths)}")
    print()

    results: list[dict] = []
    for path in fixture_paths:
        result = probe_one(path, client, model, config)
        results.append(result)
        print_comparison(result, model, verbose=verbose)

    print_summary(results, model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
