"""Tests for state export serialization."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from burr.core import State

from zorkburr.state import S, create_initial_state
from zorkburr.viewer.state_export import export_turn_state


class TestExportTurnStateStructure:
    """Exported dict has the expected top-level keys and types."""

    def test_has_required_top_level_keys(self):
        state = create_initial_state("test-ep")
        result = export_turn_state(state)
        assert set(result.keys()) == {
            "metadata", "turn_data", "game_state", "strategic", "map", "recent_history",
        }

    def test_is_json_serializable(self):
        state = create_initial_state("test-ep")
        result = export_turn_state(state)
        # Should not raise
        serialized = json.dumps(result)
        assert isinstance(serialized, str)


class TestMetadata:
    """metadata section captures episode/turn/score info."""

    def test_episode_id_from_state(self):
        state = create_initial_state("my-episode")
        result = export_turn_state(state)
        assert result["metadata"]["episode_id"] == "my-episode"

    def test_turn_count(self):
        state = create_initial_state("ep").update(**{S.TURN_COUNT: 42})
        result = export_turn_state(state)
        assert result["metadata"]["turn"] == 42

    def test_score_fields(self):
        state = create_initial_state("ep").update(**{S.SCORE: 25, S.MAX_SCORE: 350})
        result = export_turn_state(state)
        assert result["metadata"]["score"] == 25
        assert result["metadata"]["max_score"] == 350

    def test_game_over_fields(self):
        state = create_initial_state("ep").update(
            **{S.GAME_OVER: True, S.GAME_OVER_REASON: "victory"}
        )
        result = export_turn_state(state)
        assert result["metadata"]["game_over"] is True
        assert result["metadata"]["game_over_reason"] == "victory"

    def test_timestamp_is_iso_format(self):
        state = create_initial_state("ep")
        result = export_turn_state(state)
        ts = result["metadata"]["timestamp"]
        # Should parse as ISO 8601
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None  # should be timezone-aware


class TestTurnData:
    """turn_data section captures the current turn's decision process."""

    def test_action_and_response(self):
        state = create_initial_state("ep").update(**{
            S.ACTION_TO_TAKE: "open mailbox",
            S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        })
        result = export_turn_state(state)
        assert result["turn_data"]["action"] == "open mailbox"
        assert result["turn_data"]["game_response"] == "Opening the small mailbox reveals a leaflet."

    def test_agent_reasoning(self):
        state = create_initial_state("ep").update(**{
            S.AGENT_REASONING: "The mailbox is the only interactable object here.",
        })
        result = export_turn_state(state)
        assert result["turn_data"]["agent_reasoning"] == "The mailbox is the only interactable object here."

    def test_critic_fields(self):
        state = create_initial_state("ep").update(**{
            S.CRITIC_SCORE: 0.8,
            S.CRITIC_JUSTIFICATION: "Good exploration action.",
            S.CRITIC_CONFIDENCE: 0.9,
            S.WAS_OVERRIDDEN: False,
            S.REJECTION_COUNT: 0,
        })
        result = export_turn_state(state)
        td = result["turn_data"]
        assert td["critic_score"] == 0.8
        assert td["critic_justification"] == "Good exploration action."
        assert td["critic_confidence"] == 0.9
        assert td["was_overridden"] is False
        assert td["rejection_count"] == 0


class TestGameState:
    """game_state section captures current world state."""

    def test_location(self):
        state = create_initial_state("ep").update(**{
            S.LOCATION_NAME: "West of House",
            S.LOCATION_ID: 180,
        })
        result = export_turn_state(state)
        gs = result["game_state"]
        assert gs["location_name"] == "West of House"
        assert gs["location_id"] == 180

    def test_inventory_and_exits(self):
        state = create_initial_state("ep").update(**{
            S.INVENTORY: ["leaflet", "sword"],
            S.EXITS: ["north", "south", "west"],
        })
        result = export_turn_state(state)
        gs = result["game_state"]
        assert gs["inventory"] == ["leaflet", "sword"]
        assert gs["exits"] == ["north", "south", "west"]

    def test_combat_and_objects(self):
        state = create_initial_state("ep").update(**{
            S.IN_COMBAT: True,
            S.VISIBLE_OBJECTS: [{"name": "troll", "id": 99}],
        })
        result = export_turn_state(state)
        gs = result["game_state"]
        assert gs["in_combat"] is True
        assert gs["visible_objects"] == [{"name": "troll", "id": 99}]

    def test_progress_tracking(self):
        state = create_initial_state("ep").update(**{
            S.TURNS_SINCE_PROGRESS: 5,
        })
        result = export_turn_state(state)
        assert result["game_state"]["turns_since_progress"] == 5


