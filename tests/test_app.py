"""Integration tests for the Burr turn graph."""
from unittest.mock import MagicMock
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.llm.models import AgentResponse
from zorkburr.state import S


def test_minimal_turn_graph(jericho):
    """Run 3 turns with a mock LLM agent."""
    config = GameConfig(openrouter_api_key="test-key")
    mock_client = MagicMock()
    mock_client.create.side_effect = [
        AgentResponse(thinking="explore", action="look", new_objective=""),
        AgentResponse(thinking="check mailbox", action="open mailbox", new_objective=""),
        AgentResponse(thinking="look again", action="read leaflet", new_objective=""),
    ]

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-run",
        tracker=None,  # No tracking for tests
    )

    # Step through 3 complete turns (each turn = 3 actions: context, agent, execute)
    turns_completed = 0
    for i in range(20):  # Safety limit
        action_obj, result, state = app.step()
        if action_obj.name == "execute_action":
            turns_completed += 1
        if turns_completed >= 3 or state[S.GAME_OVER]:
            break

    assert turns_completed == 3
    assert len(state[S.ACTION_HISTORY]) == 3
    assert state[S.GAME_OVER] is False
