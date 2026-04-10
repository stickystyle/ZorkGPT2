#!/usr/bin/env python3
"""Render a ZorkBurr episode recap shot list as spoken audio.

Reads a shot list produced by scripts/generate_recap_script.py and produces
an mp3 of the narration. Two modes:

Flat mode (default): concatenates all beat narrations into one TTS call,
producing a single mp3 of ~45-65s that you can listen to in isolation to
judge whether the Attenborough writing works out loud.

Per-beat-sync mode (--per-beat-sync): generates ONE TTS call per beat,
pads each to match the beat's video duration (lead-in silence + trailing
silence), and concatenates into a master mp3 that is timecode-aligned to
the video timeline. Beat N's narration plays DURING beat N's video. This
is what assemble_recap.py mixes over the concatenated video.

Provider selection (auto-detected in this order, or pass --provider):
    1. elevenlabs   — if ELEVENLABS_API_KEY is set (best quality)
    2. openai       — if OPENAI_API_KEY is set (decent British voice: "fable")
    3. say          — macOS built-in, zero cost (default voice: "Daniel")

Note: per-beat-sync mode currently only supports --provider openai.

Usage:
    uv run scripts/render_recap_audio.py --episode-id ep98
    uv run scripts/render_recap_audio.py --episode-id ep98 --per-beat-sync
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
# Per-beat sync mode
# ---------------------------------------------------------------------------

def probe_duration(path: Path) -> float:
    """Return duration in seconds, or 0.0 if ffprobe fails."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip() or 0)


def render_per_beat_sync(
    *,
    shot_list: dict,
    episode_id: str,
    provider: str,
    voice: str,
    out_path: Path,
    out_dir: Path,
    default_beat_duration: float,
    lead_in_seconds: float,
    style: str,
) -> None:
    """Generate per-beat TTS, pad to video beat durations, concatenate.

    For each beat:
      1. Call TTS with just that beat's narration (one API call per beat).
      2. If the beat's video file exists on disk, use its exact duration as
         the padding target. Otherwise fall back to default_beat_duration.
      3. Prepend lead_in_seconds of silence (so the narration doesn't start
         immediately on cut) and pad the tail to the beat's target duration.
      4. Truncate to the beat duration (safety clamp in case TTS ran long).
    Then concatenate all padded beat-audio files into the master mp3.
    """
    if provider != "openai":
        raise SystemExit(
            f"--per-beat-sync currently only supports --provider openai "
            f"(requested: {provider}). OpenAI TTS is cheap enough for per-beat "
            f"calls; ElevenLabs and `say` can be added later."
        )
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found — required for --per-beat-sync.")

    beats = shot_list["beats"]
    tmp_dir = out_dir / f".{episode_id}.audiotmp"
    tmp_dir.mkdir(exist_ok=True)

    padded_files: list[Path] = []
    beat_timings: list[dict] = []
    total_target = 0.0
    total_words = 0

    print(f"Generating {len(beats)} per-beat TTS clips...", file=sys.stderr)
    try:
        for i, beat in enumerate(beats):
            idx = beat["beat_index"]
            narration = beat["narration"].strip()
            words = len(narration.split())
            total_words += words

            # Determine the *video* duration from the beat file if it exists.
            # This is the floor — audio will never be shorter than video.
            video_path = out_dir / f"{episode_id}.beat{idx:02d}.{style}.mp4"
            if video_path.exists():
                video_duration = probe_duration(video_path)
                source = f"{video_path.name}"
            else:
                video_duration = default_beat_duration
                source = f"default ({default_beat_duration}s)"

            raw_path = tmp_dir / f"beat{idx:02d}.raw.mp3"
            padded_path = tmp_dir / f"beat{idx:02d}.padded.mp3"

            # Step 1: render the raw per-beat TTS first, so we know its true length
            render_with_openai(narration, voice, raw_path)
            raw_duration = probe_duration(raw_path)
            required = raw_duration + lead_in_seconds + 0.5  # 0.5s trailing silence

            # Option B: never truncate. Every beat auto-extends its target past
            # the video duration if the narration needs more time. assemble_recap.py
            # will freeze-frame each beat's video individually to match.
            target = max(video_duration, required)
            if target > video_duration + 0.05:
                print(
                    f"  [beat {idx}] {words} words, extending target from "
                    f"{video_duration:.1f}s (video) to {target:.1f}s (audio) "
                    f"({source})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  [beat {idx}] {words} words, target {target:.1f}s "
                    f"({source})",
                    file=sys.stderr,
                )

            total_target += target
            beat_timings.append({
                "beat_index": idx,
                "video_duration": round(video_duration, 3),
                "audio_duration": round(target, 3),
                "freeze_pad_seconds": round(max(0.0, target - video_duration), 3),
                "words": words,
            })

            # Step 2: pad with silence at the head + trail
            lead_ms = int(lead_in_seconds * 1000)
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(raw_path),
                 "-af", f"adelay={lead_ms}|{lead_ms},apad=whole_dur={target}",
                 "-t", str(target),
                 "-acodec", "libmp3lame", "-q:a", "2",
                 str(padded_path)],
                check=True,
            )
            padded_files.append(padded_path)

        # Concat all padded beats into the master
        list_path = tmp_dir / "concat.txt"
        with list_path.open("w") as fh:
            for p in padded_files:
                fh.write(f"file '{p.name}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0",
             "-i", str(list_path),
             "-c", "copy",
             str(out_path)],
            check=True,
        )

        # Write the sidecar manifest so assemble_recap.py knows how to pad
        # each beat video individually.
        timings_path = out_dir / f"{episode_id}.beat_timings.json"
        timings_path.write_text(json.dumps({
            "episode_id": episode_id,
            "style": style,
            "lead_in_seconds": lead_in_seconds,
            "total_audio_seconds": round(total_target, 3),
            "beats": beat_timings,
        }, indent=2) + "\n")
        print(f"Wrote beat timings -> {timings_path.name}", file=sys.stderr)

        master_dur = probe_duration(out_path)
        print(f"\nMaster narration: {master_dur:.1f}s "
              f"(target {total_target:.1f}s, {total_words} words total)",
              file=sys.stderr)
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_dir, ignore_errors=True)


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
    parser.add_argument("--per-beat-sync", action="store_true",
                        help="Generate one TTS call per beat and sync to beat "
                             "video durations (for final assembly). Requires --provider openai.")
    parser.add_argument("--beat-duration", type=float, default=8.0,
                        help="Fallback beat duration in seconds if the video "
                             "file isn't on disk yet (default: 8)")
    parser.add_argument("--lead-in-seconds", type=float, default=0.3,
                        help="Silence inserted at the start of each beat's "
                             "narration (default: 0.3)")
    parser.add_argument("--style", default="cinematic",
                        help="Style suffix used to find per-beat video files "
                             "for duration probing (default: cinematic)")
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
    print(f"Rendering audio via provider={provider} voice={voice}"
          f" (per_beat_sync={args.per_beat_sync})...", file=sys.stderr)

    audio_path = args.out_dir / f"{args.episode_id}.narration.mp3"
    if args.per_beat_sync:
        render_per_beat_sync(
            shot_list=shot_list,
            episode_id=args.episode_id,
            provider=provider,
            voice=voice,
            out_path=audio_path,
            out_dir=args.out_dir,
            default_beat_duration=args.beat_duration,
            lead_in_seconds=args.lead_in_seconds,
            style=args.style,
        )
    elif provider == "say":
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
