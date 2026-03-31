#!/usr/bin/env python3
"""Run a single ZorkBurr episode with parseable stdout output for orchestrator monitoring."""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def format_turn_line(
    turn_num: int,
    loc: str,
    score: int,
    max_score: int,
    critic: float,
    rejections: int,
    action: str,
) -> str:
    safe_loc = loc.replace(" ", "_") or "unknown"
    return (
        f"TURN {turn_num} | loc={safe_loc} | score={score}/{max_score} | "
        f"critic={critic:.2f} | rejections={rejections} | action={action}"
    )


def format_episode_end(
    turns: int,
    score: int,
    max_score: int,
    locations: int,
    objectives_found: int,
    reason: str,
) -> str:
    return (
        f"EPISODE_END | turns={turns} | score={score}/{max_score} | "
        f"locations={locations} | objectives_found={objectives_found} | reason={reason}"
    )
