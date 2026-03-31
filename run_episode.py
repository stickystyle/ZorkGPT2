#!/usr/bin/env python3
"""Run a single ZorkBurr episode with parseable stdout output for orchestrator monitoring."""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.state import S


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


def run_episode(max_turns: int, episode_id: str) -> None:
    config = GameConfig()
    jericho = JerichoInterface(config.game_file)
    jericho.start()
    client = create_llm_client(config)

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=client,
        episode_id=episode_id,
        tracker=None,
        persist=False,
    )

    locations_visited: set[str] = set()
    objectives_found = 0
    turn_num = 0
    end_reason = "max_turns"

    try:
        for action_obj, result, state in app.iterate(
            halt_after=["execute_action", "turn_complete"]
        ):
            if action_obj.name == "turn_complete":
                end_reason = "game_over_win" if state[S.GAME_OVER_REASON] == "victory" else "game_over_death"
                objectives_found = len(state[S.DISCOVERED_OBJECTIVES])
                break

            if action_obj.name == "execute_action":
                turn_num = state[S.TURN_COUNT]
                loc = state[S.LOCATION_NAME]
                locations_visited.add(loc)

                print(
                    format_turn_line(
                        turn_num=turn_num,
                        loc=loc,
                        score=state[S.SCORE],
                        max_score=state[S.MAX_SCORE],
                        critic=state[S.CRITIC_SCORE],
                        rejections=state[S.REJECTION_COUNT],
                        action=state[S.ACTION_TO_TAKE],
                    ),
                    flush=True,
                )

                if state[S.GAME_OVER]:
                    end_reason = "game_over_win" if state[S.GAME_OVER_REASON] == "victory" else "game_over_death"
                    objectives_found = len(state[S.DISCOVERED_OBJECTIVES])
                    break

                if turn_num >= max_turns:
                    objectives_found = len(state[S.DISCOVERED_OBJECTIVES])
                    break
    finally:
        final_state = app.state
        print(
            format_episode_end(
                turns=turn_num,
                score=final_state[S.SCORE],
                max_score=final_state[S.MAX_SCORE],
                locations=len(locations_visited),
                objectives_found=objectives_found,
                reason=end_reason,
            ),
            flush=True,
        )
        jericho.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a ZorkBurr episode")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--episode-id", type=str, default=None)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    episode_id = args.episode_id or str(uuid.uuid4())[:8]
    run_episode(max_turns=args.max_turns, episode_id=episode_id)


if __name__ == "__main__":
    main()
