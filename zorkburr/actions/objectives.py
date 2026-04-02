"""Objective discovery, completion checking."""
from __future__ import annotations
import logging
import instructor
from zorkburr.actions import action
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.llm.client import effective_model, thinking_kwargs
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

_discovery_prompt: str | None = None
_completion_prompt: str | None = None

def _get_discovery_prompt() -> str:
    global _discovery_prompt
    if _discovery_prompt is None:
        _discovery_prompt = load_prompt("objective_discovery")
    return _discovery_prompt

def _get_completion_prompt() -> str:
    global _completion_prompt
    if _completion_prompt is None:
        _completion_prompt = load_prompt("objective_completion")
    return _completion_prompt

def _obj_text(o: object) -> str:
    """Extract text from an objective (dict or legacy string)."""
    return o["text"] if isinstance(o, dict) else str(o)


@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.ACTION_HISTORY,
           S.GAME_RESPONSE, S.SCORE, S.LOCATION_NAME, S.LOCATION_ID, S.TURN_COUNT, S.KNOWLEDGE_BASE],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def update_objectives(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent_actions = state[S.ACTION_HISTORY][-10:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:200]}" for a in recent_actions
    )
    current_objectives = state[S.DISCOVERED_OBJECTIVES]
    current_texts = [_obj_text(o) for o in current_objectives]
    user_msg = (
        f"Current location: {state[S.LOCATION_NAME]} (ID: {state[S.LOCATION_ID]})\nScore: {state[S.SCORE]}\n"
        f"Current objectives: {current_texts}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        response: ObjectiveDiscoveryResponse = client.create(
            model=effective_model(config, config.analysis_model),
            response_model=ObjectiveDiscoveryResponse,
            messages=[{"role": "system", "content": _get_discovery_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=512, max_retries=2,
            **thinking_kwargs(config, False),
        )
        completed = set(response.completed)
        updated = [o for o in current_objectives if _obj_text(o) not in completed]
        existing_texts = {_obj_text(o) for o in updated}
        for obj in response.objectives:
            if obj.text not in existing_texts:
                updated.append({"text": obj.text, "location_id": obj.location_id, "location_name": obj.location_name})
                existing_texts.add(obj.text)
        updated = updated[:15]
        completed_records = list(state[S.COMPLETED_OBJECTIVES])
        for obj_text in completed:
            completed_records.append({"objective": obj_text, "completed_turn": state[S.TURN_COUNT]})
        return (
            {"new_count": len(response.objectives)},
            state.update(**{S.DISCOVERED_OBJECTIVES: updated, S.COMPLETED_OBJECTIVES: completed_records}),
        )
    except Exception as e:
        logger.warning(f"Objective update failed: {e}")
    return {"new_count": 0}, state

@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.GAME_RESPONSE,
           S.ACTION_TO_TAKE, S.TURN_COUNT, S.SCORE, S.PRE_SCORE],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def check_objective_completion(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    objectives = state[S.DISCOVERED_OBJECTIVES]
    if not objectives:
        return {"completed": []}, state
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    # Send text-only list to the LLM for completion matching
    obj_texts = [_obj_text(o) for o in objectives]
    user_msg = (
        f"Active objectives: {obj_texts}\n\nAction taken: {state[S.ACTION_TO_TAKE]}\n"
        f"Game response: {state[S.GAME_RESPONSE][:500]}\nCurrent score: {state[S.SCORE]}"
        f" (changed by {score_delta:+d} this turn)"
    )
    try:
        response: ObjectiveCompletionResponse = client.create(
            model=effective_model(config, config.analysis_model), response_model=ObjectiveCompletionResponse,
            messages=[{"role": "system", "content": _get_completion_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.0, max_tokens=256, max_retries=2,
            **thinking_kwargs(config, False),
        )
        completed = set(response.completed_objectives)
        if completed:
            remaining = [o for o in objectives if _obj_text(o) not in completed]
            records = list(state[S.COMPLETED_OBJECTIVES])
            for obj_text in completed:
                records.append({"objective": obj_text, "completed_turn": state[S.TURN_COUNT]})
            return (
                {"completed": list(completed)},
                state.update(**{S.DISCOVERED_OBJECTIVES: remaining, S.COMPLETED_OBJECTIVES: records}),
            )
    except Exception as e:
        logger.warning(f"Completion check failed: {e}")
    return {"completed": []}, state
