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
            # Prune ephemeral memories from prior episodes
            raw_mems = overrides["memories_by_location"]
            cleaned = {}
            dropped = 0
            for loc_key, mems in raw_mems.items():
                kept = [m for m in mems if m.get("persistence") != "ephemeral"]
                dropped += len(mems) - len(kept)
                if kept:
                    cleaned[loc_key] = kept
            overrides["memories_by_location"] = cleaned
            if dropped:
                logger.info(f"Pruned {dropped} ephemeral memories from previous episodes")
        except Exception as e:
            logger.warning(f"Failed to load memories: {e}")

    return overrides


def persist_map(map_data: dict, config: GameConfig) -> None:
    """Write map data to disk. Called after every map update."""
    if not map_data:
        return
    path = Path(config.map_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(map_data, indent=2))
    logger.debug(f"Persisted map to {path}")


def persist_memories(memories: dict, config: GameConfig) -> None:
    """Write memories to disk. Called after every new memory."""
    if not memories:
        return
    path = Path(config.memory_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memories, indent=2))
    total = sum(len(v) for v in memories.values())
    logger.debug(f"Persisted {total} memories to {path}")


def persist_knowledge(knowledge: str, config: GameConfig) -> None:
    """Write knowledge base to disk. Called after every knowledge update."""
    if not knowledge:
        return
    path = Path(config.knowledge_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(knowledge)
    logger.debug(f"Persisted knowledge to {path}")


def finalize_episode(state: State, config: GameConfig, client=None) -> dict:
    """Save map and knowledge to disk for cross-episode persistence.

    If *client* is provided, regenerates the KB with full episode data
    before persisting so that gameplay after the last periodic update
    is captured.

    Returns an episode summary dict.
    """
    if client is not None:
        try:
            from zorkburr.actions.knowledge import update_knowledge
            _, state = update_knowledge.run(state, client=client, config=config, use_thinking=False)
        except Exception:
            logger.warning("Final KB update failed; persisting existing KB")

    persist_map(state[S.MAP_DATA], config)
    persist_knowledge(state[S.KNOWLEDGE_BASE], config)
    persist_memories(state[S.MEMORIES_BY_LOCATION], config)

    return {
        "episode_id": state[S.EPISODE_ID],
        "turns": state[S.TURN_COUNT],
        "score": state[S.SCORE],
        "max_score": state[S.MAX_SCORE],
        "reason": state[S.GAME_OVER_REASON],
    }
