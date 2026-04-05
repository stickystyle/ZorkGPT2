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


def _enforce_verified_scores(kb_text: str, verified_bullets: list[str]) -> str:
    """Replace the Score Changes section with only verified entries and
    remove hallucinated score claims from other sections.

    This is a structural guardrail: the Score Changes section is entirely
    controlled by Python-computed data, not by LLM output.  Any hallucinated
    score entries that survived the merge are removed here.
    """
    # Build set of verified action verbs for cross-reference
    verified_actions: set[str] = set()
    for bullet in verified_bullets:
        # Extract action from "- <action> at <location> (score ...)"
        m = re.match(r'^-\s+(.+?)\s+at\s+', bullet)
        if m:
            verified_actions.add(m.group(1).strip().lower())

    sections = _parse_sections(kb_text)

    # If the text has no parseable sections, return it as-is — nothing to enforce
    if not sections:
        return kb_text

    # 1. Overwrite Score Changes with verified data (or remove if empty)
    if verified_bullets:
        sections["Score Changes"] = verified_bullets
    else:
        sections.pop("Score Changes", None)

    # 2. Remove bullets in OTHER sections that contain hallucinated score claims
    #    A bullet with "(score +N)" or "(score -N)" that doesn't match any
    #    verified action is a hallucination leak from the Score Changes section.
    _score_claim_re = re.compile(r'\(score\s+[+\-]?\d+\)', re.IGNORECASE)
    for section_name, bullets in sections.items():
        if section_name == "Score Changes":
            continue
        filtered = []
        for bullet in bullets:
            if _score_claim_re.search(bullet):
                # Check if any verified action appears in this bullet
                bullet_lower = bullet.lower()
                if not any(action in bullet_lower for action in verified_actions):
                    logger.info("Removed hallucinated score claim from %s: %s", section_name, bullet.strip())
                    continue
            filtered.append(bullet)
        sections[section_name] = filtered

    # Re-render in canonical order
    lines: list[str] = []
    rendered: set[str] = set()
    for section_name in _SECTIONS:
        bullets = sections.get(section_name, [])
        if bullets:
            if lines:
                lines.append("")
            lines.append(f"**{section_name}:**")
            lines.extend(bullets)
            rendered.add(section_name)
    for section_name, bullets in sections.items():
        if section_name not in rendered and bullets:
            if lines:
                lines.append("")
            lines.append(f"**{section_name}:**")
            lines.extend(bullets)
    return "\n".join(lines)


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
    recent = state[S.ACTION_HISTORY]
    lines = []
    for a in recent:
        delta = a.get('score_after', 0) - a.get('score_before', 0)
        score_tag = f" [SCORE: {a.get('score_before', '?')}→{a.get('score_after', '?')}, {delta:+d}]" if delta != 0 else ""
        lines.append(f"Turn {a['turn']} [{a.get('location_name', '?')}]: {a['action']} -> {a.get('response', '')[:150]}{score_tag}")
    action_summary = "\n".join(lines)

    # Pre-compute verified score changes from FULL action history (Python, not LLM)
    all_history = state[S.ACTION_HISTORY]
    verified_score_bullets: list[str] = []
    for a in all_history:
        delta = a.get('score_after', 0) - a.get('score_before', 0)
        if delta != 0:
            loc_name = a.get('location_name', 'Unknown')
            verified_score_bullets.append(f"- {a['action']} at {loc_name} (score {a.get('score_before')}→{a.get('score_after')}, {delta:+d})")
    verified_scores = "\n".join(verified_score_bullets) if verified_score_bullets else "(no score changes in this episode)"

    existing = state[S.KNOWLEDGE_BASE] or ""
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n\n"
        f"VERIFIED SCORE CHANGES (computed from game engine — these are the ONLY score changes that occurred):\n{verified_scores}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        kb_model = config.knowledge_model or config.analysis_model
        raw_client, model = client.raw_client_for(kb_model)
        response = raw_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": _get_knowledge_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.2, max_tokens=2048,
            timeout=config.llm_request_timeout,
            **thinking_kwargs(config, kb_model, False),
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

        # Structural guardrail: replace Score Changes section with verified data
        content = _enforce_verified_scores(content, verified_score_bullets)

        persist_knowledge(content, config)
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
