"""Main entry point: run ZorkBurr episodes."""
from __future__ import annotations

import argparse
import logging
import sys

from zorkburr.actions.episode import finalize_episode, initialize_episode
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.llm.mlx_server import MlxServer
from zorkburr.state import S

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("zorkburr")


def run_episode(
    config: GameConfig,
    jericho: JerichoInterface,
    client,
    episode_number: int,
) -> dict:
    """Run a single episode and return a summary dict."""
    jericho.start()
    logger.info(f"=== Episode {episode_number} starting ===")

    overrides = initialize_episode(jericho, config, episode_number)

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=client,
        episode_id=f"ep-{episode_number}",
        tracker="local",
    )

    if overrides:
        app._state = app.state.update(**overrides)

    state = app.state
    try:
        while True:
            action_obj, result, state = app.step()
            if action_obj.name == "execute_action":
                turn = state[S.TURN_COUNT]
                if turn % 10 == 0 or turn <= 3:
                    logger.info(
                        f"Turn {turn} | Score: {state[S.SCORE]} "
                        f"| Location: {state[S.LOCATION_NAME]}"
                    )
            if state[S.GAME_OVER]:
                logger.info(f"Game over: {state[S.GAME_OVER_REASON]}")
                break
            if state[S.TURN_COUNT] >= config.max_turns_per_episode:
                logger.info("Max turns reached")
                break
            if (
                state[S.TURNS_SINCE_PROGRESS] >= config.max_turns_stuck
                and state[S.TURN_COUNT] % config.stuck_check_interval == 0
            ):
                logger.info("Stuck — ending episode")
                break
    except KeyboardInterrupt:
        logger.info("Interrupted")

    return finalize_episode(state, config)


def _run_episodes(config: GameConfig, args: argparse.Namespace) -> None:
    client = create_llm_client(config)
    for ep in range(1, args.episodes + 1):
        with JerichoInterface(config.game_file) as jericho:
            summary = run_episode(config, jericho, client, ep)
            print(f"\nEpisode {ep}: {summary}")
    print("\nBurr tracking: run 'burr' to view at http://localhost:7241")


def main():
    parser = argparse.ArgumentParser(description="ZorkBurr: AI Zork Player")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=None)
    args = parser.parse_args()

    config = GameConfig()
    if args.max_turns:
        config.max_turns_per_episode = args.max_turns

    if not config.use_local_models and (
        not config.openrouter_api_key or config.openrouter_api_key == "your-key-here"
    ):
        print("Set OPENROUTER_API_KEY in .env (or set use_local_models = true)")
        sys.exit(1)

    if config.use_local_models:
        with MlxServer(config):
            _run_episodes(config, args)
    else:
        _run_episodes(config, args)


if __name__ == "__main__":
    main()
