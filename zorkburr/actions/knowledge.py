"""Periodic knowledge synthesis: distill gameplay into strategic insights."""
from __future__ import annotations
import logging
import instructor
from zorkburr.actions import action
from zorkburr.actions.episode import persist_knowledge
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.state import S
from zorkburr.llm.client import effective_model, thinking_kwargs

logger = logging.getLogger(__name__)

_KNOWLEDGE_PROMPT = """You are reviewing a gameplay log from a text adventure. Summarize what happened.

STRICT RULES:
1. ONLY describe events that appear in the gameplay log below. Every claim must cite a turn number.
2. NEVER add knowledge from outside the log. You likely know this game — ignore that knowledge entirely.
3. BAD examples (NEVER write these): "In this game, the key is usually found...", "The nest contains...", "You need to go to X to find Y", "The standard solution is..."
4. GOOD examples: "Turn 8: took egg from tree (score +5)", "Turns 40-43: entered house via window, score increased to 15", "Dark staircase at Kitchen requires light source (tried at turn 55, got 'too dark')"

FORMAT: List events by turn number. Group by location. Note: score changes, items found, failed actions, areas not yet explored.
Do NOT speculate about what the agent should do next or where items might be. Only record what happened.
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
            temperature=0.7, max_tokens=1024,
            **thinking_kwargs(config, False),
        )
        content = response.choices[0].message.content or ""
        persist_knowledge(content, config)
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
