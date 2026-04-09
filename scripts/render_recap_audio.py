#!/usr/bin/env python3
"""Render a ZorkBurr episode recap shot list as spoken audio.

Reads a shot list produced by scripts/generate_recap_script.py, concatenates
the narration lines with natural pauses between beats, and produces an mp3 of
the full recap so you can hear whether the Attenborough writing works out
loud *before* investing in real TTS or video generation.

Provider selection (auto-detected in this order, or pass --provider):
    1. elevenlabs   — if ELEVENLABS_API_KEY is set (best quality)
    2. openai       — if OPENAI_API_KEY is set (decent British voice: "fable")
    3. say          — macOS built-in, zero cost (default voice: "Daniel")

Usage:
    uv run scripts/render_recap_audio.py --episode-id ep98
    uv run scripts/render_recap_audio.py --episode-id ep98 --voice Grandpa
    uv run scripts/render_recap_audio.py --episode-id ep98 --provider openai
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RECAPS_DIR = Path(__file__).parent.parent / "data" / "recaps"

# Provider defaults
DEFAULT_SAY_VOICE = "Daniel"          # classic British male, closest free Attenborough
DEFAULT_OPENAI_VOICE = "fable"        # OpenAI's British-accented voice
DEFAULT_ELEVENLABS_VOICE = "George"   # warm low British male on ElevenLabs

# Pause between beats, in seconds. Gives the listener a beat-break rhythm.
BEAT_PAUSE_SECONDS = 0.6


# ---------------------------------------------------------------------------
# Script assembly
# ---------------------------------------------------------------------------

def assemble_narration(shot_list: dict) -> tuple[str, list[str]]:
    """Return (full_script_with_pauses, list_of_beat_lines).

    The full script uses double-newlines between beats, which `say` and most
    TTS engines interpret as a natural pause. For ElevenLabs we also have a
    per-beat list so we can control pacing more precisely.

    Note: `final_score_stinger` is display text for the end title card, NOT
    spoken narration. The spoken version of the score lives inside the
    closing beat's narration (the director is instructed to spell numbers
    out there). We do not append the stinger to the spoken text.
    """
    beats = shot_list["beats"]
    lines = [b["narration"].strip() for b in beats]
    full = "\n\n".join(lines)
    return full, lines


def pick_provider(requested: str | None) -> str:
    if requested:
        return requested
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "say"


# ---------------------------------------------------------------------------
# Provider: macOS `say` (zero-cost fallback)
# ---------------------------------------------------------------------------

def render_with_say(text: str, voice: str, out_path: Path) -> None:
    """Use macOS `say` to produce an aiff, then ffmpeg to mp3."""
    if shutil.which("say") is None:
        raise SystemExit("macOS `say` command not found — this provider only works on macOS.")
    aiff_path = out_path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", voice, "-r", "155", "-o", str(aiff_path), text],
        check=True,
    )
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff_path),
             "-codec:a", "libmp3lame", "-qscale:a", "2", str(out_path)],
            check=True,
        )
        aiff_path.unlink()
    else:
        # No ffmpeg — leave the aiff in place and redirect out_path
        print("  (ffmpeg not found — leaving .aiff instead of .mp3)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Provider: OpenAI TTS
# ---------------------------------------------------------------------------

def render_with_openai(text: str, voice: str, out_path: Path) -> None:
    from openai import OpenAI
    client = OpenAI()
    # tts-1-hd is higher quality; tts-1 is faster/cheaper
    with client.audio.speech.with_streaming_response.create(
        model="tts-1-hd",
        voice=voice,
        input=text,
    ) as response:
        response.stream_to_file(out_path)


# ---------------------------------------------------------------------------
# Provider: ElevenLabs
# ---------------------------------------------------------------------------

def render_with_elevenlabs(text: str, voice: str, out_path: Path) -> None:
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError:
        raise SystemExit(
            "elevenlabs package not installed. Run: pip install elevenlabs"
        )
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    audio = client.text_to_speech.convert(
        voice_id=voice,
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
    )
    with open(out_path, "wb") as fh:
        for chunk in audio:
            if chunk:
                fh.write(chunk)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="e.g. ep98")
    parser.add_argument(
        "--provider",
        choices=["say", "openai", "elevenlabs"],
        default=None,
        help="TTS provider (auto-detect if omitted)",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Voice name/ID. Defaults depend on provider. "
             "say: Daniel/Grandpa. openai: fable/onyx. elevenlabs: George/Brian.",
    )
    parser.add_argument("--out-dir", type=Path, default=RECAPS_DIR)
    args = parser.parse_args()

    shotlist_path = args.out_dir / f"{args.episode_id}.shotlist.json"
    if not shotlist_path.exists():
        raise SystemExit(
            f"Shot list not found: {shotlist_path}\n"
            f"Run: uv run scripts/generate_recap_script.py --episode-id {args.episode_id}"
        )
    shot_list = json.loads(shotlist_path.read_text())

    full_text, beat_lines = assemble_narration(shot_list)

    # Write the spoken script to a .txt for quick review
    script_path = args.out_dir / f"{args.episode_id}.narration.txt"
    script_path.write_text(full_text + "\n")
    word_count = sum(len(line.split()) for line in beat_lines)
    target_secs = shot_list.get("total_duration_seconds", 0)
    print(f"Wrote narration script -> {script_path}", file=sys.stderr)
    print(f"  {len(beat_lines)} lines, {word_count} words, target {target_secs}s "
          f"(~{word_count / 2.5:.0f}s at 150 wpm)", file=sys.stderr)

    provider = pick_provider(args.provider)
    voice = args.voice or {
        "say": DEFAULT_SAY_VOICE,
        "openai": DEFAULT_OPENAI_VOICE,
        "elevenlabs": DEFAULT_ELEVENLABS_VOICE,
    }[provider]
    print(f"Rendering audio via provider={provider} voice={voice}...", file=sys.stderr)

    audio_path = args.out_dir / f"{args.episode_id}.narration.mp3"
    if provider == "say":
        render_with_say(full_text, voice, audio_path)
    elif provider == "openai":
        render_with_openai(full_text, voice, audio_path)
    elif provider == "elevenlabs":
        render_with_elevenlabs(full_text, voice, audio_path)

    if audio_path.exists():
        print(f"\nWrote audio -> {audio_path}", file=sys.stderr)
        print(f"Play it: open {audio_path}", file=sys.stderr)
    else:
        # `say` may have left an aiff if ffmpeg is missing
        aiff = audio_path.with_suffix(".aiff")
        if aiff.exists():
            print(f"\nWrote audio -> {aiff}", file=sys.stderr)
            print(f"Play it: open {aiff}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
