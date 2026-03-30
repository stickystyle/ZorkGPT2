from burr.core import State
from zorkburr.state import create_initial_state, S

def test_create_initial_state():
    state = create_initial_state(episode_id="test-ep-1")
    assert state[S.EPISODE_ID] == "test-ep-1"
    assert state[S.TURN_COUNT] == 0
    assert state[S.GAME_OVER] is False
    assert state[S.ACTION_HISTORY] == []

def test_state_keys_are_strings():
    assert isinstance(S.TURN_COUNT, str)
    assert isinstance(S.GAME_RESPONSE, str)

def test_state_is_burr_compatible():
    state = create_initial_state()
    new_state = state.update(**{S.TURN_COUNT: 5})
    assert new_state[S.TURN_COUNT] == 5
    assert state[S.TURN_COUNT] == 0

def test_state_append():
    state = create_initial_state()
    new_state = state.append(**{S.ACTION_HISTORY: {"action": "look", "turn": 1}})
    assert len(new_state[S.ACTION_HISTORY]) == 1
    assert state[S.ACTION_HISTORY] == []
