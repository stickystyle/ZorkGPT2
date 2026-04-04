"""Extract turn-state fixtures from the Burr tracker for prompt validation.

Usage:
  python3 scripts/extract_fixtures.py <app_id> --turns 37,42,45 \
    --action generate_action --role problem \
    --description "Agent ignored location memories"
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _args import fetch_steps, get_state, get_action

# Map action_type -> (state keys to capture, output keys to capture)
ACTION_SCHEMA = {
    "generate_action": {
        "state_keys": [
            "formatted_context", "rejection_count", "critic_justification",
            "knowledge_base", "turn_count",
        ],
        "output_keys": [
            "proposed_action", "agent_reasoning", "next_steps", "new_objective",
        ],
    },
    "evaluate_action": {
        "state_keys": [
            "proposed_action", "game_response", "action_history", "exits",
            "inventory", "location_name", "rejection_count", "in_combat",
        ],
        "output_keys": [
            "critic_score", "critic_justification", "critic_confidence",
        ],
    },
    "record_memory": {
        "state_keys": [
            "pre_location_id", "pre_location_name", "pre_score", "pre_inventory",
            "location_id", "score", "inventory", "game_over", "game_over_reason",
            "game_response", "action_to_take", "agent_reasoning", "action_history",
            "memories_by_location", "episode_id", "turn_count", "memory_stats",
            "location_summaries",
        ],
        "output_keys": [
            "memories_by_location", "memory_stats", "location_summaries",
        ],
    },
    "update_knowledge": {
        "state_keys": [
            "knowledge_base", "action_history", "score", "turn_count",
            "memories_by_location",
        ],
        "output_keys": ["knowledge_base"],
    },
    "extract_info": {
        "state_keys": [
            "game_response", "location_name", "location_id", "in_combat",
        ],
        "output_keys": [
            "exits", "in_combat", "is_room_description", "visible_objects",
        ],
    },
    "update_objectives": {
        "state_keys": [
            "discovered_objectives", "completed_objectives", "action_history",
            "game_response", "score", "location_name", "location_id",
            "turn_count", "knowledge_base",
        ],
        "output_keys": ["discovered_objectives", "completed_objectives"],
    },
    "check_objective_completion": {
        "state_keys": [
            "discovered_objectives", "completed_objectives", "game_response",
            "action_to_take", "turn_count", "score", "pre_score",
        ],
        "output_keys": ["discovered_objectives", "completed_objectives"],
    },
}
