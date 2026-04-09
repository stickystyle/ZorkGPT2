"""Tests for critic action: object tree validation and LLM evaluation."""
from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.critic import evaluate_action, validate_against_object_tree
from zorkburr.llm.models import CriticResponse
from zorkburr.state import S


def _make_mock_jericho(visible_objects=None, inventory=None):
    """Create a mock JerichoInterface with configurable objects."""
    mock = MagicMock()
    mock.get_visible_objects.return_value = visible_objects or []
    mock.get_inventory.return_value = inventory or []
    return mock


def _make_state(**overrides):
    """Create a minimal state for critic tests."""
    defaults = {
        S.PROPOSED_ACTION: "look",
        S.GAME_RESPONSE: "You are in a clearing.",
        S.ACTION_HISTORY: [],
        S.EXITS: ["north", "south"],
        S.INVENTORY: [],
        S.LOCATION_NAME: "Clearing",
        S.REJECTION_COUNT: 0,
    }
    defaults.update(overrides)
    return State(defaults)


def _make_config(enable_critic=True, threshold=0.3, max_rejections=3):
    """Create a mock config."""
    mock = MagicMock()
    mock.enable_critic = enable_critic
    mock.critic_model = "test-model"
    mock.critic_rejection_threshold = threshold
    mock.max_rejections_per_turn = max_rejections
    return mock


# --- validate_against_object_tree tests ---

def test_validate_take_sword_visible():
    """take sword when sword is visible -> True."""
    jericho = _make_mock_jericho(visible_objects=[{"name": "sword", "num": 10}])
    is_valid, reason = validate_against_object_tree("take sword", jericho)
    assert is_valid is True


def test_validate_take_sword_not_visible():
    """take sword when sword is NOT visible -> False."""
    jericho = _make_mock_jericho(visible_objects=[{"name": "mailbox", "num": 5}])
    is_valid, reason = validate_against_object_tree("take sword", jericho)
    assert is_valid is False


def test_validate_single_word():
    """Single-word command like 'look' -> True."""
    jericho = _make_mock_jericho()
    is_valid, reason = validate_against_object_tree("look", jericho)
    assert is_valid is True


def test_validate_movement():
    """Movement command 'go north' -> True."""
    jericho = _make_mock_jericho()
    is_valid, reason = validate_against_object_tree("go north", jericho)
    assert is_valid is True


# --- evaluate_action tests ---

def test_evaluate_action_accepts_good_action():
    """LLM returns score 0.8 -> action accepted, rejection_count unchanged."""
    mock_llm = MagicMock()
    mock_llm.create.return_value = CriticResponse(
        score=0.8, justification="Good interaction", confidence=0.9
    )
    jericho = _make_mock_jericho(visible_objects=[{"name": "mailbox", "num": 5}])
    state = _make_state(**{S.PROPOSED_ACTION: "open mailbox"})
    config = _make_config()

    result, new_state = evaluate_action.run(
        state, llm=mock_llm, jericho=jericho, config=config
    )
    assert result["accepted"] is True
    assert new_state[S.CRITIC_SCORE] == 0.8
    assert new_state[S.REJECTION_COUNT] == 0


def test_evaluate_action_rejects_bad_action():
    """LLM returns score -0.5 -> action rejected, rejection_count increments."""
    mock_llm = MagicMock()
    mock_llm.create.return_value = CriticResponse(
        score=-0.5, justification="Jumping is pointless", confidence=0.9
    )
    jericho = _make_mock_jericho()
    state = _make_state(**{S.PROPOSED_ACTION: "jump"})
    config = _make_config()

    result, new_state = evaluate_action.run(
        state, llm=mock_llm, jericho=jericho, config=config
    )
    assert result["accepted"] is False
    assert new_state[S.CRITIC_SCORE] == -0.5
    assert new_state[S.REJECTION_COUNT] == 1


def test_evaluate_action_auto_accepts_when_disabled():
    """Critic disabled -> auto-accept with score 0.5."""
    mock_llm = MagicMock()
    jericho = _make_mock_jericho()
    state = _make_state(**{S.PROPOSED_ACTION: "jump"})
    config = _make_config(enable_critic=False)

    result, new_state = evaluate_action.run(
        state, llm=mock_llm, jericho=jericho, config=config
    )
    assert result["accepted"] is True
    assert new_state[S.CRITIC_SCORE] == 0.5
    assert new_state[S.REJECTION_COUNT] == 0
    # LLM should NOT have been called
    mock_llm.create.assert_not_called()
