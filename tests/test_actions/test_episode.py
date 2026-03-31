"""Tests for episode persistence: incremental and finalize."""
# ABOUTME: Tests for persist_map, persist_memories, persist_knowledge,
# ABOUTME: initialize_episode, and finalize_episode functions.
from __future__ import annotations

import json
from pathlib import Path

from burr.core import State
from zorkburr.actions.episode import (
    finalize_episode,
    initialize_episode,
    persist_knowledge,
    persist_map,
    persist_memories,
)
from zorkburr.config import GameConfig
from zorkburr.state import S, create_initial_state


def _config(tmp_path: Path) -> GameConfig:
    return GameConfig(
        openrouter_api_key="test",
        map_file=str(tmp_path / "map.json"),
        memory_file=str(tmp_path / "memories.json"),
        knowledge_file=str(tmp_path / "knowledge.md"),
    )


class TestPersistMap:
    def test_writes_map_json(self, tmp_path):
        cfg = _config(tmp_path)
        map_data = {"rooms": {"10": {"name": "West of House"}}, "connections": {}}
        persist_map(map_data, cfg)
        assert json.loads(Path(cfg.map_file).read_text()) == map_data

    def test_skips_empty_map(self, tmp_path):
        cfg = _config(tmp_path)
        persist_map({}, cfg)
        assert not Path(cfg.map_file).exists()

    def test_creates_parent_dirs(self, tmp_path):
        cfg = GameConfig(
            openrouter_api_key="test",
            map_file=str(tmp_path / "nested" / "dir" / "map.json"),
        )
        persist_map({"rooms": {}}, cfg)
        assert Path(cfg.map_file).exists()


class TestPersistMemories:
    def test_writes_memories_json(self, tmp_path):
        cfg = _config(tmp_path)
        mems = {"10": [{"category": "item", "title": "Sword found", "text": "A sword"}]}
        persist_memories(mems, cfg)
        assert json.loads(Path(cfg.memory_file).read_text()) == mems

    def test_skips_empty_memories(self, tmp_path):
        cfg = _config(tmp_path)
        persist_memories({}, cfg)
        assert not Path(cfg.memory_file).exists()


class TestPersistKnowledge:
    def test_writes_knowledge_md(self, tmp_path):
        cfg = _config(tmp_path)
        persist_knowledge("# Strategy\nExplore north.", cfg)
        assert Path(cfg.knowledge_file).read_text() == "# Strategy\nExplore north."

    def test_skips_empty_knowledge(self, tmp_path):
        cfg = _config(tmp_path)
        persist_knowledge("", cfg)
        assert not Path(cfg.knowledge_file).exists()


class TestInitializeEpisode:
    def test_loads_all_persisted_data(self, tmp_path):
        cfg = _config(tmp_path)
        map_data = {"rooms": {"10": {"name": "West"}}, "connections": {}}
        mems = {"10": [{"category": "item", "title": "t", "text": "x"}]}
        kb = "# Knowledge"
        Path(cfg.map_file).write_text(json.dumps(map_data))
        Path(cfg.memory_file).write_text(json.dumps(mems))
        Path(cfg.knowledge_file).write_text(kb)

        from unittest.mock import MagicMock
        jericho = MagicMock()

        overrides = initialize_episode(jericho, cfg)
        assert overrides["map_data"]["rooms"] == map_data["rooms"]
        assert overrides["memories_by_location"] == mems
        assert overrides["knowledge_base"] == kb

    def test_returns_empty_when_no_files(self, tmp_path):
        cfg = _config(tmp_path)
        from unittest.mock import MagicMock
        jericho = MagicMock()
        overrides = initialize_episode(jericho, cfg)
        assert overrides == {}


class TestFinalizeEpisode:
    def test_writes_all_data(self, tmp_path):
        cfg = _config(tmp_path)
        state = create_initial_state("ep-test").update(**{
            S.MAP_DATA: {"rooms": {"1": {"name": "R"}}, "connections": {}},
            S.KNOWLEDGE_BASE: "# KB",
            S.MEMORIES_BY_LOCATION: {"1": [{"title": "t"}]},
        })
        summary = finalize_episode(state, cfg)
        assert Path(cfg.map_file).exists()
        assert Path(cfg.knowledge_file).exists()
        assert Path(cfg.memory_file).exists()
        assert summary["episode_id"] == "ep-test"
