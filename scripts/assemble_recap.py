#!/usr/bin/env python3
"""Assemble per-beat Veo clips + narration mp3 into a final ZorkBurr recap mp4.

Takes all epNNN.beatNN.<style>.mp4 files for an episode, concatenates them in
beat order using ffmpeg's concat demuxer, then mixes the narration mp3 on top
of the concatenated ambient audio (ambient ducked to ~25%, narration at full
volume). Output: data/recaps/epNNN.final.<style>.mp4.

Prerequisites:
  1. Shot list exists at data/recaps/epNNN.shotlist.json
  2. Per-beat clips exist (run scripts/generate_recap_video.py --all-beats)
  3. Narration mp3 exists (run scripts/render_recap_audio.py)
  4. ffmpeg is installed (brew install ffmpeg)

Usage:
    uv run scripts/assemble_recap.py --episode-id ep98
    uv run scripts/assemble_recap.py --episode-id ep98 --style cinematic
    uv run scripts/assemble_recap.py --episode-id ep98 --ambient-volume 0.20
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RECAPS_DIR = Path(__file__).parent.parent / "data" / "recaps"


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ffmpeg not found on PATH. Install with: brew install ffmpeg"
        )


def find_beat_clips(episode_id: str, style: str, recaps_dir: Path) -> list[Path]:
    """Return per-beat mp4s sorted by beat index."""
    pattern = f"{episode_id}.beat*.{style}.mp4"
    clips = sorted(recaps_dir.glob(pattern))
    if not clips:
        raise SystemExit(
            f"No beat clips found matching {recaps_dir / pattern}\n"
            f"Run: uv run scripts/generate_recap_video.py "
            f"--episode-id {episode_id} --all-beats --style {style}"
        )
    return clips


def run_ffmpeg(args: list[str]) -> None:
    """Run ffmpeg, surfacing errors clearly."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"ffmpeg failed with exit code {result.returncode}")
    if result.stderr.strip():
        # Pass through any warnings even on success
        print(result.stderr.strip(), file=sys.stderr)


def normalize_clip(
    input_path: Path,
    output_path: Path,
    pad_seconds: float,
) -> None:
    """Re-encode a clip to a uniform profile, optionally freeze-padding its tail.

    Every beat clip is pushed through this in Option B, whether or not it
    needs padding, so the concat demuxer downstream sees identical codec
    params across all clips. When pad_seconds > 0, the last video frame is
    cloned for that long and the audio is silence-padded to match.
    """
    vf_parts = []
    af_parts = []
    if pad_seconds > 0:
        vf_parts.append(f"tpad=stop_mode=clone:stop_duration={pad_seconds}")
        af_parts.append(f"apad=pad_dur={pad_seconds}")
    vf = ",".join(vf_parts) if vf_parts else "null"
    af = ",".join(af_parts) if af_parts else "anull"
    run_ffmpeg([
        "-i", str(input_path),
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ])


