"""Execute action: send command to Jericho, capture game state."""
from __future__ import annotations
import logging
from burr.core import State
from zorkburr.actions import action
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S

logger = logging.getLogger(__name__)

@action(
    reads=[S.ACTION_TO_TAKE, S.TURN_COUNT, S.SCORE, S.LOCATION_ID, S.LOCATION_NAME, S.INVENTORY, S.ACTION_HISTORY],
    writes=[S.GAME_RESPONSE, S.SCORE, S.MAX_SCORE, S.LOCATION_ID, S.LOCATION_NAME, S.INVENTORY,
            S.GAME_OVER, S.GAME_OVER_REASON, S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME,
            S.PRE_SCORE, S.PRE_INVENTORY, S.ACTION_HISTORY, S.TURN_COUNT],
)
def execute_action(state: State, jericho: JerichoInterface) -> tuple[dict, State]:
    """Send the chosen action to Jericho and capture the resulting game state."""
    command = state[S.ACTION_TO_TAKE]
    turn = state[S.TURN_COUNT]

    # Snapshot pre-action state (at SOURCE location for memory)
    pre_loc_id = state[S.LOCATION_ID]
    pre_loc_name = state[S.LOCATION_NAME]
    pre_score = state[S.SCORE]
    pre_inventory = list(state[S.INVENTORY])

    # Execute command
    response = jericho.send_command(command)

    # Capture post-action state from Z-machine (ground truth)
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    game_over, reason = jericho.is_game_over(response)

    # Build action history entry
    history_entry = {
        "turn": turn + 1,
        "action": command,
        "response": response[:500],
        "location_id": pre_loc_id,
        "location_name": pre_loc_name,
        "score_before": pre_score,
        "score_after": score,
    }

    result = {"response": response, "score_delta": score - pre_score}

    new_state = (
        state.update(**{
            S.GAME_RESPONSE: response,
            S.SCORE: score,
            S.MAX_SCORE: max_score,
            S.LOCATION_ID: loc_id,
            S.LOCATION_NAME: loc_name,
            S.INVENTORY: inventory,
            S.GAME_OVER: game_over,
            S.GAME_OVER_REASON: reason,
            S.PRE_LOCATION_ID: pre_loc_id,
            S.PRE_LOCATION_NAME: pre_loc_name,
            S.PRE_SCORE: pre_score,
            S.PRE_INVENTORY: pre_inventory,
            S.TURN_COUNT: turn + 1,
        })
        .append(**{S.ACTION_HISTORY: history_entry})
    )

    return result, new_state
