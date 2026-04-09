#!/usr/bin/env python3
"""Generate a character reference image for the ZorkBurr recap franchise.

Uses Gemini 2.5 Flash Image ("nano banana") via the Google AI Studio API to
produce a canonical portrait of the adventurer in one of several visual
styles. Saves to data/recaps/character_reference_<style>.png.

The reference is a ONE-TIME franchise commitment — generate it once, then
reuse the same PNG across every episode's video generation via:

    uv run scripts/generate_recap_video.py \
        --character-reference data/recaps/character_reference_<style>.png \
        --episode-id epNNN --beat-index N

Usage:
    uv run scripts/generate_character_reference.py --style cinematic
    uv run scripts/generate_character_reference.py --style spiderverse
    uv run scripts/generate_character_reference.py --style cinematic --variations 4
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

RECAPS_DIR = Path(__file__).parent.parent / "data" / "recaps"
MODEL_ID = "nano-banana-pro-preview"

# ---------------------------------------------------------------------------
# Style prompts — each describes the adventurer in a specific visual register.
# All share the same base silhouette (cloak, hood, empty hands) so the
# character is recognisable as "the ZorkBurr adventurer" across any style.
# ---------------------------------------------------------------------------

STYLE_PROMPTS = {
    "cinematic": """Character reference sheet for a cinematic fantasy video project. Single full-body hero portrait of a lone adventurer standing in a three-quarter pose, facing slightly off-camera to the left. Full-body framing, feet to crown, character positioned slightly left-of-centre in the frame with environmental space on the right.

The adventurer wears a worn brown traveling cloak with the hood raised. The face is half-concealed in the deep shadow of the hood — jaw visible, set with quiet determination; upper face and eyes lost in darkness. Medium human build. The cloak is rough hand-spun wool, weathered and patched, hanging to mid-shin. Beneath it, a simple dark wool tunic and heavy trousers. Mud-caked leather boots, scuffed and travel-worn.

This is the adventurer at the very beginning of their journey — empty hands, no weapons, no lantern, no bag, no belt pouches, nothing attached to the belt, nothing on the back. Hands hang loosely at the sides, clearly visible and clearly empty.

Style: cinematic fantasy realism in the register of The Witcher (Netflix series), Game of Thrones, or a AAA action RPG cutscene. Photorealistic rendering with physical materials — the wool cloak has visible fibers and weave, the leather boots show grain and scuffing, the skin of the jaw shows faint stubble and the soft shadow of the hood's interior. Grimdark colour grading: desaturated earth tones, muted greens and umbers in the background, a single warm key light from the upper left casting the adventurer's right side in amber and leaving the left side in cold blue shadow.

Background: a suggestion of dim forest edge or stone path at dusk, heavily out-of-focus, so the character reads cleanly against it. Shot on a virtual cinema camera with a 35mm equivalent lens, shallow depth of field, natural light. Reminiscent of promotional stills for prestige fantasy television.

No text, logos, watermarks, or UI elements. 16:9 landscape aspect ratio.""",

    "spiderverse": """Character reference sheet in the visual style of Spider-Man: Into the Spider-Verse and Across the Spider-Verse — stylised cel-shaded 3D animation rendered to look like a moving comic book. Single full-body portrait of a lone adventurer in a three-quarter hero pose, facing slightly off-camera to the left. 16:9 landscape framing, character positioned left-of-centre with environmental space on the right.

The adventurer wears a worn brown traveling cloak with the hood raised. The face is half-concealed in the deep shadow of the hood — jaw visible and set with quiet determination; upper face in darkness. Medium human build. Cloak of hand-spun wool hanging to mid-shin over a dark tunic and trousers. Mud-caked leather boots.

This is the adventurer at the very beginning of their journey — empty hands, no weapons, no lantern, no bag, no belt pouches, no visible gear. Hands hang empty at the sides.

Style: cel-shaded 3D animation in the Spider-Verse aesthetic. Thick black ink outlines around the character and major shapes. Flat shaded colour regions — not gradients, but distinct steps of light and shadow. Visible halftone dot patterns in the mid-tones, giving a printed-comic feel. Slight chromatic aberration on high-contrast edges, with faint cyan and magenta fringes. Bold, saturated colours: burnt orange and warm amber for the cloak highlights, deep purple and navy blue for shadows, a touch of magenta in the sky. Action-comic energy even in a static pose — slightly dynamic lines of the cloak, a sense of imminent motion. Frame-rate feel of stop-motion, as though hand-posed.

Background: a simple stylised forest-edge or stone path, flat colour blocks, thick outlines, no photoreal detail. Like a comic-book panel background — suggestive, not literal.

No text, no UI, no watermarks. 16:9 landscape aspect ratio.""",
}


def load_api_key() -> str:
    for key in ("GOOGLE_AI_STUDIO", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        val = os.environ.get(key)
        if val:
            return val
    raise SystemExit(
        "No Google AI Studio API key found. Set GOOGLE_AI_STUDIO in .env."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--style",
        required=True,
        choices=sorted(STYLE_PROMPTS.keys()),
        help="Visual style to generate",
    )
    parser.add_argument(
        "--variations",
        type=int,
        default=1,
        help="Number of variations to request (saves as _01.png, _02.png, ...)",
    )
    parser.add_argument("--out-dir", type=Path, default=RECAPS_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    prompt = STYLE_PROMPTS[args.style]

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    print(f"Generating {args.variations} variation(s) of character_reference_{args.style}", file=sys.stderr)
    print(f"Model: {MODEL_ID}", file=sys.stderr)
    print("=" * 72, file=sys.stderr)

    saved: list[Path] = []
    for i in range(1, args.variations + 1):
        print(f"\n[{i}/{args.variations}] requesting...", file=sys.stderr)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        # Extract image bytes from response
        image_bytes = None
        for cand in response.candidates:
            for part in cand.content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    image_bytes = inline.data
                    break
            if image_bytes:
                break

        if not image_bytes:
            print(f"  [warn] no image in response for variation {i}", file=sys.stderr)
            continue

        suffix = f"_{i:02d}" if args.variations > 1 else ""
        out_path = args.out_dir / f"character_reference_{args.style}{suffix}.png"
        out_path.write_bytes(image_bytes)
        size_kb = out_path.stat().st_size / 1024
        print(f"  saved {size_kb:.0f} KB -> {out_path}", file=sys.stderr)
        saved.append(out_path)

    if not saved:
        raise SystemExit("No images were saved.")

    print("\n" + "=" * 72, file=sys.stderr)
    print(f"Done. {len(saved)} image(s) saved.", file=sys.stderr)
    print("\nTo use as video reference:", file=sys.stderr)
    print(f"  uv run scripts/generate_recap_video.py \\", file=sys.stderr)
    print(f"      --episode-id ep98 --beat-index 6 \\", file=sys.stderr)
    print(f"      --character-reference {saved[0]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
