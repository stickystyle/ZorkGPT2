"""Export Burr state to JSON-serializable dict for the viewer."""
from __future__ import annotations

from datetime import datetime, timezone

from burr.core import State

from zorkburr.state import S


def export_turn_state(state: State) -> dict:
    """Convert current Burr state into a viewer-friendly JSON dict."""
    location_id = state[S.LOCATION_ID]
    memories_by_loc = state[S.MEMORIES_BY_LOCATION]
    # Look up memories for current location (keys may be str or int)
    memories_here = (
        memories_by_loc.get(str(location_id), [])
        or memories_by_loc.get(location_id, [])
    )

    map_data = state[S.MAP_DATA]
    rooms = map_data.get("rooms", {}) if map_data else {}
    connections = map_data.get("connections", {}) if map_data else {}

    # Ensure room keys are strings for JSON serialization
    str_rooms = {str(k): v for k, v in rooms.items()}
    str_connections = {
        str(k): v for k, v in connections.items()
    }

    # Build confidence with string keys (source may have tuple keys)
    raw_confidence = map_data.get("confidence", {}) if map_data else {}
    str_confidence = {}
    for k, v in raw_confidence.items():
        if isinstance(k, tuple):
            str_confidence[f"{k[0]}:{k[1]}"] = v
        else:
            str_confidence[str(k)] = v

    action_history = state[S.ACTION_HISTORY]
    recent = action_history[-50:] if len(action_history) > 50 else list(action_history)

    return {
        "metadata": {
            "episode_id": state[S.EPISODE_ID],
            "turn": state[S.TURN_COUNT],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "game_over": state[S.GAME_OVER],
            "game_over_reason": state[S.GAME_OVER_REASON],
            "score": state[S.SCORE],
            "max_score": state[S.MAX_SCORE],
        },
        "turn_data": {
            "action": state[S.ACTION_TO_TAKE],
            "game_response": state[S.GAME_RESPONSE],
            "agent_reasoning": state[S.AGENT_REASONING],
            "critic_score": state[S.CRITIC_SCORE],
            "critic_justification": state[S.CRITIC_JUSTIFICATION],
            "critic_confidence": state[S.CRITIC_CONFIDENCE],
            "was_overridden": state[S.WAS_OVERRIDDEN],
            "rejection_count": state[S.REJECTION_COUNT],
        },
        "game_state": {
            "location_name": state[S.LOCATION_NAME],
            "location_id": location_id,
            "inventory": state[S.INVENTORY],
            "exits": state[S.EXITS],
            "in_combat": state[S.IN_COMBAT],
            "visible_objects": state[S.VISIBLE_OBJECTS],
            "turns_since_progress": state[S.TURNS_SINCE_PROGRESS],
        },
        "strategic": {
            "discovered_objectives": state[S.DISCOVERED_OBJECTIVES],
            "completed_objectives": state[S.COMPLETED_OBJECTIVES],
            "knowledge_base": state[S.KNOWLEDGE_BASE],
            "memories_at_location": memories_here,
        },
        "map": {
            "rooms": str_rooms,
            "connections": str_connections,
            "confidence": str_confidence,
            "current_room": location_id,
            "visited_count": len(state[S.VISITED_LOCATIONS]),
            "total_rooms": len(str_rooms),
        },
        "recent_history": recent,
    }
