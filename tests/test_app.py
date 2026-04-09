"""Integration tests for the Burr turn graph."""
from unittest.mock import MagicMock
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.llm.models import (
    AgentResponse,
    CriticResponse,
    GroundingJudgment,
    GroundingValidationResponse,
    MemorySynthesisResponse,
    ObjectiveCompletionResponse,
)
from zorkburr.state import S


def _mock_llm_side_effect(**kwargs):
    """Return appropriate mock response based on the requested response_model."""
    model = kwargs.get("response_model")
    if model == AgentResponse:
        return AgentResponse(thinking="test", action="look", new_objective="")
    elif model == CriticResponse:
        return CriticResponse(score=0.8, justification="ok", confidence=0.9)
    elif model == MemorySynthesisResponse:
        return MemorySynthesisResponse(should_remember=False, reasoning="skip")
    elif model == ObjectiveCompletionResponse:
        return ObjectiveCompletionResponse(completed_objectives=[])
    elif model == GroundingValidationResponse:
        # Auto-accept all grounding validations in tests
        return GroundingValidationResponse(judgments=[])
    return MagicMock()


def _make_mock_client():
    mock_client = MagicMock()
    mock_client.create.side_effect = _mock_llm_side_effect
    return mock_client


def test_minimal_turn_graph(jericho):
    """Run 3 turns with a mock LLM agent and critic."""
    config = GameConfig(openrouter_api_key="test-key")
    mock_client = _make_mock_client()

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-run",
        tracker=None,  # No tracking for tests
    )

    # Step through 3 complete turns
    turns_completed = 0
    for i in range(60):  # Safety limit (more steps due to larger pipeline)
        action_obj, result, state = app.step()
        if action_obj.name == "execute_action":
            turns_completed += 1
        if turns_completed >= 3 or state[S.GAME_OVER]:
            break

    assert turns_completed == 3
    assert len(state[S.ACTION_HISTORY]) == 3
    assert state[S.GAME_OVER] is False


def test_turn_graph_with_critic(jericho):
    """Critic rejects first action, agent retries, second accepted."""
    config = GameConfig(openrouter_api_key="test-key", enable_critic=True)

    call_count = [0]

    def side_effect_with_rejection(**kwargs):
        model = kwargs.get("response_model")
        if model == AgentResponse:
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentResponse(thinking="try jump", action="jump", new_objective="")
            return AgentResponse(thinking="try mailbox", action="open mailbox", new_objective="")
        elif model == CriticResponse:
            if call_count[0] == 1:
                return CriticResponse(score=-0.5, justification="jumping is pointless", confidence=0.9)
            return CriticResponse(score=0.7, justification="good interaction", confidence=0.8)
        elif model == MemorySynthesisResponse:
            return MemorySynthesisResponse(should_remember=False, reasoning="skip")
        elif model == ObjectiveCompletionResponse:
            return ObjectiveCompletionResponse(completed_objectives=[])
        elif model == GroundingValidationResponse:
            return GroundingValidationResponse(judgments=[])
        return MagicMock()

    mock_client = MagicMock()
    mock_client.create.side_effect = side_effect_with_rejection

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-critic",
        tracker=None,
    )

    # Step until execute_action fires
    for _ in range(30):
        action_obj, result, state = app.step()
        if action_obj.name == "execute_action":
            break
    assert state[S.ACTION_TO_TAKE] == "open mailbox"
