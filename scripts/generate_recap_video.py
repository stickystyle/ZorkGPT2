#!/usr/bin/env python3
"""Generate a Veo 3.1 Lite video clip for one beat of a ZorkBurr recap.

Reads a shot list produced by scripts/generate_recap_script.py, picks a
single beat by --beat-index, feeds its scene_prompt + the canonical
character reference image to Veo 3.1 Lite, polls until the operation
completes, and downloads the resulting mp4 to data/recaps/.

First-test mode: you MUST pass --beat-index. There is no "generate the whole
recap" flag yet — we test one beat at a time to avoid blowing budget on a
bad format.

Requires GOOGLE_AI_STUDIO (or GOOGLE_API_KEY / GEMINI_API_KEY) in the env.

Usage:
    uv run scripts/generate_recap_video.py --episode-id ep98 --beat-index 6
    uv run scripts/generate_recap_video.py --episode-id ep98 --beat-index 6 --resolution 1080p
    uv run scripts/generate_recap_video.py --episode-id ep98 --beat-index 6 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

RECAPS_DIR = Path(__file__).parent.parent / "data" / "recaps"
CHARACTER_REFERENCE = RECAPS_DIR / "character_reference.png"

MODEL_ID = "veo-3.1-lite-generate-preview"
MAX_DURATION_SECONDS = 8  # Veo 3.1 caps at 8s per clip

# Style enforcement directives, appended to every scene prompt.
#
# The Gemini API (unlike Vertex) does NOT support negative_prompt, so our
# only lever is aggressive positive prompting. Research on diffusion models
# shows "NOT X" / "no X" phrasing is a weak signal — the model often
# focuses on X anyway. These directives are written entirely in positive
# terms, describing what the shot IS with enough specificity and repetition
# that the target-style training-data neurons dominate the defaults.
#
# The --style flag picks which enforcer to use. The chosen enforcer also
# replaces the director's visual_style field at prompt-assembly time, so
# there is no conflict between director output and target style.
STYLE_ENFORCERS: dict[str, str] = {
    "cinematic": (
        "The entire shot is rendered as cinematic fantasy realism in the "
        "register of prestige television — The Witcher, Game of Thrones, "
        "House of the Dragon — or a AAA action RPG cutscene like God of War "
        "or The Last of Us. Shot on a virtual cinema camera with a 35mm "
        "equivalent lens, shallow depth of field, natural motivated lighting. "
        "Physical materials rendered with full PBR fidelity: the wool cloak "
        "shows individual fibers and weave, the leather boots show grain "
        "and scuffing, every surface has micro-detail. Grimdark colour "
        "grading: desaturated earth tones, muted greens and umbers, warm "
        "amber key light against cold blue shadow. Volumetric atmosphere, "
        "dust in the air catching the light. The character moves with the "
        "restrained, weighty physicality of live-action actors in costume. "
        "The overall look is that of a high-budget fantasy television still "
        "brought to motion — every frame could be a promotional key art."
    ),
    "painterly": (
        "The entire shot is rendered as a moving oil painting on rough "
        "canvas. Every frame shows visible brushstrokes, hand-painted "
        "textures, and the slight imperfection of traditional physical "
        "media. The colors are mixed on a wooden palette: burnt umber, raw "
        "sienna, yellow ochre, deep ultramarine, titanium white used "
        "sparingly. The figure and the setting are rendered with the loose, "
        "atmospheric brushwork of late-1970s fantasy paperback covers — "
        "Frank Frazetta, James Gurney, Darrell Sweet, Boris Vallejo, Jeff "
        "Jones. Every surface is painted, not rendered. The overall look "
        "is a 1979 fantasy paperback illustration that has been gently, "
        "softly animated — the painting breathes and moves but remains, "
        "unmistakably, a painting."
    ),
    "spiderverse": (
        "The entire shot is rendered in the visual style of Spider-Man: "
        "Into the Spider-Verse and Across the Spider-Verse — stylised "
        "cel-shaded 3D animation that looks like a moving comic book. "
        "Thick black ink outlines around the character and major shapes. "
        "Flat shaded colour regions — distinct steps of light and shadow, "
        "not smooth gradients. Visible halftone dot patterns in the "
        "mid-tones, giving a printed-comic feel. Slight chromatic "
        "aberration on high-contrast edges, with cyan and magenta fringes. "
        "Bold, saturated colours: warm ambers, deep purples, splashes of "
        "magenta. The camera moves with action-comic dynamism — every "
        "frame could be a panel in a printed graphic novel. The frame "
        "rate has the slightly stuttered feel of stop-motion, as though "
        "each pose was held for an extra half-beat."
    ),
}

# Price per second (720p and 1080p, with audio) as of 2026-04
PRICE_PER_SECOND = {
    "720p": 0.05,
    "1080p": 0.08,
}

POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 900  # 15 minutes


def load_api_key() -> str:
    for key in ("GOOGLE_AI_STUDIO", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        val = os.environ.get(key)
        if val:
            return val
    raise SystemExit(
        "No Google AI Studio API key found. Set GOOGLE_AI_STUDIO in .env "
        "(or GOOGLE_API_KEY / GEMINI_API_KEY)."
    )


def load_shot_list(episode_id: str) -> dict:
    path = RECAPS_DIR / f"{episode_id}.shotlist.json"
    if not path.exists():
        raise SystemExit(
            f"Shot list not found: {path}\n"
            f"Run: uv run scripts/generate_recap_script.py --episode-id {episode_id}"
        )
    return json.loads(path.read_text())


def load_reference_image(path: Path) -> types.Image:
    if not path.exists():
        raise SystemExit(
            f"Character reference image not found: {path}\n"
            f"Generate it with nano banana / your image tool and save it there, "
            f"or pass --character-reference PATH to point at a different file."
        )
    suffix = path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp"}.get(suffix.lstrip("."), "image/png")
    return types.Image(
        image_bytes=path.read_bytes(),
        mime_type=mime,
    )


def build_prompt(beat: dict, shot_list: dict, style: str) -> str:
    """Assemble the Veo prompt from the beat's scene_prompt + continuity fields.

    The director's visual_style field is REPLACED here by the chosen style's
    enforcer, because the director is still writing Infocom-painterly
    descriptions by default — if we keep the original visual_style AND add a
    cinematic enforcer, they conflict. The scene_prompt still contains a
    couple of painterly phrases that we cannot strip safely, but the
    enforcer being last (and much longer) should dominate.

    STYLE_ENFORCER is appended last because Veo weights the tail of the
    prompt most heavily.
    """
    enforcer = STYLE_ENFORCERS[style]
    parts = [
        beat["scene_prompt"],
        "",
        f"The character in this shot: {shot_list['base_character']} "
        f"{beat['carried_items']}",
        "",
        enforcer,
    ]
    return "\n".join(parts)


def pick_beat(shot_list: dict, beat_index: int) -> dict:
    beats = shot_list["beats"]
    match = [b for b in beats if b["beat_index"] == beat_index]
    if not match:
        available = [b["beat_index"] for b in beats]
        raise SystemExit(
            f"Beat {beat_index} not found in shot list. Available: {available}"
        )
    return match[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="e.g. ep98")
    parser.add_argument("--beat-index", type=int, required=True,
                        help="Beat number to render (1-based)")
    parser.add_argument("--resolution", default="720p", choices=["720p", "1080p"])
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt and cost estimate, don't call the API")
    parser.add_argument("--out-dir", type=Path, default=RECAPS_DIR)
    parser.add_argument(
        "--character-reference",
        type=Path,
        default=CHARACTER_REFERENCE,
        help="Path to the character reference image (default: data/recaps/character_reference.png)",
    )
    parser.add_argument(
        "--style",
        choices=sorted(STYLE_ENFORCERS.keys()),
        default="cinematic",
        help="Visual style enforcer to append to the prompt (default: cinematic)",
    )
    args = parser.parse_args()

    shot_list = load_shot_list(args.episode_id)
    beat = pick_beat(shot_list, args.beat_index)

    # Clamp duration to Veo's 8s max, warn if truncated
    requested_duration = beat["duration_seconds"]
    duration = min(requested_duration, MAX_DURATION_SECONDS)
    if duration < requested_duration:
        print(
            f"  ⚠ Beat duration {requested_duration}s exceeds Veo's {MAX_DURATION_SECONDS}s "
            f"cap — clamping. Fix the director schema to cap at 8s.",
            file=sys.stderr,
        )

    prompt = build_prompt(beat, shot_list, args.style)
    cost = duration * PRICE_PER_SECOND[args.resolution]

    print("=" * 72, file=sys.stderr)
    print(f"Episode:     {args.episode_id}", file=sys.stderr)
    print(f"Beat:        {args.beat_index}/{len(shot_list['beats'])} — {beat['title']}", file=sys.stderr)
    print(f"Turn range:  {beat['turn_range']}", file=sys.stderr)
    print(f"Duration:    {duration}s  (requested {requested_duration}s)", file=sys.stderr)
    print(f"Resolution:  {args.resolution}", file=sys.stderr)
    print(f"Style:       {args.style}", file=sys.stderr)
    print(f"Reference:   {args.character_reference.name}", file=sys.stderr)
    print(f"Model:       {MODEL_ID}", file=sys.stderr)
    print(f"Cost est:    ${cost:.3f}", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print(f"\nPROMPT:\n{prompt}\n", file=sys.stderr)
    print("=" * 72, file=sys.stderr)

    if args.dry_run:
        print("\n(--dry-run — not calling the API)", file=sys.stderr)
        return 0

    # --- live path ---
    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    # Note on image conditioning: the Gemini API does NOT support
    # `reference_images` (that's Vertex-only). It DOES support first-frame
    # image-to-video via the top-level `image=` parameter. We pass the
    # character reference PNG as the starting frame, and Veo animates
    # forward from it. A better approach for future work is to pre-generate
    # a scene-specific first-frame image per beat (nano banana) and use
    # THAT as the starting frame — same cost for the video call, much
    # better framing.
    #
    # Similarly, `generate_audio` is Vertex-AI-only. On the Gemini API,
    # Veo 3.1's audio generation is always-on and the parameter is rejected.
    # Gemini API rejects `negative_prompt`, `reference_images`, and
    # `generate_audio` — all three are Vertex-AI-only. All our style
    # steering must happen inside the positive `prompt` via STYLE_ENFORCER.
    config = types.GenerateVideosConfig(
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        duration_seconds=duration,
        number_of_videos=1,
    )

    print(f"\nCharacter reference: {args.character_reference}", file=sys.stderr)
    print("Submitting video generation request...", file=sys.stderr)
    operation = client.models.generate_videos(
        model=MODEL_ID,
        prompt=prompt,
        image=load_reference_image(args.character_reference),
        config=config,
    )
    print(f"Operation: {operation.name if hasattr(operation, 'name') else '(submitted)'}", file=sys.stderr)

    start = time.time()
    while not operation.done:
        elapsed = int(time.time() - start)
        if elapsed > POLL_TIMEOUT_SECONDS:
            raise SystemExit(f"Polling timed out after {elapsed}s")
        print(f"  [{elapsed:>3}s] generating...", file=sys.stderr)
        time.sleep(POLL_INTERVAL_SECONDS)
        operation = client.operations.get(operation)

    elapsed = int(time.time() - start)
    print(f"  [{elapsed}s] complete.", file=sys.stderr)

    # Error check
    if hasattr(operation, "error") and operation.error:
        raise SystemExit(f"Generation failed: {operation.error}")

    response = operation.response
    if not response or not getattr(response, "generated_videos", None):
        raise SystemExit(f"No video in response: {response}")

    generated = response.generated_videos[0]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.episode_id}.beat{args.beat_index:02d}.{args.style}.mp4"

    print(f"\nDownloading to {out_path}...", file=sys.stderr)
    client.files.download(file=generated.video)
    generated.video.save(str(out_path))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Saved {size_mb:.1f} MB -> {out_path}", file=sys.stderr)
    print(f"Open it: open {out_path}", file=sys.stderr)
    print(f"\nActual cost: ${cost:.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
