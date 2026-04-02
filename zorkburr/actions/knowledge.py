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
from zorkburr.llm.prompts import load_prompt

logger = logging.getLogger(__name__)

_knowledge_prompt: str | None = None

def _get_knowledge_prompt() -> str:
    global _knowledge_prompt
    if _knowledge_prompt is None:
        _knowledge_prompt = load_prompt("knowledge")
    return _knowledge_prompt

@action(
    reads=[S.KNOWLEDGE_BASE, S.ACTION_HISTORY, S.SCORE, S.TURN_COUNT,
           S.MEMORIES_BY_LOCATION],
    writes=[S.KNOWLEDGE_BASE],
)
def update_knowledge(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent = state[S.ACTION_HISTORY][-50:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:150]}" for a in recent
    )
    existing = state[S.KNOWLEDGE_BASE]
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=effective_model(config, config.analysis_model),
            messages=[{"role": "system", "content": _get_knowledge_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=1024,
            **thinking_kwargs(config, False),
        )
        content = response.choices[0].message.content or ""
        persist_knowledge(content, config)
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
