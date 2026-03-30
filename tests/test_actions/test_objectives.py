from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.objectives import update_objectives, check_objective_completion
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.state import S

def test_update_objectives_discovers_new():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=["Find the treasure", "Explore the forest"], completed=[]
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [{"action": "look", "response": "forest", "turn": 1}],
        S.GAME_RESPONSE: "You are in a forest.", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
    })
    _, new_state = update_objectives.run(state, client=mock_client, config=MagicMock(analysis_model="test"))
    assert "Find the treasure" in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 2

def test_check_completion_marks_done():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveCompletionResponse(completed_objectives=["Open the mailbox"])
    state = State({
        S.DISCOVERED_OBJECTIVES: ["Open the mailbox", "Find treasure"],
        S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.TURN_COUNT: 5, S.SCORE: 5,
    })
    _, new_state = check_objective_completion.run(state, client=mock_client, config=MagicMock(analysis_model="test"))
    assert "Open the mailbox" not in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1
    assert new_state[S.COMPLETED_OBJECTIVES][0]["objective"] == "Open the mailbox"

def test_check_completion_no_objectives():
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "test", S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 1, S.SCORE: 0,
    })
    result, new_state = check_objective_completion.run(state, client=MagicMock(), config=MagicMock())
    assert result["completed"] == []
