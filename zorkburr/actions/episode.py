"""Episode lifecycle: initialization and finalization."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from burr.core import State

from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.game.map_graph import MapGraph
from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse
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
                overrides["ephemeral_pruned"] = dropped
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


def apply_consolidation_actions(
    memories: list[dict],
    actions: list[ConsolidationAction],
) -> tuple[list[dict], dict]:
    """Apply consolidation actions to a location's memory list.

    Returns (updated_memories, stats_dict).
    """
    stats = {"kept": 0, "dropped": 0, "merged": 0, "superseded": 0}
    # Track which memories have been processed
    processed_titles: set[str] = set()
    result = list(memories)  # shallow copy

    for act in actions:
        if act.action == "keep":
            stats["kept"] += 1
            processed_titles.add(act.memory_title)

        elif act.action == "drop":
            result = [m for m in result if m.get("title") != act.memory_title]
            logger.warning(f"Consolidation dropped memory: {act.memory_title} — {act.reason}")
            stats["dropped"] += 1
            processed_titles.add(act.memory_title)

        elif act.action == "merge":
            # Mark both source memories as SUPERSEDED
            for m in result:
                if m.get("title") in (act.memory_title, act.merge_with) and m.get("status") != "SUPERSEDED":
                    m["status"] = "SUPERSEDED"
                    m["superseded_by"] = act.new_title
            # Create merged memory — category from the primary memory
            primary = next((m for m in memories if m.get("title") == act.memory_title), None)
            merged = {
                "category": primary.get("category", "NOTE") if primary else "NOTE",
                "title": act.new_title,
                "text": act.new_text,
                "episode": "consolidated",
                "turn": 0,
                "persistence": "permanent",
                "status": "ACTIVE",
                "superseded_by": "",
            }
            result.append(merged)
            logger.warning(
                f"Consolidation merged '{act.memory_title}' + '{act.merge_with}' -> '{act.new_title}' — {act.reason}"
            )
            stats["merged"] += 1
            processed_titles.add(act.memory_title)
            processed_titles.add(act.merge_with)

        elif act.action == "supersede":
            for m in result:
                if m.get("title") == act.memory_title and m.get("status") != "SUPERSEDED":
                    m["status"] = "SUPERSEDED"
                    m["superseded_by"] = act.merge_with
                    logger.info(f"Consolidation superseded '{act.memory_title}' by '{act.merge_with}' — {act.reason}")
            stats["superseded"] += 1
            processed_titles.add(act.memory_title)

    # Default-keep any non-superseded memories not mentioned in actions
    for m in result:
        if m.get("title") not in processed_titles and m.get("status") != "SUPERSEDED":
            stats["kept"] += 1

    return result, stats


_consolidation_prompt: str | None = None


def _get_consolidation_prompt() -> str:
    global _consolidation_prompt
    if _consolidation_prompt is None:
        from zorkburr.llm.prompts import load_prompt
        _consolidation_prompt = load_prompt("memory_consolidation")
    return _consolidation_prompt


def consolidate_location(
    location_id: str,
    memories: list[dict],
    knowledge_base: str,
    client: Any,
    config: GameConfig,
) -> tuple[list[dict], dict]:
    """Run consolidation LLM on one location's memories. Returns (updated_memories, stats)."""
    from zorkburr.llm.client import effective_model, thinking_kwargs

    # Build context: all memories with status markers
    mem_lines = []
    for m in memories:
        status_tag = " [SUPERSEDED]" if m.get("status") == "SUPERSEDED" else ""
        mem_lines.append(f"- [{m.get('title', '?')}]{status_tag}: {m.get('text', '')}")

    context = (
        f"Location ID: {location_id}\n\n"
        f"Memories:\n" + "\n".join(mem_lines) + "\n\n"
        f"Current Knowledge Base:\n{knowledge_base or '(empty)'}"
    )

    response: ConsolidationResponse = client.create(
        model=effective_model(config, config.analysis_model),
        response_model=ConsolidationResponse,
        messages=[
            {"role": "system", "content": _get_consolidation_prompt()},
            {"role": "user", "content": context},
        ],
        temperature=0.3, max_tokens=2048, max_retries=2,
        **thinking_kwargs(config, False),
    )

    return apply_consolidation_actions(memories, response.actions)


def finalize_episode(state: State, config: GameConfig, client=None) -> dict:
    """Save map and knowledge to disk for cross-episode persistence.

    If *client* is provided, regenerates the KB with full episode data
    before persisting, then runs memory consolidation on locations
    with 5+ active memories.

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

    # Run memory consolidation if client is available
    all_mems = dict(state[S.MEMORIES_BY_LOCATION])
    consolidated_total = 0
    if client is not None and all_mems:
        # Backup before consolidation
        mem_path = Path(config.memory_file)
        if mem_path.exists():
            shutil.copy2(mem_path, str(mem_path) + ".bak")
            logger.info(f"Created pre-consolidation backup: {mem_path}.bak")

        kb = state[S.KNOWLEDGE_BASE]
        for loc_key, loc_mems in list(all_mems.items()):
            active_count = sum(1 for m in loc_mems if m.get("status") != "SUPERSEDED")
            if active_count < 5:
                continue
            try:
                updated, stats = consolidate_location(
                    location_id=loc_key, memories=loc_mems,
                    knowledge_base=kb, client=client, config=config,
                )
                all_mems[loc_key] = updated
                before = len(loc_mems)
                after = sum(1 for m in updated if m.get("status") != "SUPERSEDED")
                consolidated_total += stats["dropped"] + stats["merged"] + stats["superseded"]
                logger.info(
                    f"CONSOLIDATION | location={loc_key} | before={before} | after={after}"
                    f" | kept={stats['kept']} | merged={stats['merged']}"
                    f" | dropped={stats['dropped']} | superseded={stats['superseded']}"
                )
            except Exception as e:
                logger.warning(f"Consolidation failed for location {loc_key}: {e}")

    persist_memories(all_mems, config)

    return {
        "episode_id": state[S.EPISODE_ID],
        "turns": state[S.TURN_COUNT],
        "score": state[S.SCORE],
        "max_score": state[S.MAX_SCORE],
        "reason": state[S.GAME_OVER_REASON],
        "mem_consolidated": consolidated_total,
    }
