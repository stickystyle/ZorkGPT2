from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.knowledge import update_knowledge
from zorkburr.state import S


def _mock_config(**kwargs):
    defaults = dict(objective_model="test", knowledge_model="test", use_local_models=False)
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _mock_client_with_raw(response_content="insights"):
    """Create a mock client that supports raw_client_for()."""
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = response_content
    mock_raw.chat.completions.create.return_value = mock_response
    # raw_client_for returns (raw_openai_client, stripped_model_name)
    mock_client.raw_client_for.return_value = (mock_raw, "test")
    return mock_client, mock_raw


def _base_state():
    return State({
        S.KNOWLEDGE_BASE: "",
        S.ACTION_HISTORY: [{"turn": i, "action": f"a{i}", "response": f"r{i}"} for i in range(1, 11)],
        S.DISCOVERED_OBJECTIVES: ["Find treasure"],
        S.COMPLETED_OBJECTIVES: [],
        S.SCORE: 10, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })


def test_update_knowledge_synthesizes():
    mock_client, _ = _mock_client_with_raw("## Strategic Insights\n- The mailbox contains a leaflet\n")

    _, new_state = update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert "mailbox" in new_state[S.KNOWLEDGE_BASE].lower()


def test_update_knowledge_fallback_on_error():
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_raw.chat.completions.create.side_effect = Exception("API error")
    mock_client.raw_client_for.return_value = (mock_raw, "test")

    state = State({
        S.KNOWLEDGE_BASE: "existing",
        S.ACTION_HISTORY: [], S.DISCOVERED_OBJECTIVES: [],
        S.COMPLETED_OBJECTIVES: [], S.SCORE: 0, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })

    result, new_state = update_knowledge.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert result["knowledge_length"] == 0
    assert new_state[S.KNOWLEDGE_BASE] == "existing"


def test_update_knowledge_extra_body_for_local():
    mock_client, mock_raw = _mock_client_with_raw()

    update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_raw.chat.completions.create.call_args.kwargs
    # knowledge always uses thinking=False regardless of the use_thinking param
    assert call_kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_update_knowledge_no_extra_body_on_openrouter():
    mock_client, mock_raw = _mock_client_with_raw()

    update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_raw.chat.completions.create.call_args.kwargs
    assert "extra_body" not in call_kwargs


def test_update_knowledge_uses_knowledge_model():
    mock_client, _ = _mock_client_with_raw()

    update_knowledge.run(
        _base_state(), client=mock_client,
        config=_mock_config(knowledge_model="remote/anthropic/claude-sonnet-4.6"),
        use_thinking=False,
    )
    mock_client.raw_client_for.assert_called_with("remote/anthropic/claude-sonnet-4.6")


