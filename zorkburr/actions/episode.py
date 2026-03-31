"""Episode lifecycle: initialization and finalization."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from burr.core import State

from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.game.map_graph import MapGraph
from zorkburr.state import S

logger = logging.getLogger(__name__)


def initialize_episode(
    jericho: JerichoInterface,
    config: GameConfig,
    episode_number: int = 1,
) -> dict:
    """Load persisted data for cross-episode learning.

    Returns a dict of state overrides to apply before the first turn.
    """
    overrides: dict = {}

    map_path = Path(config.map_file)
    if map_path.exists():
        try:
            mg = MapGraph.from_dict(json.loads(map_path.read_text()))
            overrides["map_data"] = mg.to_dict()
            logger.info(f"Loaded map with {len(mg.rooms)} rooms")
        except Exception as e:
            logger.warning(f"Failed to load map: {e}")

    kb_path = Path(config.knowledge_file)
    if kb_path.exists():
        try:
            overrides["knowledge_base"] = kb_path.read_text()
            logger.info("Loaded knowledge base")
        except Exception as e:
            logger.warning(f"Failed to load knowledge base: {e}")

    # Room memories are stored as JSON (dict keyed by location_id)
    mem_path = Path(config.memory_file)
    if mem_path.exists():
        try:
            overrides["memories_by_location"] = json.loads(mem_path.read_text())
            total = sum(len(v) for v in overrides["memories_by_location"].values())
            logger.info(f"Loaded {total} memories across {len(overrides['memories_by_location'])} locations")
        except Exception as e:
            logger.warning(f"Failed to load memories: {e}")

    return overrides


def finalize_episode(state: State, config: GameConfig) -> dict:
    """Save map and knowledge to disk for cross-episode persistence.

    Returns an episode summary dict.
    """
    if state[S.MAP_DATA]:
        map_path = Path(config.map_file)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(state[S.MAP_DATA], indent=2))
        logger.info(f"Saved map to {map_path}")

    if state[S.KNOWLEDGE_BASE]:
        kb_path = Path(config.knowledge_file)
        kb_path.parent.mkdir(parents=True, exist_ok=True)
        kb_path.write_text(state[S.KNOWLEDGE_BASE])
        logger.info(f"Saved knowledge to {kb_path}")

    if state[S.MEMORIES_BY_LOCATION]:
        mem_path = Path(config.memory_file)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        mem_path.write_text(json.dumps(state[S.MEMORIES_BY_LOCATION], indent=2))
        total = sum(len(v) for v in state[S.MEMORIES_BY_LOCATION].values())
        logger.info(f"Saved {total} memories to {mem_path}")

    return {
        "episode_id": state[S.EPISODE_ID],
        "turns": state[S.TURN_COUNT],
        "score": state[S.SCORE],
        "max_score": state[S.MAX_SCORE],
        "reason": state[S.GAME_OVER_REASON],
    }
