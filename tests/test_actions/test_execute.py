from burr.core import State
from zorkburr.actions.execute import execute_action
from zorkburr.state import S


def test_execute_look(jericho):
    state = State({
        S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 1,
        S.SCORE: 0,
        S.LOCATION_ID: 0,
        S.LOCATION_NAME: "",
        S.INVENTORY: [],
        S.ACTION_HISTORY: [],
        S.GAME_OVER: False,
    })
    result, new_state = execute_action.run(state, jericho=jericho)
    assert "white house" in new_state[S.GAME_RESPONSE].lower()
    assert new_state[S.LOCATION_ID] > 0
    assert isinstance(new_state[S.INVENTORY], list)
    assert new_state[S.GAME_OVER] is False


def test_execute_captures_pre_state(jericho):
    state = State({
        S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 1,
        S.SCORE: 0,
        S.LOCATION_ID: 42,
        S.LOCATION_NAME: "Test Room",
        S.INVENTORY: ["lamp"],
        S.ACTION_HISTORY: [],
        S.GAME_OVER: False,
    })
    _, new_state = execute_action.run(state, jericho=jericho)
    assert new_state[S.PRE_LOCATION_ID] == 42
    assert new_state[S.PRE_LOCATION_NAME] == "Test Room"
    assert new_state[S.PRE_INVENTORY] == ["lamp"]


def test_execute_increments_turn(jericho):
    state = State({
        S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 5,
        S.SCORE: 0,
        S.LOCATION_ID: 0,
        S.LOCATION_NAME: "",
        S.INVENTORY: [],
        S.ACTION_HISTORY: [],
        S.GAME_OVER: False,
    })
    _, new_state = execute_action.run(state, jericho=jericho)
    assert new_state[S.TURN_COUNT] == 6
    assert len(new_state[S.ACTION_HISTORY]) == 1
