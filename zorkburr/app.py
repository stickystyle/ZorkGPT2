"""Burr application builders for ZorkBurr turn and episode graphs."""
from __future__ import annotations

from burr.core import ApplicationBuilder, State, action, default, expr, when

from zorkburr.actions.agent import generate_action
from zorkburr.actions.context import assemble_context
from zorkburr.actions.critic import evaluate_action
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
    """Build the turn graph: context -> agent -> critic -> execute -> loop.

    Critic evaluates proposed actions and can reject them back to agent.
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
    bound_critic = evaluate_action.bind(llm=client, jericho=jericho, config=config)
    bound_execute = execute_action.bind(jericho=jericho)

    threshold = config.critic_rejection_threshold
    max_rejections = config.max_rejections_per_turn

    builder = (
        ApplicationBuilder()
        .with_actions(
            assemble_context=assemble_context,
            generate_action=bound_agent,
            evaluate_action=bound_critic,
            execute_action=bound_execute,
            turn_complete=turn_complete,
        )
        .with_transitions(
            ("assemble_context", "generate_action"),
            ("generate_action", "evaluate_action"),
            # Accepted: score >= threshold
            ("evaluate_action", "execute_action", expr(f"critic_score >= {threshold}")),
            # Max rejections reached — force accept
            ("evaluate_action", "execute_action", expr(f"rejection_count >= {max_rejections}")),
            # Rejected — retry
            ("evaluate_action", "generate_action", default),
            # After execution
            ("execute_action", "turn_complete", when(**{S.GAME_OVER: True})),
            ("execute_action", "assemble_context", default),
        )
        .with_entrypoint("assemble_context")
        .with_state(initial_state)
    )

    if tracker:
        builder = builder.with_tracker(tracker)

    return builder.build()
