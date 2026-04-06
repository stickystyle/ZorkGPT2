"""Grounding validation: reject hallucinated memories and objectives."""
from __future__ import annotations
import logging

import instructor
from langfuse import observe

from zorkburr.actions import action
from zorkburr.actions.episode import persist_memories, persist_summaries
from zorkburr.actions.memory import generate_location_summary
from zorkburr.config import GameConfig
from zorkburr.llm.client import thinking_kwargs
from zorkburr.llm.models import GroundingValidationResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S, State

logger = logging.getLogger(__name__)

_grounding_prompt: str | None = None

MEMORY_ADDENDUM = """
## Memory-Specific Rules
- Items listed in the player's inventory are CARRIED by the player. They are NOT native to the current location. Only validate a memory claiming an item is "found here" if the game response explicitly describes the item as present in the room (on a table, in a corner, etc.).
- Mechanics described must match the actual game response. If the game said "The door is locked," the memory should not claim "The door opens easily."
- Score changes must correspond to the action that was actually taken, not an invented cause.
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
    score: int = 0,
    pre_score: int = 0,
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

    score_delta = score - pre_score
    score_line = f"**Score:** {pre_score} -> {score} (delta: {score_delta:+d} this turn)\n"

    user_content = (
        f"**Current Location:** {location_name} (ID: {location_id})\n"
        f"{score_line}"
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


def _commit_memory(state: State, pending: dict, config: GameConfig, client: instructor.Instructor) -> tuple[dict, State]:
    """Commit a validated pending memory to state. Handles supersession, stats, summaries."""
    mem_dict = pending["memory"]
    loc_key = pending["loc_key"]
    supersedes_titles = pending.get("supersedes_titles", [])

    all_mems = dict(state[S.MEMORIES_BY_LOCATION])
    loc_list = list(all_mems.get(loc_key, []))

    # Process supersession
    superseded_count = 0
    for old_title in supersedes_titles:
        for m in loc_list:
            if m.get("title") == old_title and m.get("status") != "SUPERSEDED":
                m["status"] = "SUPERSEDED"
                m["superseded_by"] = mem_dict["title"]
                logger.info(f"Superseded memory '{old_title}' with '{mem_dict['title']}' at location {loc_key}")
                superseded_count += 1
                break

    loc_list.append(mem_dict)
    all_mems[loc_key] = loc_list
    persist_memories(all_mems, config)

    # Regenerate location summary
    summaries = dict(state[S.LOCATION_SUMMARIES])
    summary = generate_location_summary(
        loc_key, state[S.PRE_LOCATION_NAME], loc_list, client, config,
    )
    if summary:
        summaries[loc_key] = summary
        persist_summaries(summaries, config)

    stats = dict(state[S.MEMORY_STATS])
    stats["new"] = stats.get("new", 0) + 1
    stats["superseded"] = stats.get("superseded", 0) + superseded_count

    new_state = state.update(**{
        S.MEMORIES_BY_LOCATION: all_mems,
        S.MEMORY_STATS: stats,
        S.LOCATION_SUMMARIES: summaries,
        S.PENDING_MEMORY: None,
    })
    return {"validated": True, "memory_title": mem_dict["title"]}, new_state


@action(
    reads=[S.PENDING_MEMORY, S.ACTION_HISTORY, S.LOCATION_NAME, S.LOCATION_ID,
           S.INVENTORY, S.MEMORIES_BY_LOCATION, S.MEMORY_STATS,
           S.LOCATION_SUMMARIES, S.PRE_LOCATION_NAME, S.EPISODE_ID, S.TURN_COUNT,
           S.SCORE, S.PRE_SCORE],
    writes=[S.MEMORIES_BY_LOCATION, S.MEMORY_STATS, S.LOCATION_SUMMARIES, S.PENDING_MEMORY],
)
@observe()
def validate_memory(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    """Validate a pending memory against recent game output. Accept or drop."""
    pending = state[S.PENDING_MEMORY]
    if not pending:
        return {"validated": False, "reason": "no_pending"}, state

    # If validator disabled, commit unconditionally
    if not config.enable_grounding_validator:
        return _commit_memory(state, pending, config, client)

    mem_dict = pending["memory"]
    try:
        response = _call_grounding_validator(
            client=client,
            config=config,
            candidates=[{"item": f"{mem_dict['title']}: {mem_dict['text']}"}],
            addendum=MEMORY_ADDENDUM,
            action_history=state[S.ACTION_HISTORY],
            location_name=state[S.LOCATION_NAME],
            location_id=state[S.LOCATION_ID],
            inventory=state[S.INVENTORY],
            score=state[S.SCORE],
            pre_score=state[S.PRE_SCORE],
        )
        if response.judgments and response.judgments[0].grounded:
            logger.info(f"Grounding accepted memory: '{mem_dict['title']}'")
            return _commit_memory(state, pending, config, client)
        else:
            reason = response.judgments[0].reason if response.judgments else "no judgment returned"
            logger.info(f"Grounding rejected memory: '{mem_dict['title']}' — {reason}")
            stats = dict(state[S.MEMORY_STATS])
            stats["grounding_rejected"] = stats.get("grounding_rejected", 0) + 1
            return (
                {"validated": False, "reason": "ungrounded"},
                state.update(**{S.PENDING_MEMORY: None, S.MEMORY_STATS: stats}),
            )
    except Exception as e:
        logger.warning(f"Grounding validation failed for memory '{mem_dict['title']}': {e}")
        # On error, commit anyway (fail open)
        return _commit_memory(state, pending, config, client)
