"""Tests for memory consolidation models and processing."""
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
