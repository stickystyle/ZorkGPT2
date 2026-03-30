"""Integration tests for the Burr turn graph."""
from unittest.mock import MagicMock
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.llm.models import AgentResponse, CriticResponse
from zorkburr.state import S


def test_minimal_turn_graph(jericho):
    """Run 3 turns with a mock LLM agent and critic."""
    config = GameConfig(openrouter_api_key="test-key")
    mock_client = MagicMock()
    mock_client.create.side_effect = [
        AgentResponse(thinking="explore", action="look", new_objective=""),
        CriticResponse(score=0.7, justification="good exploration", confidence=0.8),
        AgentResponse(thinking="check mailbox", action="open mailbox", new_objective=""),
        CriticResponse(score=0.7, justification="good interaction", confidence=0.8),
        AgentResponse(thinking="look again", action="read leaflet", new_objective=""),
        CriticResponse(score=0.7, justification="good reading", confidence=0.8),
    ]

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-run",
        tracker=None,  # No tracking for tests
    )

    # Step through 3 complete turns (each turn = 4 actions: context, agent, critic, execute)
    turns_completed = 0
    for i in range(30):  # Safety limit
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
    config = GameConfig(openrouter_api_key="test-key")
    mock_client = MagicMock()
    mock_client.create.side_effect = [
        AgentResponse(thinking="try jump", action="jump", new_objective=""),
        CriticResponse(score=-0.5, justification="jumping is pointless", confidence=0.9),
        AgentResponse(thinking="try mailbox", action="open mailbox", new_objective=""),
        CriticResponse(score=0.7, justification="good interaction", confidence=0.8),
    ]
    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-critic",
        tracker=None,
    )

    # Step until execute_action fires
    for _ in range(20):
        action_obj, result, state = app.step()
        if action_obj.name == "execute_action":
            break
    assert state[S.ACTION_TO_TAKE] == "open mailbox"
