"""Burr application builders for ZorkBurr turn and episode graphs."""
from __future__ import annotations

from burr.core import ApplicationBuilder, State, action, default, when

from zorkburr.actions.agent import generate_action
from zorkburr.actions.context import assemble_context
from zorkburr.actions.execute import execute_action
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S, create_initial_state

import instructor


@action(reads=[], writes=[])
def turn_complete(state: State) -> tuple[dict, State]:
    """Terminal action — game is over."""
    return {"status": "complete"}, state


def build_turn_app(
    config: GameConfig,
    jericho: JerichoInterface,
    client: instructor.Instructor,
    episode_id: str | None = None,
    tracker: str | None = "local",
):
    """Build the minimal turn graph: context -> agent -> execute -> loop.

    No critic yet — this is the Phase 2 minimal loop.
    """
    initial_state = create_initial_state(episode_id=episode_id)

    # Seed initial game state from Jericho
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    initial_state = initial_state.update(**{
        S.GAME_RESPONSE: jericho.last_response,
        S.LOCATION_ID: loc_id,
        S.LOCATION_NAME: loc_name,
        S.SCORE: score,
        S.MAX_SCORE: max_score,
        S.INVENTORY: inventory,
    })

    # Bind dependencies to actions
    bound_agent = generate_action.bind(client=client, config=config)
    bound_execute = execute_action.bind(jericho=jericho)

    builder = (
        ApplicationBuilder()
        .with_actions(
            assemble_context=assemble_context,
            generate_action=bound_agent,
            execute_action=bound_execute,
            turn_complete=turn_complete,
        )
        .with_transitions(
            ("assemble_context", "generate_action"),
            ("generate_action", "execute_action"),
            ("execute_action", "turn_complete", when(**{S.GAME_OVER: True})),
            ("execute_action", "assemble_context", default),
        )
        .with_entrypoint("assemble_context")
        .with_state(initial_state)
    )

    if tracker:
        builder = builder.with_tracker(tracker)

    return builder.build()
