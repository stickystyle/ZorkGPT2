"""Tests for memory consolidation models and processing."""
import json
from pathlib import Path
from unittest.mock import MagicMock

from zorkburr.actions.episode import apply_consolidation_actions, consolidate_location
from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse


def test_consolidation_action_keep():
    a = ConsolidationAction(action="keep", memory_title="Found Sword", reason="useful")
    assert a.action == "keep"
    assert a.merge_with == ""
    assert a.new_text == ""
    assert a.new_title == ""


def test_consolidation_action_merge():
    a = ConsolidationAction(
        action="merge", memory_title="Window Open",
        merge_with="Window Ajar", new_title="Enter via Window",
        new_text="Open window behind house to reach Kitchen.",
        reason="duplicate info",
    )
    assert a.action == "merge"
    assert a.merge_with == "Window Ajar"
    assert a.new_title == "Enter via Window"


def test_consolidation_action_drop():
    a = ConsolidationAction(action="drop", memory_title="Room Description", reason="low value")
    assert a.action == "drop"


def test_consolidation_action_supersede():
    a = ConsolidationAction(
        action="supersede", memory_title="Wrong Info",
        merge_with="Correct Info", reason="contradicted by evidence",
    )
    assert a.action == "supersede"
    assert a.merge_with == "Correct Info"


def test_consolidation_response():
    r = ConsolidationResponse(actions=[
        ConsolidationAction(action="keep", memory_title="A", reason="good"),
        ConsolidationAction(action="drop", memory_title="B", reason="junk"),
    ])
    assert len(r.actions) == 2


