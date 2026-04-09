"""Tests for extract_fixtures.py — fixture extraction from Burr tracker data."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_fixtures import find_action_step, build_fixture, ACTION_SCHEMA


def _make_step(action_name, state_dict):
    """Build a minimal Burr step structure."""
    return {
        "step_start_log": {"action": action_name},
        "step_end_log": {"state": state_dict},
    }


def test_find_action_step_generate_action():
    steps = [
        _make_step("assemble_context", {"turn_count": 0, "formatted_context": "ctx"}),
        _make_step("generate_action", {"turn_count": 0, "proposed_action": "look", "agent_reasoning": "look around", "next_steps": "", "new_objective": ""}),
        _make_step("evaluate_action", {"turn_count": 0, "critic_score": 0.7}),
        _make_step("execute_action", {"turn_count": 1}),
        _make_step("assemble_context", {"turn_count": 1, "formatted_context": "ctx2"}),
        _make_step("generate_action", {"turn_count": 1, "proposed_action": "north", "agent_reasoning": "go north", "next_steps": "explore", "new_objective": ""}),
        _make_step("evaluate_action", {"turn_count": 1, "critic_score": 0.8}),
        _make_step("execute_action", {"turn_count": 2}),
    ]
    state = find_action_step(steps, target_turn=2, action_type="generate_action")
    assert state is not None
    assert state["proposed_action"] == "north"


def test_find_action_step_missing_turn():
    steps = [
        _make_step("execute_action", {"turn_count": 1}),
    ]
    state = find_action_step(steps, target_turn=99, action_type="generate_action")
    assert state is None


def test_find_action_step_post_execute():
    """Post-execute actions like record_memory should be found by walking forward."""
    steps = [
        _make_step("execute_action", {"turn_count": 1}),
        _make_step("record_memory", {"turn_count": 1, "memories_by_location": {"10": []}}),
        _make_step("assemble_context", {"turn_count": 1}),
    ]
    state = find_action_step(steps, target_turn=1, action_type="record_memory")
    assert state is not None
    assert "memories_by_location" in state


def test_build_fixture_captures_correct_keys():
    state = {
        "formatted_context": "You are at the house.",
        "rejection_count": 0,
        "critic_justification": "",
        "knowledge_base": "some kb",
        "turn_count": 5,
        "proposed_action": "look",
        "agent_reasoning": "exploring",
        "next_steps": "",
        "new_objective": "",
        "episode_id": "ep42",
        # Extra keys that should NOT be captured
        "score": 10,
        "location_name": "House",
    }
    fixture = build_fixture(
        state, action_type="generate_action", turn=5,
        app_id="app123", role="problem",
        description="Agent ignored memories",
    )
    assert fixture["meta"]["episode_id"] == "ep42"
    assert fixture["meta"]["role"] == "problem"
    assert fixture["action_type"] == "generate_action"
    assert fixture["state"]["formatted_context"] == "You are at the house."
    assert fixture["state"]["knowledge_base"] == "some kb"
    assert "score" not in fixture["state"]
    assert fixture["original_output"]["proposed_action"] == "look"
    assert fixture["original_output"]["agent_reasoning"] == "exploring"
