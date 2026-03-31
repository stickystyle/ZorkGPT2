"""Periodic knowledge synthesis: distill gameplay into strategic insights."""
from __future__ import annotations
import logging
import instructor
from zorkburr.actions import action
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.state import S
from zorkburr.llm.client import effective_model, thinking_kwargs

logger = logging.getLogger(__name__)

_KNOWLEDGE_PROMPT = """You are a strategic analyst for an AI playing Zork I.
Analyze the recent gameplay and produce a concise strategic guide.
Focus on: key discoveries, puzzle insights, dangerous areas, useful items, unexplored areas.
Integrate with any existing knowledge — don't duplicate, update.
Return the full updated strategic guide as markdown text (not JSON).
"""

@action(
    reads=[S.KNOWLEDGE_BASE, S.ACTION_HISTORY, S.DISCOVERED_OBJECTIVES,
           S.COMPLETED_OBJECTIVES, S.SCORE, S.TURN_COUNT, S.MEMORIES_BY_LOCATION],
    writes=[S.KNOWLEDGE_BASE],
)
def update_knowledge(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent = state[S.ACTION_HISTORY][-50:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:150]}" for a in recent
    )
    existing = state[S.KNOWLEDGE_BASE]
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n"
        f"Objectives: {state[S.DISCOVERED_OBJECTIVES]}\n"
        f"Completed: {[o['objective'] for o in state[S.COMPLETED_OBJECTIVES]]}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=effective_model(config, config.analysis_model),
            messages=[{"role": "system", "content": _KNOWLEDGE_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=4096,
            **thinking_kwargs(config, use_thinking),
        )
        content = response.choices[0].message.content or ""
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
