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
        map_data = {"rooms": {"10": "West of House"}, "connections": {}}
        persist_map(map_data, cfg)
        result = json.loads(Path(cfg.map_file).read_text())
        assert result["rooms"] == {"10": "West of House"}
        assert result["connections"] == {}

    def test_skips_empty_map(self, tmp_path):
        cfg = _config(tmp_path)
        persist_map({}, cfg)
        assert not Path(cfg.map_file).exists()

    def test_merges_with_existing_map(self, tmp_path):
        """A smaller episode map must not overwrite a larger on-disk map."""
        cfg = _config(tmp_path)
        # Simulate a large accumulated map on disk
        big_map = {
            "rooms": {"10": "West of House", "20": "Kitchen", "30": "Attic"},
            "connections": {"10": {"north": 20}, "20": {"south": 10, "up": 30}},
            "confidence": {"10:north": 3, "20:south": 3, "20:up": 2},
            "failures": {},
        }
        Path(cfg.map_file).write_text(json.dumps(big_map))

        # Episode only visits one room — must not lose the others
        small_map = {
            "rooms": {"10": "West of House"},
            "connections": {},
            "confidence": {},
            "failures": {},
        }
        persist_map(small_map, cfg)
        result = json.loads(Path(cfg.map_file).read_text())
        assert set(result["rooms"].keys()) == {"10", "20", "30"}
        assert result["connections"]["20"]["up"] == 30

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


class TestEphemeralPruning:
    def test_prunes_ephemeral_memories_on_load(self, tmp_path):
        cfg = _config(tmp_path)
        mems = {
            "10": [
                {"category": "NOTE", "title": "temp", "text": "x",
                 "episode": "ep-1", "turn": 1, "persistence": "ephemeral", "status": "ACTIVE"},
                {"category": "DISCOVERY", "title": "keep", "text": "y",
                 "episode": "ep-1", "turn": 2, "persistence": "permanent", "status": "ACTIVE"},
            ],
            "20": [
                {"category": "NOTE", "title": "also temp", "text": "z",
                 "episode": "ep-1", "turn": 3, "persistence": "ephemeral", "status": "ACTIVE"},
            ],
        }
        Path(cfg.memory_file).write_text(json.dumps(mems))
        from unittest.mock import MagicMock
        overrides = initialize_episode(MagicMock(), cfg)
        # Ephemeral memories pruned
        assert len(overrides["memories_by_location"]["10"]) == 1
        assert overrides["memories_by_location"]["10"][0]["title"] == "keep"
        # Location 20 had only ephemeral memories — should be removed entirely
        assert "20" not in overrides["memories_by_location"]

    def test_no_pruning_when_all_permanent(self, tmp_path):
        cfg = _config(tmp_path)
        mems = {
            "10": [
                {"category": "DISCOVERY", "title": "keep", "text": "y",
                 "persistence": "permanent", "status": "ACTIVE"},
            ],
        }
        Path(cfg.memory_file).write_text(json.dumps(mems))
        from unittest.mock import MagicMock
        overrides = initialize_episode(MagicMock(), cfg)
        assert len(overrides["memories_by_location"]["10"]) == 1


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


class TestConsolidationInFinalize:
    def test_creates_backup_before_consolidation(self, tmp_path):
        """finalize_episode should create memories.json.bak before consolidating."""
        from unittest.mock import MagicMock
        from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse

        cfg = _config(tmp_path)
        # Write initial memories (6 at one location to trigger consolidation)
        mems = {"10": [
            {"title": f"Mem {i}", "text": f"Text {i}", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": i}
            for i in range(6)
        ]}
        Path(cfg.memory_file).write_text(json.dumps(mems))

        state = create_initial_state("ep-test").update(**{
            S.MAP_DATA: {},
            S.KNOWLEDGE_BASE: "# KB",
            S.MEMORIES_BY_LOCATION: mems,
        })

        # Mock the LLM client to return all-keep actions
        mock_client = MagicMock()
        mock_client.create.return_value = ConsolidationResponse(
            actions=[ConsolidationAction(action="keep", memory_title=f"Mem {i}", reason="good") for i in range(6)]
        )

        finalize_episode(state, cfg, client=mock_client)

        # Backup should exist
        bak_path = Path(cfg.memory_file + ".bak")
        assert bak_path.exists()
        # Backup content should match original
        assert json.loads(bak_path.read_text()) == mems

    def test_skips_consolidation_for_small_locations(self, tmp_path):
        """Locations with fewer than 5 non-SUPERSEDED memories should not be consolidated."""
        from unittest.mock import MagicMock
        from zorkburr.llm.models import ConsolidationResponse

        cfg = _config(tmp_path)
        mems = {"10": [
            {"title": f"Mem {i}", "text": f"Text {i}", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": i}
            for i in range(3)
        ]}
        Path(cfg.memory_file).write_text(json.dumps(mems))

        state = create_initial_state("ep-test").update(**{
            S.MAP_DATA: {},
            S.KNOWLEDGE_BASE: "# KB",
            S.MEMORIES_BY_LOCATION: mems,
        })

        mock_client = MagicMock()
        finalize_episode(state, cfg, client=mock_client)

        # LLM should NOT have been called for consolidation
        for call in mock_client.create.call_args_list:
            if call.kwargs.get("response_model") == ConsolidationResponse:
                raise AssertionError("Should not call consolidation for <5 memories")
