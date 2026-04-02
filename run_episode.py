#!/usr/bin/env python3
"""Run a single ZorkBurr episode with parseable stdout output for orchestrator monitoring."""
from __future__ import annotations

import argparse
from dotenv import load_dotenv

load_dotenv()  # Export .env vars (incl. AWS creds) to the environment for boto3
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from langfuse import observe, get_client, propagate_attributes

from zorkburr.actions.episode import finalize_episode, initialize_episode
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.llm.llama_server import LlamaServer
from zorkburr.state import S


_REASON_MAP = {
    "victory": "game_over_win",
    "death": "game_over_death",
}


def _resolve_end_reason(game_over_reason: str) -> str:
    return _REASON_MAP.get(game_over_reason, f"game_over_unknown:{game_over_reason}")


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
    memory_stats: dict | None = None,
) -> str:
    line = (
        f"EPISODE_END | turns={turns} | score={score}/{max_score} | "
        f"locations={locations} | objectives_found={objectives_found} | reason={reason}"
    )
    if memory_stats:
        mem_total = memory_stats.get("total", 0)
        mem_new = memory_stats.get("new", 0)
        mem_dedup = memory_stats.get("dedup_rejected", 0)
        mem_superseded = memory_stats.get("superseded", 0)
        mem_pruned = memory_stats.get("ephemeral_pruned", 0)
        mem_consolidated = memory_stats.get("mem_consolidated", 0)
        line += (
            f" | mem_total={mem_total} | mem_new={mem_new}"
            f" | mem_dedup_rejected={mem_dedup} | mem_superseded={mem_superseded}"
            f" | mem_ephemeral_pruned={mem_pruned} | mem_consolidated={mem_consolidated}"
        )
    return line


@observe()
def _run(config: GameConfig, max_turns: int, episode_id: str) -> None:
    jericho = JerichoInterface(config.game_file)
    jericho.start()
    client = create_llm_client(config)

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=client,
        episode_id=episode_id,
        tracker="local",
        persist=False,
    )

    # Load cross-episode learning (knowledge base, map) from prior episodes
    overrides = initialize_episode(jericho, config)
    if overrides:
        app._state = app.state.update(**overrides)

    locations_visited: set[str] = set()
    objectives_found = 0
    turn_num = 0
    end_reason = "max_turns"

    try:
        with propagate_attributes(
            trace_name=f"zorkburr-episode-{episode_id}",
            session_id=episode_id,
            user_id="zorkburr",
            metadata={
                "agent_model": config.agent_model,
                "critic_model": config.critic_model,
                "max_turns": str(max_turns),
            },
            tags=["zorkburr", "episode"],
        ):
            for action_obj, result, state in app.iterate(
                halt_after=["turn_complete"]
            ):
                if action_obj.name == "turn_complete":
                    end_reason = _resolve_end_reason(state[S.GAME_OVER_REASON])
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
                        end_reason = _resolve_end_reason(state[S.GAME_OVER_REASON])
                        objectives_found = len(state[S.DISCOVERED_OBJECTIVES])
                        break

                    if turn_num >= max_turns:
                        objectives_found = len(state[S.DISCOVERED_OBJECTIVES])
                        break
    finally:
        try:
            final_state = app.state
            # Save cross-episode learning (knowledge base, map) for future episodes
            summary = finalize_episode(final_state, config, client=client)

            # Compute memory stats for EPISODE_END
            mem_stats = dict(final_state.get(S.MEMORY_STATS, {}))
            all_mems = final_state.get(S.MEMORIES_BY_LOCATION, {})
            mem_stats["total"] = sum(len(v) for v in all_mems.values())
            mem_stats["ephemeral_pruned"] = overrides.get("ephemeral_pruned", 0)
            mem_stats["mem_consolidated"] = summary.get("mem_consolidated", 0)

            print(
                format_episode_end(
                    turns=turn_num,
                    score=final_state[S.SCORE],
                    max_score=final_state[S.MAX_SCORE],
                    locations=len(locations_visited),
                    objectives_found=objectives_found,
                    reason=end_reason,
                    memory_stats=mem_stats,
                ),
                flush=True,
            )
        finally:
            jericho.close()
            get_client().flush()


def run_episode(max_turns: int, episode_id: str) -> None:
    config = GameConfig()
    if config.use_local_models:
        with LlamaServer(config):
            _run(config, max_turns, episode_id)
    else:
        _run(config, max_turns, episode_id)


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
