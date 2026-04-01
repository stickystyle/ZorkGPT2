from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.agent import generate_action
from zorkburr.llm.models import AgentResponse
from zorkburr.state import S

def _mock_config(**kwargs):
    """Config mock with safe defaults for local-model guards."""
    defaults = dict(
        agent_model="test",
        default_temperature=1.0,
        default_max_tokens=4096,
        use_local_models=False,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)

def test_generate_action_returns_validated_response():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="I should look around", action="look", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are at the white house.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "look"
    assert "look around" in new_state[S.AGENT_REASONING]

def test_generate_action_retry_includes_feedback():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="trying something else", action="open mailbox", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are at the white house.",
        S.REJECTION_COUNT: 1,
        S.CRITIC_JUSTIFICATION: "Action 'north' was repetitive.",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 2,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "open mailbox"
    call_args = mock_client.create.call_args
    messages = call_args.kwargs.get("messages")
    user_msg = messages[-1]["content"]
    assert "rejected" in user_msg.lower() or "repetitive" in user_msg.lower()

def test_generate_action_fallback_on_error():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("LLM error")
    state = State({
        S.FORMATTED_CONTEXT: "You are somewhere.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "look"  # Safe fallback

def test_generate_action_no_extra_body_for_local():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="deep reasoning", action="north", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are in a maze.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 5,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert "extra_body" not in call_kwargs

def test_generate_action_no_extra_body_on_openrouter():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="reasoning", action="south", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "context",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
