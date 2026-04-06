"""Grounding validation: reject hallucinated memories and objectives."""
from __future__ import annotations
import logging

import instructor

from zorkburr.config import GameConfig
from zorkburr.llm.client import thinking_kwargs
from zorkburr.llm.models import GroundingValidationResponse
from zorkburr.llm.prompts import load_prompt

logger = logging.getLogger(__name__)

_grounding_prompt: str | None = None

MEMORY_ADDENDUM = """
## Memory-Specific Rules
- Items listed in the player's inventory are CARRIED by the player. They are NOT native to the current location. Only validate a memory claiming an item is "found here" if the game response explicitly describes the item as present in the room (on a table, in a corner, etc.).
- Mechanics described must match the actual game response. If the game said "The door is locked," the memory should not claim "The door opens easily."
- Score changes must correspond to the action that was actually taken, not an invented cause.
"""

OBJECTIVE_ADDENDUM = """
## Objective-Specific Rules
- Every item, NPC, or location referenced in the objective must have appeared in the recent game text.
- Parser prompts like "What do you want to unlock with?" do NOT reveal which tool to use. Do not validate objectives that name specific tools not yet seen in game output.
- Objectives must describe actions based on observed game state, not inferred puzzle solutions or general game knowledge.
"""


def _get_grounding_prompt() -> str:
    global _grounding_prompt
    if _grounding_prompt is None:
        _grounding_prompt = load_prompt("grounding_validator")
    return _grounding_prompt


def _call_grounding_validator(
    client: instructor.Instructor,
    config: GameConfig,
    candidates: list[dict],
    addendum: str,
    action_history: list[dict],
    location_name: str,
    location_id: int,
    inventory: list[str],
) -> GroundingValidationResponse:
    """Call the grounding validator LLM with the shared prompt + type-specific addendum."""
    prompt = _get_grounding_prompt().replace("{grounding_rules}", addendum)

    recent = action_history[-5:]
    history_lines = []
    for entry in recent:
        history_lines.append(
            f"Turn {entry['turn']}: Action: {entry['action']}\n"
            f"  Response: {entry.get('response', '')[:300]}"
        )

    inv_str = ", ".join(inventory) if inventory else "(empty)"
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(f"- {c['item']}")

    user_content = (
        f"**Current Location:** {location_name} (ID: {location_id})\n"
        f"**Inventory:** {inv_str}\n\n"
        f"**Recent Game History:**\n" + "\n".join(history_lines) + "\n\n"
        f"**Candidates to validate:**\n" + "\n".join(candidate_lines)
    )

    return client.create(
        model=config.critic_model,
        response_model=GroundingValidationResponse,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=512,
        max_retries=2,
        **thinking_kwargs(config, config.critic_model, False),
    )
