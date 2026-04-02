"""Critic action: object tree validation + LLM scoring with rejection loop."""
from __future__ import annotations
import logging

import instructor
from burr.core import State
from langfuse import observe

from zorkburr.actions import action
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import effective_model, thinking_kwargs
from zorkburr.llm.models import CriticResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

# Verbs that require the object to be visible in the room
TAKE_VERBS = {"take", "get", "grab", "pick"}
# Verbs that require the object to be visible OR in inventory
INTERACT_VERBS = {"close", "drop", "put", "give", "unlock", "light", "turn"}
# Safe exploratory verbs that should always pass object-tree validation.
# These target environmental features (tree, grating, window, ledge) that
# Jericho's get_visible_objects() doesn't list. If the object doesn't exist,
# the parser will say so and the agent learns from the feedback.
SAFE_VERBS = {"examine", "look", "read", "open"}
# Movement words that always pass
MOVEMENT_WORDS = {
    "north", "south", "east", "west", "up", "down",
    "n", "s", "e", "w", "u", "d",
    "ne", "nw", "se", "sw",
    "northeast", "northwest", "southeast", "southwest",
    "go", "walk", "run", "climb", "enter", "exit",
}


def validate_against_object_tree(
    action_text: str, jericho: JerichoInterface
) -> tuple[bool, str]:
    """Fast validation: check if action references objects that exist.

    Returns (is_valid, reason).
    """
    parts = action_text.strip().lower().split()
    if len(parts) <= 1:
        return True, "Single-word command, auto-pass."

    verb = parts[0]
    target = " ".join(parts[1:])

    # Movement commands always pass
    if verb in MOVEMENT_WORDS or target in MOVEMENT_WORDS:
        return True, "Movement command, auto-pass."

    # Safe exploratory verbs always pass — targets may be environmental
    # features (tree, grating, window, ledge) not in Jericho's object tree.
    if verb in SAFE_VERBS:
        return True, f"Safe verb '{verb}', auto-pass."

    visible_objects = jericho.get_visible_objects()
    visible_names = {obj["name"].lower() for obj in visible_objects}
    inventory = jericho.get_inventory()
    inventory_names = {item.lower() for item in inventory}

    if verb in TAKE_VERBS:
        # Target must be in visible objects
        if any(target in name or name in target for name in visible_names):
            return True, f"Object '{target}' is visible."
        return False, f"Object '{target}' is not visible in the current location."

    if verb in INTERACT_VERBS:
        # Target must be visible or in inventory
        all_names = visible_names | inventory_names
        if any(target in name or name in target for name in all_names):
            return True, f"Object '{target}' is visible or in inventory."
        return False, f"Object '{target}' is not visible or in inventory."

    # Unknown verb — let it through
    return True, "Verb not in validation set, auto-pass."


@action(
    reads=[
        S.PROPOSED_ACTION, S.GAME_RESPONSE, S.ACTION_HISTORY, S.EXITS,
        S.INVENTORY, S.LOCATION_NAME, S.REJECTION_COUNT, S.IN_COMBAT,
    ],
    writes=[
        S.CRITIC_SCORE, S.CRITIC_JUSTIFICATION, S.CRITIC_CONFIDENCE,
        S.ACTION_TO_TAKE, S.REJECTION_COUNT,
    ],
)
@observe(capture_input=False)
def evaluate_action(
    state: State,
    llm: instructor.Instructor,
    jericho: JerichoInterface,
    config: GameConfig,
) -> tuple[dict, State]:
    """Evaluate proposed action with object tree check and optional LLM critic."""
    proposed = state[S.PROPOSED_ACTION]
    rejection_count = state[S.REJECTION_COUNT]

    # 1. Fast object tree validation
    is_valid, reason = validate_against_object_tree(proposed, jericho)
    if not is_valid:
        new_state = state.update(**{
            S.CRITIC_SCORE: -1.0,
            S.CRITIC_JUSTIFICATION: reason,
            S.CRITIC_CONFIDENCE: 1.0,
            S.ACTION_TO_TAKE: proposed,
            S.REJECTION_COUNT: rejection_count + 1,
        })
        return {"accepted": False, "reason": reason}, new_state

    # 2. If critic disabled, auto-accept
    if not config.enable_critic:
        new_state = state.update(**{
            S.CRITIC_SCORE: 0.5,
            S.CRITIC_JUSTIFICATION: "Critic disabled, auto-accept.",
            S.CRITIC_CONFIDENCE: 1.0,
            S.ACTION_TO_TAKE: proposed,
            S.REJECTION_COUNT: rejection_count,
        })
        return {"accepted": True, "reason": "critic_disabled"}, new_state

    # 3. LLM evaluation
    system_prompt = load_prompt("critic")

    # Build context for critic
    history = state[S.ACTION_HISTORY]
    recent = history[-3:] if history else []
    recent_lines = []
    for entry in recent:
        recent_lines.append(
            f"  Turn {entry['turn']}: {entry['action']} -> {entry.get('response', '')[:200]}"
        )

    context_parts = [
        f"**Game State:** {state[S.GAME_RESPONSE][:500]}",
        f"**Location:** {state[S.LOCATION_NAME]}",
        f"**Available Exits:** {', '.join(state[S.EXITS]) if state[S.EXITS] else 'unknown'}",
        f"**Inventory:** {', '.join(state[S.INVENTORY]) if state[S.INVENTORY] else '(empty)'}",
        f"**In Combat:** {state[S.IN_COMBAT]}",
    ]
    if recent_lines:
        context_parts.append("**Recent Actions:**\n" + "\n".join(recent_lines))
    context_parts.append(f"\n**Proposed Action:** {proposed}")

    user_content = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        response: CriticResponse = llm.create(
            model=effective_model(config, config.critic_model),
            response_model=CriticResponse,
            messages=messages,
            max_retries=2,
            max_tokens=256,
            **thinking_kwargs(config, False),
        )
        score = response.score
        justification = response.justification
        confidence = response.confidence
    except Exception as e:
        logger.error(f"Critic LLM call failed: {e}")
        # On failure, auto-accept
        score = 0.5
        justification = f"Critic error: {e}"
        confidence = 0.0

    # 4/5. Accept or reject based on threshold
    threshold = config.critic_rejection_threshold
    accepted = score >= threshold

    if accepted:
        new_rejection_count = rejection_count
    else:
        new_rejection_count = rejection_count + 1

    new_state = state.update(**{
        S.CRITIC_SCORE: score,
        S.CRITIC_JUSTIFICATION: justification,
        S.CRITIC_CONFIDENCE: confidence,
        S.ACTION_TO_TAKE: proposed,
        S.REJECTION_COUNT: new_rejection_count,
    })
    return {"accepted": accepted, "reason": justification}, new_state
