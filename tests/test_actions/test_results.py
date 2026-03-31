from unittest.mock import patch

from burr.core import State
from zorkburr.actions.results import record_results
from zorkburr.config import GameConfig
from zorkburr.game.map_graph import MapGraph
from zorkburr.state import S

_CONFIG = GameConfig(openrouter_api_key="test", map_file="/dev/null")


@patch("zorkburr.actions.results.persist_map")
def test_record_results_updates_map_on_movement(mock_persist):
    mg = MapGraph()
    mg.add_room(10, "West of House")
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.LOCATION_ID: 20, S.LOCATION_NAME: "North of House",
        S.ACTION_TO_TAKE: "north", S.SCORE: 0, S.PRE_SCORE: 0,
        S.TURN_COUNT: 3, S.GAME_OVER: False,
        S.MAP_DATA: mg.to_dict(), S.VISITED_LOCATIONS: [10],
        S.TURNS_SINCE_PROGRESS: 2, S.LAST_SCORE_CHANGE_TURN: 1,
        S.REJECTION_COUNT: 0,
    })
    result, new_state = record_results.run(state, config=_CONFIG)
    mg2 = MapGraph.from_dict(new_state[S.MAP_DATA])
    assert mg2.has_room(20)
    assert mg2.get_exits(10).get("north") == 20
    assert 20 in new_state[S.VISITED_LOCATIONS]
    mock_persist.assert_called_once()


@patch("zorkburr.actions.results.persist_map")
def test_record_results_tracks_score_progress(mock_persist):
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West",
        S.LOCATION_ID: 10, S.LOCATION_NAME: "West",
        S.ACTION_TO_TAKE: "open mailbox", S.SCORE: 5, S.PRE_SCORE: 0,
        S.TURN_COUNT: 3, S.GAME_OVER: False,
        S.MAP_DATA: {}, S.VISITED_LOCATIONS: [10],
        S.TURNS_SINCE_PROGRESS: 5, S.LAST_SCORE_CHANGE_TURN: 0,
        S.REJECTION_COUNT: 0,
    })
    result, new_state = record_results.run(state, config=_CONFIG)
    assert new_state[S.TURNS_SINCE_PROGRESS] == 0
    assert new_state[S.LAST_SCORE_CHANGE_TURN] == 3


@patch("zorkburr.actions.results.persist_map")
def test_record_results_resets_rejection_count(mock_persist):
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West",
        S.LOCATION_ID: 10, S.LOCATION_NAME: "West",
        S.ACTION_TO_TAKE: "look", S.SCORE: 0, S.PRE_SCORE: 0,
        S.TURN_COUNT: 2, S.GAME_OVER: False,
        S.MAP_DATA: {}, S.VISITED_LOCATIONS: [10],
        S.TURNS_SINCE_PROGRESS: 1, S.LAST_SCORE_CHANGE_TURN: 0,
        S.REJECTION_COUNT: 2,
    })
    _, new_state = record_results.run(state, config=_CONFIG)
    assert new_state[S.REJECTION_COUNT] == 0
