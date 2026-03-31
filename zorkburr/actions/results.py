"""Record results: update map, track progress, reset per-turn state."""
from __future__ import annotations
from zorkburr.actions import action
from burr.core import State
from zorkburr.actions.episode import persist_map
from zorkburr.config import GameConfig
from zorkburr.game.map_graph import MapGraph, normalize_direction
from zorkburr.state import S

@action(
    reads=[S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME, S.LOCATION_ID, S.LOCATION_NAME,
           S.ACTION_TO_TAKE, S.SCORE, S.PRE_SCORE, S.TURN_COUNT, S.GAME_OVER,
           S.MAP_DATA, S.VISITED_LOCATIONS, S.TURNS_SINCE_PROGRESS,
           S.LAST_SCORE_CHANGE_TURN, S.REJECTION_COUNT],
    writes=[S.MAP_DATA, S.VISITED_LOCATIONS, S.TURNS_SINCE_PROGRESS,
            S.LAST_SCORE_CHANGE_TURN, S.REJECTION_COUNT],
)
def record_results(state: State, config: GameConfig) -> tuple[dict, State]:
    pre_loc = state[S.PRE_LOCATION_ID]
    cur_loc = state[S.LOCATION_ID]
    action_text = state[S.ACTION_TO_TAKE]
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    turn = state[S.TURN_COUNT]

    mg = MapGraph.from_dict(state[S.MAP_DATA]) if state[S.MAP_DATA] else MapGraph()
    if not mg.has_room(cur_loc):
        mg.add_room(cur_loc, state[S.LOCATION_NAME])

    moved = pre_loc != cur_loc and pre_loc != 0
    if moved:
        direction = normalize_direction(action_text)
        if direction:
            if not mg.has_room(pre_loc):
                mg.add_room(pre_loc, state[S.PRE_LOCATION_NAME])
            mg.add_connection(pre_loc, direction, cur_loc)

    visited = list(state[S.VISITED_LOCATIONS])
    if cur_loc not in visited:
        visited.append(cur_loc)

    turns_since = state[S.TURNS_SINCE_PROGRESS]
    last_score_turn = state[S.LAST_SCORE_CHANGE_TURN]
    if score_delta != 0:
        turns_since = 0
        last_score_turn = turn
    else:
        turns_since += 1

    map_data = mg.to_dict()
    persist_map(map_data, config)

    return (
        {"moved": moved, "score_delta": score_delta},
        state.update(**{
            S.MAP_DATA: map_data,
            S.VISITED_LOCATIONS: visited,
            S.TURNS_SINCE_PROGRESS: turns_since,
            S.LAST_SCORE_CHANGE_TURN: last_score_turn,
            S.REJECTION_COUNT: 0,
        }),
    )
