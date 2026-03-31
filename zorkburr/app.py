"""Burr application builders for ZorkBurr turn and episode graphs."""
from __future__ import annotations

from burr.core import ApplicationBuilder, State, action, default, expr, when
from burr.core.persistence import SQLitePersister

from zorkburr.actions.agent import generate_action
from zorkburr.actions.context import assemble_context
from zorkburr.actions.critic import evaluate_action
from zorkburr.actions.execute import execute_action
from zorkburr.actions.extract import extract_info
from zorkburr.actions.knowledge import update_knowledge
from zorkburr.actions.memory import record_memory
from zorkburr.actions.objectives import check_objective_completion, update_objectives
from zorkburr.actions.results import record_results
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
    persist: bool = False,
):
    """Build the turn graph with full post-execution pipeline.

    Flow: context -> agent -> critic -> execute -> extract -> results ->
          memory -> completion check -> [periodic updates] -> loop/halt
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
    bound_agent = generate_action.bind(client=client, config=config, use_thinking=True)
    bound_critic = evaluate_action.bind(llm=client, jericho=jericho, config=config)
    bound_execute = execute_action.bind(jericho=jericho)
    bound_extract = extract_info.bind(client=client, jericho=jericho, config=config)
    bound_memory = record_memory.bind(client=client, config=config)
    bound_completion = check_objective_completion.bind(client=client, config=config)
    bound_objectives = update_objectives.bind(client=client, config=config, use_thinking=True)
    bound_knowledge = update_knowledge.bind(client=client, config=config, use_thinking=True)

    threshold = config.critic_rejection_threshold
    max_rejections = config.max_rejections_per_turn
    obj_interval = config.objective_update_interval
    kb_interval = config.knowledge_update_interval

    hooks = []
    if config.s3_bucket:
        from zorkburr.viewer.s3_hook import S3ViewerHook
        hooks.append(S3ViewerHook(bucket=config.s3_bucket, prefix=config.s3_key_prefix))

    builder = (
        ApplicationBuilder()
        .with_actions(
            assemble_context=assemble_context,
            generate_action=bound_agent,
            evaluate_action=bound_critic,
            execute_action=bound_execute,
            extract_info=bound_extract,
            record_results=record_results.bind(config=config),
            record_memory=bound_memory,
            check_objective_completion=bound_completion,
            update_objectives=bound_objectives,
            update_knowledge=bound_knowledge,
            turn_complete=turn_complete,
        )
        .with_transitions(
            # Core loop
            ("assemble_context", "generate_action"),
            ("generate_action", "evaluate_action"),
            # Accepted: score >= threshold
            ("evaluate_action", "execute_action", expr(f"critic_score >= {threshold}")),
            # Max rejections reached — force accept
            ("evaluate_action", "execute_action", expr(f"rejection_count >= {max_rejections}")),
            # Rejected — retry
            ("evaluate_action", "generate_action", default),
            # Post-execution pipeline
            ("execute_action", "extract_info"),
            ("extract_info", "record_results"),
            ("record_results", "record_memory"),
            ("record_memory", "check_objective_completion"),
            # Periodic updates (conditional)
            ("check_objective_completion", "update_objectives",
             expr(f"turn_count > 0 and turn_count % {obj_interval} == 0 and game_over == False")),
            ("check_objective_completion", "turn_complete", when(**{S.GAME_OVER: True})),
            ("check_objective_completion", "assemble_context", default),
            ("update_objectives", "update_knowledge",
             expr(f"turn_count % {kb_interval} == 0")),
            ("update_objectives", "assemble_context", default),
            ("update_knowledge", "assemble_context", default),
        )
        .with_entrypoint("assemble_context")
        .with_state(initial_state)
    )

    if hooks:
        builder = builder.with_hooks(*hooks)

    if tracker:
        builder = builder.with_tracker(tracker)

    if persist:
        persister = SQLitePersister.from_values(
            db_path="data/burr_state.db",
            table_name="zorkburr_state",
        )
        persister.initialize()
        builder = builder.with_state_persister(persister)

    return builder.build()
