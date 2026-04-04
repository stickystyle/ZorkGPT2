"""Periodic knowledge synthesis: distill gameplay into strategic insights."""
from __future__ import annotations
import logging
import re
import instructor
from langfuse import observe
from zorkburr.actions import action
from zorkburr.actions.episode import persist_knowledge
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.state import S
from zorkburr.llm.client import thinking_kwargs
from zorkburr.llm.prompts import load_prompt

logger = logging.getLogger(__name__)

_knowledge_prompt: str | None = None

# Canonical section headers in priority order
_SECTIONS = [
    "Score Changes",
    "Puzzle Mechanics Discovered",
    "Items Found",
    "Dangerous Areas",
    "Failed Approaches",
    "Unexplored Leads",
]


def _get_knowledge_prompt() -> str:
    global _knowledge_prompt
    if _knowledge_prompt is None:
        _knowledge_prompt = load_prompt("knowledge")
    return _knowledge_prompt


def _parse_sections(kb_text: str) -> dict[str, list[str]]:
    """Parse a KB markdown string into {section_name: [bullet_lines]}.

    Handles both **Section:** and **Section** header formats.
    """
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in kb_text.splitlines():
        # Match section headers like **Score Changes:** or **Score Changes**
        header_match = re.match(r'^\*\*(.+?)(?::)?\*\*\s*$', line.strip())
        if header_match:
            current_section = header_match.group(1).strip()
            if current_section not in sections:
                sections[current_section] = []
            continue
        # Collect bullet lines under the current section
        stripped = line.strip()
        if current_section and stripped.startswith(('* ', '- ', '+ ')):
            sections[current_section].append(stripped)
    return sections


def _normalize_bullet(bullet: str) -> str:
    """Normalize a bullet for dedup comparison: lowercase, strip markers/whitespace."""
    text = re.sub(r'^[\*\-\+]\s+', '', bullet.strip())
    # Remove bold markers
    text = text.replace('**', '')
    return text.lower().strip()


def _merge_kb(existing_kb: str, new_kb: str) -> str:
    """Merge new KB entries into existing KB, deduplicating by normalized content.

    Existing entries always survive. New entries are appended per-section.
    """
    existing_sections = _parse_sections(existing_kb)
    new_sections = _parse_sections(new_kb)

    # Build normalized set of existing bullets per section for dedup
    existing_normalized: dict[str, set[str]] = {}
    for section, bullets in existing_sections.items():
        existing_normalized[section] = {_normalize_bullet(b) for b in bullets}

    # Merge new bullets into existing sections
    for section, new_bullets in new_sections.items():
        if section not in existing_sections:
            existing_sections[section] = []
            existing_normalized[section] = set()
        for bullet in new_bullets:
            norm = _normalize_bullet(bullet)
            if norm not in existing_normalized[section]:
                existing_sections[section].append(bullet)
                existing_normalized[section].add(norm)

    # Render merged KB in canonical section order
    lines: list[str] = []
    # First render sections in canonical order
    rendered_sections: set[str] = set()
    for section_name in _SECTIONS:
        bullets = existing_sections.get(section_name, [])
        if bullets:
            if lines:
                lines.append("")
            lines.append(f"**{section_name}:**")
            lines.extend(bullets)
            rendered_sections.add(section_name)
    # Then render any non-canonical sections
    for section_name, bullets in existing_sections.items():
        if section_name not in rendered_sections and bullets:
            if lines:
                lines.append("")
            lines.append(f"**{section_name}:**")
            lines.extend(bullets)

    return "\n".join(lines)


@action(
    reads=[S.KNOWLEDGE_BASE, S.ACTION_HISTORY, S.SCORE, S.TURN_COUNT,
           S.MEMORIES_BY_LOCATION],
    writes=[S.KNOWLEDGE_BASE],
)
@observe()
def update_knowledge(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent = state[S.ACTION_HISTORY][-25:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:150]}" for a in recent
    )
    existing = state[S.KNOWLEDGE_BASE] or ""
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        raw_client, model = client.raw_client_for(config.analysis_model)
        response = raw_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": _get_knowledge_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=1024,
            timeout=config.llm_request_timeout,
            **thinking_kwargs(config, config.analysis_model, False),
        )
        llm_output = response.choices[0].message.content or ""

        # Programmatic merge: existing entries always survive, new entries appended
        if existing.strip():
            content = _merge_kb(existing, llm_output)
            logger.info(
                "KB merge: existing=%d chars, llm_output=%d chars, merged=%d chars",
                len(existing), len(llm_output), len(content),
            )
        else:
            content = llm_output

        persist_knowledge(content, config)
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
