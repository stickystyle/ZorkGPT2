from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.objectives import update_objectives, check_objective_completion
from zorkburr.llm.models import Objective, ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.state import S


def _mock_config(**kwargs):
    defaults = dict(analysis_model="test", use_local_models=False)
    defaults.update(kwargs)
    return MagicMock(**defaults)


def test_update_objectives_discovers_new():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=[
            Objective(text="Find the treasure", location_id=42, location_name="Forest"),
            Objective(text="Explore the forest", location_id=0, location_name=""),
        ],
        completed=[],
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [{"action": "look", "response": "forest", "turn": 1}],
        S.GAME_RESPONSE: "You are in a forest.", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.LOCATION_ID: 42, S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {"rooms": {"42": "Forest"}},
    })
    _, new_state = update_objectives.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    objs = new_state[S.DISCOVERED_OBJECTIVES]
    assert len(objs) == 2
    assert objs[0]["text"] == "Find the treasure"
    assert objs[0]["location_id"] == 42
    assert objs[0]["location_name"] == "Forest"
    assert objs[1]["text"] == "Explore the forest"
    assert objs[1]["location_id"] == 0


def test_check_completion_marks_done():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveCompletionResponse(
        completed_objectives=["Open the mailbox"]
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: [
            {"text": "Open the mailbox", "location_id": 10, "location_name": "West House"},
            {"text": "Find treasure", "location_id": 0, "location_name": ""},
        ],
        S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.TURN_COUNT: 5, S.SCORE: 5, S.PRE_SCORE: 0,
    })
    _, new_state = check_objective_completion.run(
        state, client=mock_client, config=MagicMock()
    )
    remaining = new_state[S.DISCOVERED_OBJECTIVES]
    assert len(remaining) == 1
    assert remaining[0]["text"] == "Find treasure"
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1


def test_check_completion_no_objectives():
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "test", S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 1, S.SCORE: 0, S.PRE_SCORE: 0,
    })
    result, new_state = check_objective_completion.run(
        state, client=MagicMock(), config=MagicMock()
    )
    assert result["completed"] == []


def test_update_objectives_extra_body_for_local():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(objectives=[], completed=[])
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [], S.GAME_RESPONSE: "test", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.LOCATION_ID: 42, S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {},
    })
    update_objectives.run(
        state, client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    # use_thinking=True should be propagated to thinking_kwargs
    assert call_kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": True}}


def test_update_objectives_reasoning_on_openrouter():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(objectives=[], completed=[])
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [], S.GAME_RESPONSE: "test", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.LOCATION_ID: 42, S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {},
    })
    update_objectives.run(
        state, client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert call_kwargs["extra_body"] == {"reasoning": {"enabled": True}}


def test_update_objectives_deduplicates():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=[Objective(text="Find the treasure", location_id=42, location_name="Forest")],
        completed=[],
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: [
            {"text": "Find the treasure", "location_id": 42, "location_name": "Forest"},
        ],
        S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [{"action": "look", "response": "forest", "turn": 1}],
        S.GAME_RESPONSE: "forest", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.LOCATION_ID: 42, S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {"rooms": {"42": "Forest"}},
    })
    _, new_state = update_objectives.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 1
