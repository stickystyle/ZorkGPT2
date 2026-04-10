#!/usr/bin/env python3
"""Generate a 3-pass video recap pipeline for a ZorkBurr episode.

Pass 1 — Visual Director: reads dossier, produces 10-15 candidate shots
Pass 2 — Editor: selects 6-9 shots, arranges into scenes, locks timeline
Pass 3 — Narrator: writes voiceover to the locked edit

Pulls the episode's full action history from data/burr_state.db, compiles a
compact "dossier" of the dramatic spine, then runs each pass through an LLM.

Usage:
    uv run scripts/generate_recap_script.py --episode-id ep98
    uv run scripts/generate_recap_script.py --episode-id ep98 --dossier-only
    uv run scripts/generate_recap_script.py --episode-id ep98 --pass1-only
    uv run scripts/generate_recap_script.py --episode-id ep98 --pass2-only
    uv run scripts/generate_recap_script.py --episode-id ep98 --model anthropic/claude-opus-4.6
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

# Make zorkburr importable when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from zorkburr.config import GameConfig
from zorkburr.llm.client import create_llm_client
from zorkburr.llm.prompts import load_prompt

BURR_DB = Path(__file__).parent.parent / "data" / "burr_state.db"
OUT_DIR = Path(__file__).parent.parent / "data" / "recaps"


# ---------------------------------------------------------------------------
# Pass 1 schema — Visual Director: candidate shots
# ---------------------------------------------------------------------------

class CandidateShot(BaseModel):
    shot_id: int = Field(ge=1, description="Sequential 1-based shot number")
    turn_range: str = Field(description='Turns this shot spans, e.g. "T1-T5" or "T14-T16"')
    location: str = Field(description="Where this takes place")
    continuous_action: str = Field(
        description="Plain English description of the continuous action sequence"
    )
    on_screen_action: str = Field(
        description="What the camera sees — framing, movement, physical action"
    )
    inventory_at_start: list[str] = Field(description="Items carried at shot start")
    inventory_at_end: list[str] = Field(description="Items carried at shot end")
    visual_richness: str = Field(description="high / medium / low")
    category: str = Field(
        description="physical_comedy / ritual / discovery / "
        "environmental_transformation / journey / quiet_moment"
    )
    suggested_duration_seconds: int = Field(
        ge=4, le=10,
        description="Suggested duration in seconds (provider may constrain further)"
    )
    notes: str = Field(description="Context for the editor")


class VisualDirectorOutput(BaseModel):
    episode_id: str
    total_turns: int
    final_score: str
    candidate_shots: list[CandidateShot] = Field(
        min_length=10, max_length=20,
        description="10-15 candidate shots (up to 20 allowed)"
    )

    @model_validator(mode="after")
    def _validate_shots(self):
        ids = [s.shot_id for s in self.candidate_shots]
        if ids != sorted(ids):
            raise ValueError(f"shot_ids must be in ascending order, got {ids}")
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate shot_ids: {ids}")
        return self


# ---------------------------------------------------------------------------
# Pass 2 schema — Editor: locked timeline
# ---------------------------------------------------------------------------

class EditShot(BaseModel):
    sequence: int = Field(ge=1, description="Order within the scene (1-based)")
    source_shot_id: int = Field(ge=1, description="Which candidate shot this came from")
    turn_range: str
    on_screen_action: str = Field(
        description="Refined visual description for text-to-video"
    )
    inventory_at_start: list[str]
    inventory_at_end: list[str]
    duration_seconds: int = Field(ge=4, le=10, description="Locked duration in seconds")
    framing_notes: str = Field(
        description="Camera direction: wide/medium/close, movement, focus"
    )
    mood: str = Field(description="One or two words for visual style")


class EditScene(BaseModel):
    scene_id: int = Field(ge=1, description="Sequential scene number")
    scene_title: str
    location: str
    transition_in: str | None = Field(
        default=None,
        description="How we arrive (null for first scene)"
    )
    shots: list[EditShot] = Field(
        min_length=1, max_length=3,
        description="1-3 shots in this scene"
    )
    transition_out: str | None = Field(
        default=None,
        description="How we leave (null for last scene)"
    )


class EditorOutput(BaseModel):
    episode_id: str
    title: str = Field(description="Punchy video title")
    logline: str = Field(description="One sentence, under 140 chars")
    total_duration_seconds: int = Field(
        ge=40, le=90,
        description="Sum of all shot durations"
    )
    final_score_stinger: str = Field(description='Display text, e.g. "90 / 350"')
    scenes: list[EditScene] = Field(
        min_length=2, max_length=4,
        description="2-4 scenes"
    )

    @model_validator(mode="after")
    def _validate_timeline(self):
        total_shots = sum(len(s.shots) for s in self.scenes)
        if not 6 <= total_shots <= 9:
            raise ValueError(
                f"need 6-9 total shots, got {total_shots}"
            )
        actual_duration = sum(
            shot.duration_seconds
            for scene in self.scenes
            for shot in scene.shots
        )
        if actual_duration != self.total_duration_seconds:
            raise ValueError(
                f"total_duration_seconds={self.total_duration_seconds} but "
                f"shot durations sum to {actual_duration}"
            )
        # Scene IDs must be sequential
        scene_ids = [s.scene_id for s in self.scenes]
        if scene_ids != list(range(1, len(self.scenes) + 1)):
            raise ValueError(f"scene_ids must be sequential, got {scene_ids}")
        return self


# ---------------------------------------------------------------------------
# Pass 3 schema — Narrator: voiceover
# ---------------------------------------------------------------------------

class NarratedShot(BaseModel):
    scene_id: int
    sequence: int
    duration_seconds: int
    word_count: int
    narration: str

    @model_validator(mode="after")
    def _validate_narration(self):
        import re
        actual = len(self.narration.split())
        if actual != self.word_count:
            raise ValueError(
                f"scene {self.scene_id} seq {self.sequence}: word_count says "
                f"{self.word_count} but narration has {actual} words"
            )
        max_words = round(self.duration_seconds * 2.3)
        if actual > max_words:
            raise ValueError(
                f"scene {self.scene_id} seq {self.sequence}: {actual} words "
                f"exceeds budget of {max_words} for {self.duration_seconds}s shot"
            )
        # TTS safety: no sentence shorter than 5 words
        sentences = [s.strip() for s in re.split(r"[.!?]+", self.narration) if s.strip()]
        for s in sentences:
            words = s.split()
            if len(words) < 5:
                raise ValueError(
                    f"scene {self.scene_id} seq {self.sequence}: sentence "
                    f"'{s}' has only {len(words)} words — minimum is 5 "
                    f"(TTS uniform-cadence delivery makes short sentences flat)"
                )
        return self


class NarratorOutput(BaseModel):
    episode_id: str
    narrated_shots: list[NarratedShot] = Field(min_length=6, max_length=9)
    total_words: int
    total_duration_seconds: int
    estimated_speaking_seconds: float

    @model_validator(mode="after")
    def _validate_totals(self):
        actual_words = sum(s.word_count for s in self.narrated_shots)
        if actual_words != self.total_words:
            raise ValueError(
                f"total_words={self.total_words} but shots sum to {actual_words}"
            )
        actual_dur = sum(s.duration_seconds for s in self.narrated_shots)
        if actual_dur != self.total_duration_seconds:
            raise ValueError(
                f"total_duration_seconds={self.total_duration_seconds} but "
                f"shots sum to {actual_dur}"
            )
        if self.estimated_speaking_seconds > self.total_duration_seconds:
            raise ValueError(
                f"estimated_speaking_seconds ({self.estimated_speaking_seconds}) "
                f"exceeds total_duration_seconds ({self.total_duration_seconds})"
            )
        return self


# ---------------------------------------------------------------------------
# Dossier extraction (unchanged from v1)
# ---------------------------------------------------------------------------

def find_episode_app(conn: sqlite3.Connection, episode_id: str) -> str:
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
            per_turn[turn] = json.loads(inv_json)
        except (TypeError, json.JSONDecodeError):
            continue
    return per_turn


def compute_inventory_events(timeline: dict[int, list[str]]) -> list[dict[str, Any]]:
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
    if turn in timeline:
        return timeline[turn]
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
    ah: list[dict] = state.get("action_history", []) or []

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

    completed = state.get("completed_objectives", []) or []
    discovered = state.get("discovered_objectives", []) or []

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
# LLM calls — three passes
# ---------------------------------------------------------------------------

def _call_llm(prompt_name: str, response_model, user_content: str,
              model_override: str | None, pass_name: str):
    config = GameConfig()
    client = create_llm_client(config)
    system_prompt = load_prompt(prompt_name)
    model = model_override or config.agent_model

    print(f"\n[{pass_name}] Calling LLM ({model})...", file=sys.stderr)
    result = client.create(
        model=model,
        response_model=response_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.9,
        max_tokens=8192,
    )
    return result


def run_pass1_visual_director(dossier: dict, model: str | None) -> VisualDirectorOutput:
    user_content = (
        "Here is the episode dossier. Identify 10-15 candidate shots.\n\n"
        f"```json\n{json.dumps(dossier, indent=2)}\n```"
    )
    return _call_llm("recap_visual_director", VisualDirectorOutput,
                      user_content, model, "Pass 1: Visual Director")


PROVIDER_DURATIONS = {
    "runway": (5, 10),
    "veo": (4, 6, 8),
}


def run_pass2_editor(
    candidates: VisualDirectorOutput, dossier: dict, model: str | None,
    video_provider: str = "runway",
) -> EditorOutput:
    valid_durations = PROVIDER_DURATIONS.get(video_provider, (5, 10))
    duration_note = (
        f"\n\n## IMPORTANT: Duration Constraint\n\n"
        f"The video generator ({video_provider}) only produces clips of "
        f"exactly **{' or '.join(str(d) for d in valid_durations)} seconds**. "
        f"Every shot's `duration_seconds` MUST be one of: {list(valid_durations)}. "
        f"No other values are accepted. Use shorter clips for quick action "
        f"beats and longer clips for scenes that need room to breathe."
    )
    user_content = (
        "Here are the candidate shots from the visual director, "
        "followed by the episode dossier for reference.\n\n"
        "## Candidate Shots\n\n"
        f"```json\n{candidates.model_dump_json(indent=2)}\n```\n\n"
        "## Episode Dossier\n\n"
        f"```json\n{json.dumps(dossier, indent=2)}\n```"
        f"{duration_note}"
    )
    return _call_llm("recap_editor", EditorOutput,
                      user_content, model, "Pass 2: Editor")


def run_pass3_narrator(
    edit: EditorOutput, dossier: dict, model: str | None,
) -> NarratorOutput:
    user_content = (
        "Here is the locked edit timeline, followed by the episode dossier "
        "for factual accuracy.\n\n"
        "## Locked Edit Timeline\n\n"
        f"```json\n{edit.model_dump_json(indent=2)}\n```\n\n"
        "## Episode Dossier\n\n"
        f"```json\n{json.dumps(dossier, indent=2)}\n```"
    )
    return _call_llm("recap_narrator", NarratorOutput,
                      user_content, model, "Pass 3: Narrator")


# ---------------------------------------------------------------------------
# Merge passes into a final shot list for downstream tools
# ---------------------------------------------------------------------------

def merge_to_shotlist(
    edit: EditorOutput,
    narration: NarratorOutput,
    dossier: dict,
) -> dict:
    """Produce the downstream-compatible shot list used by video gen, TTS,
    and assembly scripts. Combines editor timeline + narrator text."""
    narr_lookup = {
        (n.scene_id, n.sequence): n for n in narration.narrated_shots
    }
    beats = []
    beat_index = 0
    for scene in edit.scenes:
        for shot in scene.shots:
            beat_index += 1
            key = (scene.scene_id, shot.sequence)
            narr = narr_lookup.get(key)
            beats.append({
                "beat_index": beat_index,
                "scene_id": scene.scene_id,
                "scene_title": scene.scene_title,
                "turn_range": shot.turn_range,
                "title": f"{scene.scene_title} #{shot.sequence}",
                "scene_prompt": shot.on_screen_action,
                "framing_notes": shot.framing_notes,
                "mood": shot.mood,
                "inventory_at_start": shot.inventory_at_start,
                "inventory_at_end": shot.inventory_at_end,
                "narration": narr.narration if narr else "",
                "duration_seconds": shot.duration_seconds,
                "word_count": narr.word_count if narr else 0,
            })

    return {
        "episode_id": edit.episode_id,
        "title": edit.title,
        "logline": edit.logline,
        "total_duration_seconds": edit.total_duration_seconds,
        "final_score_stinger": edit.final_score_stinger,
        "beats": beats,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="e.g. ep98")
    parser.add_argument("--model", default=None, help="Override LLM model for all passes")
    parser.add_argument("--dossier-only", action="store_true",
                        help="Only build & dump the dossier; skip all LLM calls")
    parser.add_argument("--pass1-only", action="store_true",
                        help="Run only Pass 1 (Visual Director)")
    parser.add_argument("--pass2-only", action="store_true",
                        help="Run Pass 1 + Pass 2 (Editor), skip narrator")
    parser.add_argument("--provider", choices=["runway", "veo"], default="runway",
                        help="Video provider — determines valid shot durations "
                             "(runway: 5/10s, veo: 4/6/8s). Default: runway")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    # Build dossier
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

    # --- Pass 1: Visual Director ---
    candidates = run_pass1_visual_director(dossier, args.model)
    p1_path = args.out_dir / f"{args.episode_id}.candidates.json"
    p1_path.write_text(candidates.model_dump_json(indent=2))
    print(f"Wrote {len(candidates.candidate_shots)} candidate shots -> {p1_path.name}",
          file=sys.stderr)

    # Summary
    for shot in candidates.candidate_shots:
        print(
            f"  [{shot.shot_id:2d}] {shot.turn_range:8s}  {shot.suggested_duration_seconds}s  "
            f"{shot.visual_richness:6s}  {shot.category:30s}  {shot.location}",
            file=sys.stderr,
        )

    if args.pass1_only:
        return 0

    # --- Pass 2: Editor ---
    edit = run_pass2_editor(candidates, dossier, args.model, args.provider)
    p2_path = args.out_dir / f"{args.episode_id}.edit.json"
    p2_path.write_text(edit.model_dump_json(indent=2))
    total_shots = sum(len(s.shots) for s in edit.scenes)
    print(f"Wrote locked edit ({total_shots} shots, {edit.total_duration_seconds}s) -> {p2_path.name}",
          file=sys.stderr)

    # Summary
    print(f"\n  TITLE: {edit.title}", file=sys.stderr)
    print(f"  LOGLINE: {edit.logline}", file=sys.stderr)
    for scene in edit.scenes:
        print(f"\n  Scene {scene.scene_id}: {scene.scene_title} ({scene.location})",
              file=sys.stderr)
        if scene.transition_in:
            print(f"    IN: {scene.transition_in}", file=sys.stderr)
        for shot in scene.shots:
            print(
                f"    [{shot.sequence}] {shot.turn_range}  {shot.duration_seconds}s  "
                f"(from candidate #{shot.source_shot_id})  {shot.mood}",
                file=sys.stderr,
            )
        if scene.transition_out:
            print(f"    OUT: {scene.transition_out}", file=sys.stderr)

    if args.pass2_only:
        return 0

    # --- Pass 3: Narrator ---
    narration = run_pass3_narrator(edit, dossier, args.model)
    p3_path = args.out_dir / f"{args.episode_id}.narration_raw.json"
    p3_path.write_text(narration.model_dump_json(indent=2))
    print(
        f"\nWrote narration ({narration.total_words} words, "
        f"~{narration.estimated_speaking_seconds:.0f}s speaking) -> {p3_path.name}",
        file=sys.stderr,
    )

    # Summary
    for ns in narration.narrated_shots:
        print(
            f"  [S{ns.scene_id}.{ns.sequence}] {ns.duration_seconds}s  "
            f"{ns.word_count:2d}w  \"{ns.narration}\"",
            file=sys.stderr,
        )

    # --- Merge into final shot list ---
    merged = merge_to_shotlist(edit, narration, dossier)
    shots_path = args.out_dir / f"{args.episode_id}.shotlist.json"
    shots_path.write_text(json.dumps(merged, indent=2))
    print(f"\nWrote merged shot list -> {shots_path}", file=sys.stderr)

    print("\n" + "=" * 72, file=sys.stderr)
    print(f"TITLE: {merged['title']}", file=sys.stderr)
    print(f"LOGLINE: {merged['logline']}", file=sys.stderr)
    print(f"DURATION: {merged['total_duration_seconds']}s  "
          f"({len(merged['beats'])} beats)", file=sys.stderr)
    print(f"STINGER: {merged['final_score_stinger']}", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    for beat in merged["beats"]:
        print(
            f"\n[Beat {beat['beat_index']}] S{beat['scene_id']} {beat['turn_range']} "
            f"— {beat['title']}  ({beat['duration_seconds']}s, {beat['word_count']}w)",
            file=sys.stderr,
        )
        print(f"  ACTION: {beat['scene_prompt']}", file=sys.stderr)
        print(f'  NARRATION: "{beat["narration"]}"', file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
