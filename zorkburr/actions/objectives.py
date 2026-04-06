"""Objective discovery, completion checking."""
from __future__ import annotations
import logging
import instructor
from langfuse import observe
from zorkburr.actions import action
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.llm.client import thinking_kwargs
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


def _resolve_location_id(name: str, current_loc_name: str, current_loc_id: int,
                          rooms: dict[str, str]) -> int:
    """Resolve a location name to its numeric ID using the map data.

    Tries exact match first, then case-insensitive, then substring/prefix
    matching. Returns 0 if no match found.
    """
    if not name:
        return 0
    # Check current location first
    norm = name.strip().lower()
    if norm == current_loc_name.strip().lower() and current_loc_id != 0:
        return current_loc_id
    # Exact match
    for room_id_str, room_name in rooms.items():
        if room_name.strip().lower() == norm:
            return int(room_id_str)
    # Fuzzy: one is a substring of the other (handles "Living" vs "Living Room")
    for room_id_str, room_name in rooms.items():
        rn = room_name.strip().lower()
        if norm in rn or rn in norm:
            return int(room_id_str)
    return 0


@action(
    reads=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES, S.ACTION_HISTORY,
           S.GAME_RESPONSE, S.SCORE, S.LOCATION_NAME, S.LOCATION_ID, S.TURN_COUNT, S.KNOWLEDGE_BASE,
           S.MAP_DATA],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
@observe()
def update_objectives(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent_actions = state[S.ACTION_HISTORY][-10:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:200]}" for a in recent_actions
    )
    current_objectives = state[S.DISCOVERED_OBJECTIVES]
    current_texts = [_obj_text(o) for o in current_objectives]
    kb_content = state[S.KNOWLEDGE_BASE] or ""
    kb_section = f"\n\nStrategic Knowledge (accumulated from prior episodes):\n{kb_content}" if kb_content else ""
    user_msg = (
        f"Current location: {state[S.LOCATION_NAME]} (ID: {state[S.LOCATION_ID]})\nScore: {state[S.SCORE]}\n"
        f"Current objectives: {current_texts}\n\nRecent gameplay:\n{action_summary}"
        f"{kb_section}"
    )
    try:
        response: ObjectiveDiscoveryResponse = client.create(
            model=config.analysis_model,
            response_model=ObjectiveDiscoveryResponse,
            messages=[{"role": "system", "content": _get_discovery_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=512, max_retries=2,
            **thinking_kwargs(config, config.analysis_model, use_thinking),
        )
        # Resolve location_id from location_name using map data
        map_data = state[S.MAP_DATA]
        rooms = map_data.get("rooms", {})
        cur_loc_name = state[S.LOCATION_NAME]
        cur_loc_id = state[S.LOCATION_ID]
        for obj in response.objectives:
            if obj.location_id == 0 and obj.location_name:
                resolved = _resolve_location_id(obj.location_name, cur_loc_name, cur_loc_id, rooms)
                if resolved != 0:
                    obj.location_id = resolved
                    logger.debug(f"Resolved objective location '{obj.location_name}' -> ID {resolved}")

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
@observe()
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
            model=config.analysis_model, response_model=ObjectiveCompletionResponse,
            messages=[{"role": "system", "content": _get_completion_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.0, max_tokens=256, max_retries=2,
            **thinking_kwargs(config, config.analysis_model, False),
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
