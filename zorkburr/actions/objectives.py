"""Objective discovery, completion checking."""
from __future__ import annotations
import logging
import instructor
from zorkburr.actions import action
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.llm.client import effective_model, nothink_prefix, thinking_kwargs
from zorkburr.state import S

logger = logging.getLogger(__name__)

_DISCOVERY_PROMPT = """You are analyzing a Zork I game session to discover objectives.
Based on the recent gameplay, identify 1-5 actionable objectives the player should pursue.
Objectives should be specific and achievable (e.g., "Open the trapdoor" not "Win the game").
"""

_COMPLETION_PROMPT = """Given the most recent action and response in Zork I, determine which objectives (if any) have been completed.
Only mark objectives as completed if there is clear evidence in the game response.
"""

@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.ACTION_HISTORY,
           S.GAME_RESPONSE, S.SCORE, S.LOCATION_NAME, S.TURN_COUNT, S.KNOWLEDGE_BASE],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def update_objectives(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent_actions = state[S.ACTION_HISTORY][-10:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:200]}" for a in recent_actions
    )
    current_objectives = state[S.DISCOVERED_OBJECTIVES]
    user_msg = (
        f"Current location: {state[S.LOCATION_NAME]}\nScore: {state[S.SCORE]}\n"
        f"Current objectives: {current_objectives}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        response: ObjectiveDiscoveryResponse = client.create(
            model=effective_model(config, config.analysis_model),
            response_model=ObjectiveDiscoveryResponse,
            messages=[{"role": "system", "content": nothink_prefix(config, False) + _DISCOVERY_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=256, max_retries=2,
            **thinking_kwargs(config, False),
        )
        new_objectives = response.objectives
        completed = set(response.completed)
        updated = [o for o in current_objectives if o not in completed]
        for o in new_objectives:
            if o not in updated:
                updated.append(o)
        updated = updated[:15]
        completed_records = list(state[S.COMPLETED_OBJECTIVES])
        for obj in completed:
            completed_records.append({"objective": obj, "completed_turn": state[S.TURN_COUNT]})
        return (
            {"new_count": len(new_objectives)},
            state.update(**{S.DISCOVERED_OBJECTIVES: updated, S.COMPLETED_OBJECTIVES: completed_records}),
        )
    except Exception as e:
        logger.warning(f"Objective update failed: {e}")
    return {"new_count": 0}, state

@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.GAME_RESPONSE,
           S.ACTION_TO_TAKE, S.TURN_COUNT, S.SCORE],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def check_objective_completion(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    objectives = state[S.DISCOVERED_OBJECTIVES]
    if not objectives:
        return {"completed": []}, state
    user_msg = (
        f"Active objectives: {objectives}\n\nAction taken: {state[S.ACTION_TO_TAKE]}\n"
        f"Game response: {state[S.GAME_RESPONSE][:500]}\nCurrent score: {state[S.SCORE]}"
    )
    try:
        response: ObjectiveCompletionResponse = client.create(
            model=effective_model(config, config.analysis_model), response_model=ObjectiveCompletionResponse,
            messages=[{"role": "system", "content": nothink_prefix(config, False) + _COMPLETION_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.0, max_tokens=256, max_retries=2,
            **thinking_kwargs(config, False),
        )
        completed = set(response.completed_objectives)
        if completed:
            remaining = [o for o in objectives if o not in completed]
            records = list(state[S.COMPLETED_OBJECTIVES])
            for obj in completed:
                records.append({"objective": obj, "completed_turn": state[S.TURN_COUNT]})
            return (
                {"completed": list(completed)},
                state.update(**{S.DISCOVERED_OBJECTIVES: remaining, S.COMPLETED_OBJECTIVES: records}),
            )
    except Exception as e:
        logger.warning(f"Completion check failed: {e}")
    return {"completed": []}, state