class TestApplyConsolidationActions:
    def test_keep_action(self):
        mems = [
            {"title": "Found Sword", "text": "Sword in trophy case.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 5},
        ]
        actions = [ConsolidationAction(action="keep", memory_title="Found Sword", reason="useful")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 1
        assert result[0]["title"] == "Found Sword"
        assert stats["kept"] == 1

    def test_drop_action(self):
        mems = [
            {"title": "Room Desc", "text": "A plain room.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "ephemeral", "episode": "ep-1", "turn": 2},
        ]
        actions = [ConsolidationAction(action="drop", memory_title="Room Desc", reason="junk")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 0
        assert stats["dropped"] == 1

    def test_merge_action(self):
        mems = [
            {"title": "Window Open", "text": "Window behind house is open.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 3},
            {"title": "Window Ajar", "text": "The window is ajar.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-2", "turn": 5},
        ]
        actions = [
            ConsolidationAction(
                action="merge", memory_title="Window Open", merge_with="Window Ajar",
                new_title="Enter via Window", new_text="Open window behind house to reach Kitchen.",
                reason="duplicates",
            ),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        # Both originals superseded, one new memory created
        superseded = [m for m in result if m["status"] == "SUPERSEDED"]
        active = [m for m in result if m["status"] == "ACTIVE"]
        assert len(superseded) == 2
        assert len(active) == 1
        assert active[0]["title"] == "Enter via Window"
        assert active[0]["episode"] == "consolidated"
        assert stats["merged"] == 1

    def test_supersede_action(self):
        mems = [
            {"title": "Wrong Info", "text": "Bad advice.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 2},
            {"title": "Correct Info", "text": "Good advice.", "status": "ACTIVE",
             "category": "SUCCESS", "persistence": "permanent", "episode": "ep-2", "turn": 4},
        ]
        actions = [
            ConsolidationAction(
                action="supersede", memory_title="Wrong Info",
                merge_with="Correct Info", reason="contradicted",
            ),
            ConsolidationAction(action="keep", memory_title="Correct Info", reason="accurate"),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        wrong = next(m for m in result if m["title"] == "Wrong Info")
        assert wrong["status"] == "SUPERSEDED"
        assert wrong["superseded_by"] == "Correct Info"
        assert stats["superseded"] == 1

    def test_missing_memory_defaults_to_keep(self):
        """Memories not mentioned in actions are kept by default."""
        mems = [
            {"title": "Mentioned", "text": "x", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 1},
            {"title": "Unmentioned", "text": "y", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 2},
        ]
        actions = [ConsolidationAction(action="keep", memory_title="Mentioned", reason="good")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len([m for m in result if m["status"] == "ACTIVE"]) == 2
        assert stats["kept"] == 2  # 1 explicit + 1 default


    def test_drop_with_bracketed_title(self):
        """LLM returns titles wrapped in brackets — should still match bare titles."""
        mems = [
            {"title": "Found Behind House with Window", "text": "Window is open.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 3},
        ]
        actions = [ConsolidationAction(action="drop", memory_title="[Found Behind House with Window]", reason="stale")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 0
        assert stats["dropped"] == 1
        assert stats["rejected"] == 0

    def test_merge_with_bracketed_titles(self):
        """LLM returns bracket-wrapped titles for merge — should match bare titles."""
        mems = [
            {"title": "Window Open", "text": "Window behind house is open.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 3},
            {"title": "Window Ajar", "text": "The window is ajar.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-2", "turn": 5},
        ]
        actions = [
            ConsolidationAction(
                action="merge", memory_title="[Window Open]", merge_with="[Window Ajar]",
                new_title="Enter via Window", new_text="Open window behind house to reach Kitchen.",
                reason="duplicates",
            ),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        superseded = [m for m in result if m["status"] == "SUPERSEDED"]
        active = [m for m in result if m["status"] == "ACTIVE"]
        assert len(superseded) == 2
        assert len(active) == 1
        assert active[0]["title"] == "Enter via Window"
        assert stats["merged"] == 1
        assert stats["rejected"] == 0

    def test_supersede_with_bracketed_titles(self):
        """LLM returns bracket-wrapped titles for supersede — should match bare titles."""
        mems = [
            {"title": "Wrong Info", "text": "Bad advice.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 2},
            {"title": "Correct Info", "text": "Good advice.", "status": "ACTIVE",
             "category": "SUCCESS", "persistence": "permanent", "episode": "ep-2", "turn": 4},
        ]
        actions = [
            ConsolidationAction(
                action="supersede", memory_title="[Wrong Info]",
                merge_with="[Correct Info]", reason="contradicted",
            ),
            ConsolidationAction(action="keep", memory_title="[Correct Info]", reason="accurate"),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        wrong = next(m for m in result if m["title"] == "Wrong Info")
        assert wrong["status"] == "SUPERSEDED"
        assert stats["superseded"] == 1
        assert stats["rejected"] == 0

    def test_keep_with_bracketed_title_default_keep(self):
        """Bracket-wrapped keep title should count in processed_titles, not double-count."""
        mems = [
            {"title": "Found Sword", "text": "Sword in trophy case.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 5},
            {"title": "Other Memory", "text": "Something.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 6},
        ]
        actions = [ConsolidationAction(action="keep", memory_title="[Found Sword]", reason="useful")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 2
        assert stats["kept"] == 2  # 1 explicit + 1 default


class TestConsolidateLocation:
    def test_calls_llm_and_applies_actions(self):
        mock_client = MagicMock()
        mock_client.create.return_value = ConsolidationResponse(actions=[
            ConsolidationAction(action="keep", memory_title="Good Memory", reason="useful"),
            ConsolidationAction(action="drop", memory_title="Junk Memory", reason="noise"),
        ])
        mems = [
            {"title": "Good Memory", "text": "Useful.", "status": "ACTIVE",
             "category": "SUCCESS", "persistence": "permanent", "episode": "ep-1", "turn": 1},
            {"title": "Junk Memory", "text": "Noise.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "ephemeral", "episode": "ep-1", "turn": 2},
        ]
        result, stats = consolidate_location(
            location_id="10", memories=mems, knowledge_base="# KB",
            client=mock_client, config=MagicMock(analysis_model="test"),
        )
        assert len(result) == 1
        assert result[0]["title"] == "Good Memory"
        assert stats["dropped"] == 1