def concat_videos(clips: list[Path], out_path: Path) -> None:
    """Concatenate clips losslessly using the concat demuxer.

    Requires all input clips to have matching codec / resolution / framerate,
    which Veo 3.1 Lite produces consistently.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, dir=out_path.parent
    ) as listfile:
        for clip in clips:
            # Concat demuxer requires POSIX-style paths inside the list file
            listfile.write(f"file '{clip.name}'\n")
        list_path = Path(listfile.name)

    try:
        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(out_path),
        ])
    finally:
        list_path.unlink(missing_ok=True)


def mix_narration(
    video_path: Path,
    narration_path: Path,
    out_path: Path,
    ambient_volume: float,
) -> None:
    """Mix a narration mp3 over the video's ambient audio.

    The ambient track is attenuated by `ambient_volume` (0.0 = silent,
    1.0 = original) so the narration sits clearly on top of the Veo-generated
    ambient bed. The final audio duration is the *longest* of the two — if
    the narration is shorter than the video, the tail will be pure ambient.
    """
    filter_complex = (
        f"[0:a]volume={ambient_volume}[ambient];"
        f"[ambient][1:a]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
    )
    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(narration_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="e.g. ep98")
    parser.add_argument("--style", default="cinematic",
                        help="Style suffix of the beat clips (default: cinematic)")
    parser.add_argument("--ambient-volume", type=float, default=0.25,
                        help="Multiplier applied to the Veo ambient track (default: 0.25)")
    parser.add_argument("--out-dir", type=Path, default=RECAPS_DIR)
    parser.add_argument("--narration",
                        type=Path, default=None,
                        help="Path to narration mp3 (default: data/recaps/epNNN.narration.mp3)")
    args = parser.parse_args()

    check_ffmpeg()

    clips = find_beat_clips(args.episode_id, args.style, args.out_dir)
    narration_path = args.narration or (args.out_dir / f"{args.episode_id}.narration.mp3")
    if not narration_path.exists():
        raise SystemExit(
            f"Narration not found: {narration_path}\n"
            f"Run: uv run scripts/render_recap_audio.py --episode-id {args.episode_id} --per-beat-sync"
        )

    # Option B: per-beat freeze padding. render_recap_audio.py (with
    # --per-beat-sync) writes a sidecar listing how long each beat's audio
    # actually is, which may exceed the beat's video duration. We freeze-pad
    # each clip individually so the narration lands inside its own shot.
    timings_path = args.out_dir / f"{args.episode_id}.beat_timings.json"
    if not timings_path.exists():
        raise SystemExit(
            f"Beat timings sidecar not found: {timings_path}\n"
            f"Run: uv run scripts/render_recap_audio.py --episode-id {args.episode_id} --per-beat-sync"
        )
    timings = json.loads(timings_path.read_text())
    timings_by_idx = {b["beat_index"]: b for b in timings["beats"]}

    # Pair each clip to its timing entry by beat index
    def clip_beat_index(clip: Path) -> int:
        # ep98.beat03.cinematic.mp4 -> 3
        stem = clip.name.split(".")[1]  # "beat03"
        return int(stem.replace("beat", ""))

    narration_duration = probe_duration(narration_path)
    print("=" * 72, file=sys.stderr)
    print(f"Episode:       {args.episode_id}", file=sys.stderr)
    print(f"Style:         {args.style}", file=sys.stderr)
    print(f"Beat clips:    {len(clips)}", file=sys.stderr)
    total_target = 0.0
    for c in clips:
        idx = clip_beat_index(c)
        t = timings_by_idx.get(idx, {})
        vdur = probe_duration(c)
        adur = t.get("audio_duration", vdur)
        pad = max(0.0, adur - vdur)
        total_target += adur
        marker = f"  +{pad:4.1f}s pad" if pad > 0.05 else ""
        print(f"  video {vdur:5.1f}s  audio {adur:5.1f}s{marker}  {c.name}",
              file=sys.stderr)
    print(f"Total target:  {total_target:.1f}s", file=sys.stderr)
    print(f"Narration:     {narration_duration:.1f}s  ({narration_path.name})", file=sys.stderr)
    print(f"Ambient level: {args.ambient_volume:.0%}", file=sys.stderr)
    print("=" * 72, file=sys.stderr)

    # Step 1: normalize + freeze-pad each beat clip individually
    print("\n[1/3] normalizing and per-beat freeze-padding...", file=sys.stderr)
    normalized_clips: list[Path] = []
    for c in clips:
        idx = clip_beat_index(c)
        t = timings_by_idx.get(idx)
        vdur = probe_duration(c)
        if t is None:
            pad_seconds = 0.0
        else:
            pad_seconds = max(0.0, t["audio_duration"] - vdur)
        out_clip = args.out_dir / f"{args.episode_id}.beat{idx:02d}.{args.style}.padded.mp4"
        normalize_clip(c, out_clip, pad_seconds)
        normalized_clips.append(out_clip)
        print(f"  [beat {idx}] +{pad_seconds:.1f}s -> {out_clip.name}",
              file=sys.stderr)

    # Step 2: concat the normalized clips (all share codec params now)
    print("\n[2/3] concatenating padded clips...", file=sys.stderr)
    concat_path = args.out_dir / f"{args.episode_id}.concat.{args.style}.mp4"
    concat_videos(normalized_clips, concat_path)
    print(f"  -> {concat_path.name}", file=sys.stderr)

    # Step 3: mix narration
    print("\n[3/3] mixing narration over ambient...", file=sys.stderr)
    final_path = args.out_dir / f"{args.episode_id}.final.{args.style}.mp4"
    mix_narration(
        video_path=concat_path,
        narration_path=narration_path,
        out_path=final_path,
        ambient_volume=args.ambient_volume,
    )

    # Clean up intermediates
    concat_path.unlink(missing_ok=True)
    for nc in normalized_clips:
        nc.unlink(missing_ok=True)

    final_duration = probe_duration(final_path)
    final_size_mb = final_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 72, file=sys.stderr)
    print(f"Done. {final_duration:.1f}s, {final_size_mb:.1f} MB", file=sys.stderr)
    print(f"  -> {final_path}", file=sys.stderr)
    print(f"\nOpen it: open {final_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
