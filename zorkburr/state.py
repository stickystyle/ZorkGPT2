"""Burr state schema: key constants and initial state factory."""
from __future__ import annotations
import uuid
from burr.core import State

class S:
    """State key constants."""
    EPISODE_ID = "episode_id"
    TURN_COUNT = "turn_count"
    GAME_RESPONSE = "game_response"
    LOCATION_ID = "location_id"
    LOCATION_NAME = "location_name"
    INVENTORY = "inventory"
    SCORE = "score"
    MAX_SCORE = "max_score"
    GAME_OVER = "game_over"
    GAME_OVER_REASON = "game_over_reason"
    FORMATTED_CONTEXT = "formatted_context"
    PROPOSED_ACTION = "proposed_action"
    AGENT_REASONING = "agent_reasoning"
    NEW_OBJECTIVE = "new_objective"
    ACTION_TO_TAKE = "action_to_take"
    CRITIC_SCORE = "critic_score"
    CRITIC_JUSTIFICATION = "critic_justification"
    CRITIC_CONFIDENCE = "critic_confidence"
    REJECTION_COUNT = "rejection_count"
    WAS_OVERRIDDEN = "was_overridden"
    ACTION_HISTORY = "action_history"
    REASONING_HISTORY = "reasoning_history"
    EXITS = "exits"
    IN_COMBAT = "in_combat"
    IS_ROOM_DESCRIPTION = "is_room_description"
    VISIBLE_OBJECTS = "visible_objects"
    MEMORIES_BY_LOCATION = "memories_by_location"
    MEMORY_STATS = "memory_stats"
    MAP_DATA = "map_data"
    VISITED_LOCATIONS = "visited_locations"
    DISCOVERED_OBJECTIVES = "discovered_objectives"
    COMPLETED_OBJECTIVES = "completed_objectives"
    KNOWLEDGE_BASE = "knowledge_base"
    TURNS_SINCE_PROGRESS = "turns_since_progress"
    LAST_SCORE_CHANGE_TURN = "last_score_change_turn"
    PRE_LOCATION_ID = "pre_location_id"
    PRE_LOCATION_NAME = "pre_location_name"
    PRE_SCORE = "pre_score"
    PRE_INVENTORY = "pre_inventory"

def create_initial_state(episode_id: str | None = None) -> State:
    return State({
        S.EPISODE_ID: episode_id or str(uuid.uuid4())[:8],
        S.TURN_COUNT: 0,
        S.GAME_RESPONSE: "",
        S.LOCATION_ID: 0,
        S.LOCATION_NAME: "",
        S.INVENTORY: [],
        S.SCORE: 0,
        S.MAX_SCORE: 0,
        S.GAME_OVER: False,
        S.GAME_OVER_REASON: "",
        S.FORMATTED_CONTEXT: "",
        S.PROPOSED_ACTION: "",
        S.AGENT_REASONING: "",
        S.NEW_OBJECTIVE: "",
        S.ACTION_TO_TAKE: "",
        S.CRITIC_SCORE: 0.0,
        S.CRITIC_JUSTIFICATION: "",
        S.CRITIC_CONFIDENCE: 0.0,
        S.REJECTION_COUNT: 0,
        S.WAS_OVERRIDDEN: False,
        S.ACTION_HISTORY: [],
        S.REASONING_HISTORY: [],
        S.EXITS: [],
        S.IN_COMBAT: False,
        S.IS_ROOM_DESCRIPTION: False,
        S.VISIBLE_OBJECTS: [],
        S.MEMORIES_BY_LOCATION: {},
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.MAP_DATA: {},
        S.VISITED_LOCATIONS: [],
        S.DISCOVERED_OBJECTIVES: [],
        S.COMPLETED_OBJECTIVES: [],
        S.KNOWLEDGE_BASE: "",
        S.TURNS_SINCE_PROGRESS: 0,
        S.LAST_SCORE_CHANGE_TURN: 0,
        S.PRE_LOCATION_ID: 0,
        S.PRE_LOCATION_NAME: "",
        S.PRE_SCORE: 0,
        S.PRE_INVENTORY: [],
    })
