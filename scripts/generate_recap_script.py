#!/usr/bin/env python3
"""Generate an Attenborough-style video recap shot list for a ZorkBurr episode.

Pulls the episode's full action history from data/burr_state.db, compiles a
compact "dossier" of the dramatic spine (score events, first visits, repeated
actions, memories, opening/closing turns), feeds it to an LLM director, and
writes the resulting shot list as JSON.

Usage:
    uv run scripts/generate_recap_script.py --episode-id ep98
    uv run scripts/generate_recap_script.py --episode-id ep98 --dossier-only
    uv run scripts/generate_recap_script.py --episode-id ep98 --model anthropic/claude-opus-4.6
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Make zorkburr importable when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from zorkburr.config import GameConfig
from zorkburr.llm.client import create_llm_client
from zorkburr.llm.prompts import load_prompt

BURR_DB = Path(__file__).parent.parent / "data" / "burr_state.db"
OUT_DIR = Path(__file__).parent.parent / "data" / "recaps"


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class RecapBeat(BaseModel):
    beat_index: int = Field(ge=1, description="1-based sequential beat number")
    turn_range: str = Field(description='Game turns covered, e.g. "T1-T5" or "T195"')
    title: str = Field(description="Short beat title for human reference")
    carried_items: str = Field(
        description=(
            "What the adventurer is physically carrying during this beat, in "
            "visual terms — e.g. 'a large gilded painting clutched to the chest "
            "with both hands; a brass lantern swinging from the belt; nothing "
            "else'. Must reflect the dossier's inventory_at_turn for the turn(s) "
            "this beat covers. If the character has just dropped items, describe "
            "the drop visually."
        )
    )
    scene_prompt: str = Field(
        description=(
            "Detailed visual description for text-to-video. MUST incorporate "
            "base_character AND carried_items. Do not contradict carried_items "
            "(e.g. don't describe a sword if the adventurer has dropped it)."
        )
    )
    on_screen_action: str = Field(description="One-line summary of what the viewer sees")
    narration: str = Field(description="Attenborough voiceover line(s) for this beat")
    duration_seconds: int = Field(ge=3, le=10)


class RecapShotList(BaseModel):
    title: str = Field(description="Punchy episode title")
    logline: str = Field(description="One tweetable sentence, under 140 chars")
    base_character: str = Field(
        description=(
            "The unchanging appearance of the adventurer: cloak, hood, face, "
            "boots, build. NO items, NO weapons — those belong in each beat's "
            "carried_items. This is the silhouette. It is reused verbatim in "
            "every scene_prompt alongside that beat's carried_items."
        )
    )
    visual_style: str = Field(description="Visual style phrase reused in every scene prompt")
    total_duration_seconds: int = Field(ge=45, le=90)
    final_score_stinger: str = Field(description="End title card line (display only, not spoken)")
    beats: list[RecapBeat] = Field(min_length=6, max_length=8)


# ---------------------------------------------------------------------------
# Dossier extraction
# ---------------------------------------------------------------------------

def find_episode_app(conn: sqlite3.Connection, episode_id: str) -> str:
    """Return the most recent app_id for a given episode_id."""
    row = conn.execute(
        """
        SELECT app_id
        FROM zorkburr_state
        WHERE json_extract(state, '$.episode_id') = ?
        GROUP BY app_id
        ORDER BY MAX(created_at) DESC
        LIMIT 1
        """,
        (episode_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"No episode found with episode_id={episode_id!r}")
    return row[0]


def load_final_state(conn: sqlite3.Connection, app_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT state FROM zorkburr_state WHERE app_id=? ORDER BY sequence_id DESC LIMIT 1",
        (app_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"No state rows for app_id={app_id}")
    return json.loads(row[0])


def load_inventory_timeline(conn: sqlite3.Connection, app_id: str) -> dict[int, list[str]]:
    """Reconstruct per-turn inventory from the Burr state log.

    Returns {turn_count: inventory_list} for every turn the app reached,
    using the end-of-turn state (the highest sequence_id per turn).
    """
    rows = conn.execute(
        """
        SELECT json_extract(state, '$.turn_count'), json_extract(state, '$.inventory')
        FROM zorkburr_state
        WHERE app_id = ?
        ORDER BY sequence_id
        """,
        (app_id,),
    ).fetchall()
    per_turn: dict[int, list[str]] = {}
    for turn, inv_json in rows:
        if turn is None or inv_json is None:
            continue
        try:
            per_turn[turn] = json.loads(inv_json)  # overwrite with later rows → end-of-turn
        except (TypeError, json.JSONDecodeError):
            continue
    return per_turn


def compute_inventory_events(timeline: dict[int, list[str]]) -> list[dict[str, Any]]:
    """Return a list of turns where inventory changed, with gained/lost diffs.

    Only includes turns where the inventory actually changed from the prior
    turn. Each event carries the full before/after so the director can narrate
    the moment without needing to cross-reference.
    """
    events: list[dict[str, Any]] = []
    sorted_turns = sorted(timeline.keys())
    if not sorted_turns:
        return events
    prev_inv: set[str] = set()
    prev_list: list[str] = []
    for t in sorted_turns:
        cur_list = timeline[t]
        cur = set(cur_list)
        if cur == prev_inv:
            continue
        gained = sorted(cur - prev_inv)
        lost = sorted(prev_inv - cur)
        if gained or lost:
            events.append({
                "turn": t,
                "gained": gained,
                "lost": lost,
                "inventory_before": prev_list,
                "inventory_after": cur_list,
            })
        prev_inv = cur
        prev_list = cur_list
    return events


def inventory_at(timeline: dict[int, list[str]], turn: int) -> list[str]:
    """Return the inventory at (or just before) the given turn."""
    if turn in timeline:
        return timeline[turn]
    # Walk backward to find the nearest earlier turn with data
    for t in range(turn - 1, -1, -1):
        if t in timeline:
            return timeline[t]
    return []


def build_dossier(
    episode_id: str,
    app_id: str,
    state: dict[str, Any],
    inv_timeline: dict[int, list[str]],
) -> dict[str, Any]:
    """Distill the final state into a compact narrative dossier."""
    ah: list[dict] = state.get("action_history", []) or []

    # Score events (every turn where the score changed)
    score_events = []
    prev_score = 0
    for a in ah:
        delta = a["score_after"] - prev_score
        if delta != 0:
            score_events.append({
                "turn": a["turn"],
                "delta": delta,
                "total": a["score_after"],
                "location": a.get("location_name", "?").strip(),
                "action": a["action"],
                "response": a["response"].strip()[:200],
                "reasoning": (a.get("reasoning") or "").strip()[:300],
                "inventory_at_turn": inventory_at(inv_timeline, a["turn"]),
            })
            prev_score = a["score_after"]

    # First visits (location discoveries in order)
    first_visits = []
    seen_loc: set[int] = set()
    for a in ah:
        lid = a.get("location_id")
        if lid is None or lid in seen_loc:
            continue
        seen_loc.add(lid)
        first_visits.append({
            "turn": a["turn"],
            "location_id": lid,
            "location_name": (a.get("location_name") or "").strip(),
            "entry_action": a["action"],
            "inventory_at_turn": inventory_at(inv_timeline, a["turn"]),
        })

    # Repeated action runs (3+ identical actions in a row = frustration)
    repetitions = []
    i = 0
    while i < len(ah):
        j = i
        while j < len(ah) and ah[j]["action"] == ah[i]["action"]:
            j += 1
        if j - i >= 3:
            repetitions.append({
                "turn_start": ah[i]["turn"],
                "turn_end": ah[j - 1]["turn"],
                "count": j - i,
                "action": ah[i]["action"],
                "location": (ah[i].get("location_name") or "").strip(),
                "sample_response": ah[i]["response"].strip()[:150],
            })
            i = j
        else:
            i += 1

    # Opening and closing turn windows (verbatim, with reasoning)
    def snapshot(a: dict) -> dict:
        return {
            "turn": a["turn"],
            "location": (a.get("location_name") or "").strip(),
            "action": a["action"],
            "response": a["response"].strip()[:300],
            "reasoning": (a.get("reasoning") or "").strip()[:300],
            "score_after": a["score_after"],
            "inventory_at_turn": inventory_at(inv_timeline, a["turn"]),
        }

    opening = [snapshot(a) for a in ah[:5]]
    closing = [snapshot(a) for a in ah[-5:]]

    # Memories — the agent's own post-hoc reflections (flatten across locations)
    memories = []
    for lid, mems in (state.get("memories_by_location") or {}).items():
        if not isinstance(mems, list):
            mems = [mems]
        for m in mems:
            if not isinstance(m, dict):
                continue
            memories.append({
                "location_id": lid,
                "category": m.get("category"),
                "title": m.get("title"),
                "text": m.get("text"),
            })

    # Completed / discovered objectives
    completed = state.get("completed_objectives", []) or []
    discovered = state.get("discovered_objectives", []) or []

    # Inventory story
    inv_events = compute_inventory_events(inv_timeline)
    initial_inv = inv_timeline.get(min(inv_timeline.keys()), []) if inv_timeline else []
    final_inv = state.get("inventory", [])

    return {
        "episode_id": episode_id,
        "app_id": app_id,
        "turn_count": state.get("turn_count"),
        "final_score": state.get("score"),
        "max_score": state.get("max_score"),
        "game_over": state.get("game_over"),
        "game_over_reason": state.get("game_over_reason") or None,
        "final_location": (state.get("location_name") or "").strip(),
        "initial_inventory": initial_inv,
        "final_inventory": final_inv,
        "inventory_events": inv_events,
        "unique_locations_visited": len(first_visits),
        "score_events": score_events,
        "first_visits": first_visits,
        "repeated_action_runs": repetitions,
        "opening_turns": opening,
        "closing_turns": closing,
        "agent_memories": memories,
        "completed_objectives": completed,
        "discovered_objectives_at_end": discovered[:5],
    }


# ---------------------------------------------------------------------------
# LLM director
# ---------------------------------------------------------------------------

def generate_shot_list(dossier: dict, model_override: str | None) -> RecapShotList:
    config = GameConfig()
    client = create_llm_client(config)
    system_prompt = load_prompt("recap_director")
    model = model_override or config.agent_model

    user_payload = json.dumps(dossier, indent=2)

    print(f"Calling director LLM ({model})...", file=sys.stderr)
    result = client.create(
        model=model,
        response_model=RecapShotList,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Here is the episode dossier. Produce the shot list.\n\n"
                    f"```json\n{user_payload}\n```"
                ),
            },
        ],
        temperature=0.9,
        max_tokens=4096,
    )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="e.g. ep98")
    parser.add_argument("--model", default=None, help="Override director model")
    parser.add_argument("--dossier-only", action="store_true",
                        help="Only build & dump the dossier; skip the LLM call")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    conn = sqlite3.connect(BURR_DB)
    try:
        app_id = find_episode_app(conn, args.episode_id)
        final = load_final_state(conn, app_id)
        inv_timeline = load_inventory_timeline(conn, app_id)
    finally:
        conn.close()

    dossier = build_dossier(args.episode_id, app_id, final, inv_timeline)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    dossier_path = args.out_dir / f"{args.episode_id}.dossier.json"
    dossier_path.write_text(json.dumps(dossier, indent=2))
    print(f"Wrote dossier -> {dossier_path}", file=sys.stderr)
    print(
        f"  turns={dossier['turn_count']}  score={dossier['final_score']}/{dossier['max_score']}  "
        f"locations={dossier['unique_locations_visited']}  score_events={len(dossier['score_events'])}  "
        f"repetitions={len(dossier['repeated_action_runs'])}  memories={len(dossier['agent_memories'])}  "
        f"inv_events={len(dossier['inventory_events'])}",
        file=sys.stderr,
    )

    if args.dossier_only:
        return 0

    shot_list = generate_shot_list(dossier, args.model)

    shots_path = args.out_dir / f"{args.episode_id}.shotlist.json"
    shots_path.write_text(shot_list.model_dump_json(indent=2))
    print(f"\nWrote shot list -> {shots_path}", file=sys.stderr)

    # Pretty-print a human-readable summary
    print("\n" + "=" * 72)
    print(f"TITLE: {shot_list.title}")
    print(f"LOGLINE: {shot_list.logline}")
    print(f"DURATION: {shot_list.total_duration_seconds}s")
    print(f"STINGER: {shot_list.final_score_stinger}")
    print("=" * 72)
    for beat in shot_list.beats:
        print(f"\n[Beat {beat.beat_index}] {beat.turn_range} — {beat.title}  ({beat.duration_seconds}s)")
        print(f"  ACTION: {beat.on_screen_action}")
        print(f'  NARRATION: "{beat.narration}"')
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