class TestStrategic:
    """strategic section captures objectives, knowledge, memories."""

    def test_objectives(self):
        state = create_initial_state("ep").update(**{
            S.DISCOVERED_OBJECTIVES: ["Find the trapdoor", "Explore the forest"],
            S.COMPLETED_OBJECTIVES: [{"objective": "Open mailbox", "completed_turn": 2}],
        })
        result = export_turn_state(state)
        st = result["strategic"]
        assert st["discovered_objectives"] == ["Find the trapdoor", "Explore the forest"]
        assert st["completed_objectives"] == [{"objective": "Open mailbox", "completed_turn": 2}]

    def test_knowledge_base(self):
        state = create_initial_state("ep").update(**{
            S.KNOWLEDGE_BASE: "## Strategic Guide\nAlways check the mailbox first.",
        })
        result = export_turn_state(state)
        assert result["strategic"]["knowledge_base"] == "## Strategic Guide\nAlways check the mailbox first."

    def test_memories_at_current_location(self):
        memories = {
            "180": [
                {"category": "DISCOVERY", "title": "Leaflet", "text": "Found a leaflet"},
            ],
            "200": [
                {"category": "DANGER", "title": "Troll", "text": "A troll guards the bridge"},
            ],
        }
        state = create_initial_state("ep").update(**{
            S.MEMORIES_BY_LOCATION: memories,
            S.LOCATION_ID: 180,
        })
        result = export_turn_state(state)
        # Should only include memories for current location
        assert result["strategic"]["memories_at_location"] == [
            {"category": "DISCOVERY", "title": "Leaflet", "text": "Found a leaflet"},
        ]

    def test_memories_empty_when_no_location_match(self):
        state = create_initial_state("ep").update(**{
            S.MEMORIES_BY_LOCATION: {"200": [{"title": "something"}]},
            S.LOCATION_ID: 180,
        })
        result = export_turn_state(state)
        assert result["strategic"]["memories_at_location"] == []


class TestMap:
    """map section captures room graph + convenience fields."""

    def test_empty_map(self):
        state = create_initial_state("ep")
        result = export_turn_state(state)
        m = result["map"]
        assert m["rooms"] == {}
        assert m["connections"] == {}
        assert m["current_room"] == 0
        assert m["visited_count"] == 0
        assert m["total_rooms"] == 0

    def test_populated_map(self):
        map_data = {
            "rooms": {180: "West of House", 181: "North of House"},
            "connections": {180: {"north": 181}},
            "confidence": {(180, "north"): 2},
        }
        state = create_initial_state("ep").update(**{
            S.MAP_DATA: map_data,
            S.LOCATION_ID: 180,
            S.VISITED_LOCATIONS: [180, 181],
        })
        result = export_turn_state(state)
        m = result["map"]
        # Room IDs should be string keys for JSON
        assert "180" in m["rooms"] or 180 in m["rooms"]
        assert m["current_room"] == 180
        assert m["visited_count"] == 2
        assert m["total_rooms"] == 2


class TestRecentHistory:
    """recent_history includes the last ~10 action history entries."""

    def test_empty_history(self):
        state = create_initial_state("ep")
        result = export_turn_state(state)
        assert result["recent_history"] == []

    def test_recent_history_from_action_history(self):
        history = [
            {"turn": i, "action": f"action_{i}", "response": f"response_{i}", "score": i * 5}
            for i in range(1, 6)
        ]
        state = create_initial_state("ep").update(**{S.ACTION_HISTORY: history})
        result = export_turn_state(state)
        assert len(result["recent_history"]) == 5
        assert result["recent_history"][0]["turn"] == 1
        assert result["recent_history"][-1]["turn"] == 5

    def test_recent_history_capped_at_50(self):
        history = [
            {"turn": i, "action": f"action_{i}", "response": f"resp_{i}", "score": i}
            for i in range(1, 61)
        ]
        state = create_initial_state("ep").update(**{S.ACTION_HISTORY: history})
        result = export_turn_state(state)
        assert len(result["recent_history"]) == 50
        # Should be the most recent 50
        assert result["recent_history"][0]["turn"] == 11
        assert result["recent_history"][-1]["turn"] == 60


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_initial_state_exports_cleanly(self):
        """Fresh state with all defaults should export without errors."""
        state = create_initial_state("fresh")
        result = export_turn_state(state)
        # Verify it's fully JSON-serializable
        json.dumps(result)
        assert result["metadata"]["episode_id"] == "fresh"
        assert result["metadata"]["turn"] == 0
        assert result["metadata"]["score"] == 0

    def test_map_data_from_map_graph(self):
        """MapGraph.to_dict() output should be handled correctly."""
        from zorkburr.game.map_graph import MapGraph
        mg = MapGraph()
        mg.add_room(180, "West of House")
        mg.add_room(181, "North of House")
        mg.add_connection(180, "north", 181)

        state = create_initial_state("ep").update(**{
            S.MAP_DATA: mg.to_dict(),
            S.LOCATION_ID: 180,
            S.VISITED_LOCATIONS: [180, 181],
        })
        result = export_turn_state(state)
        m = result["map"]
        assert m["total_rooms"] == 2
        assert m["visited_count"] == 2
        # Verify JSON-serializable (tuple keys from confidence would break this)
        json.dumps(result)
