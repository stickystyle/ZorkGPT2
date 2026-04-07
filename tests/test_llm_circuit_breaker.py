"""Tests for the LLM-failure circuit breaker counter in generate_action."""
from unittest.mock import MagicMock

from burr.core import State

from zorkburr.actions.agent import generate_action
from zorkburr.llm.models import AgentResponse
from zorkburr.state import S


def _mock_config(**kwargs):
    defaults = dict(
        agent_model="test",
        default_temperature=1.0,
        default_max_tokens=4096,
        use_local_models=False,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _initial_state() -> State:
    return State({
        S.FORMATTED_CONTEXT: "You are somewhere.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
        S.LLM_FAILURE_COUNT: 0,
    })


def test_failure_count_increments_after_one_failure():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("timeout")
    state = _initial_state()
    _, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.LLM_FAILURE_COUNT] == 1
    assert new_state[S.PROPOSED_ACTION] == "look"


def test_failure_count_increments_to_five_after_five_failures():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("timeout")
    state = _initial_state()
    config = _mock_config()
    for expected in range(1, 6):
        _, state = generate_action.run(
            state, client=mock_client, config=config, use_thinking=False
        )
        assert state[S.LLM_FAILURE_COUNT] == expected
    assert state[S.LLM_FAILURE_COUNT] == 5


def test_success_resets_failure_count_to_zero():
    """3 failures -> success: counter goes 1, 2, 3, then 0."""
    mock_client = MagicMock()
    mock_client.create.side_effect = [
        Exception("timeout"),
        Exception("timeout"),
        Exception("timeout"),
        AgentResponse(thinking="ok", action="north", new_objective=""),
    ]
    state = _initial_state()
    config = _mock_config()

    _, state = generate_action.run(state, client=mock_client, config=config, use_thinking=False)
    assert state[S.LLM_FAILURE_COUNT] == 1

    _, state = generate_action.run(state, client=mock_client, config=config, use_thinking=False)
    assert state[S.LLM_FAILURE_COUNT] == 2

    _, state = generate_action.run(state, client=mock_client, config=config, use_thinking=False)
    assert state[S.LLM_FAILURE_COUNT] == 3

    _, state = generate_action.run(state, client=mock_client, config=config, use_thinking=False)
    assert state[S.LLM_FAILURE_COUNT] == 0
    assert state[S.PROPOSED_ACTION] == "north"
