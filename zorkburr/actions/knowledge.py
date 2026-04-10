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


def _dedup_items_found(kb_text: str) -> str:
    """Deduplicate the Items Found section: one entry per unique item.

    For each bullet in Items Found, extract the item name (text before the
    first " — " or " at " delimiter), keep only the first occurrence per
    item name, and strip transient drop/movement annotations from the kept
    entry.

    All other sections are left untouched.
    """
    sections = _parse_sections(kb_text)
    if "Items Found" not in sections:
        return kb_text

    items_bullets = sections["Items Found"]
    seen_items: dict[str, str] = {}  # item_name_lower -> cleaned bullet
    for bullet in items_bullets:
        # Strip the bullet marker to get raw text
        raw = re.sub(r'^[\*\-\+]\s+', '', bullet.strip())
        # Extract item name: text before " — " or " at "
        item_match = re.split(r'\s+[—–]\s+|\s+at\s+', raw, maxsplit=1)
        item_name = item_match[0].strip().rstrip('.').lower()
        if item_name in seen_items:
            continue  # keep only the first entry per item
        # Strip transient drop/movement annotations from the kept entry.
        # These appear after "(taken...)" as "; dropped ...", "; left ...",
        # "; lost ...", "; deposited ...", "; placed ...", "; re-taken ...",
        # or standalone "dropped in ..." entries with no spawn location.
        cleaned = re.sub(
            r';\s*(?:dropped|left|lost|deposited|placed|re-taken|moved)\b[^)]*',
            '',
            bullet,
        )
        # Also clean up note annotations that leak episode-specific info
        cleaned = re.sub(
            r';\s*note:\s*score change not in verified list[^)]*',
            '',
            cleaned,
        )
        # Clean up trailing whitespace inside parens and dangling semicolons
        cleaned = re.sub(r';\s*\)', ')', cleaned)
        cleaned = re.sub(r'\(\s*\)', '', cleaned)  # remove empty parens
        cleaned = cleaned.rstrip('. ').rstrip()
        # If the bullet was just "- Item — dropped in X" with no spawn info, skip it
        if re.match(r'^[\*\-\+]\s+\S.*\s+[—–]\s+dropped\s', bullet.strip()):
            continue
        seen_items[item_name] = cleaned

    sections["Items Found"] = list(seen_items.values())

    # Re-render in canonical order (same logic as _enforce_verified_scores)
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


def _dedup_freetext_sections(kb_text: str) -> str:
    """Deduplicate free-text sections (Puzzle Mechanics, Dangerous Areas, etc.).

    Unlike Items Found (which has natural item-name keys), these sections
    contain free-text bullets where duplicates arise from:
    - Room ID annotations: (R1), (R38), (R215) present/absent
    - Trailing period vs no period
    - Em-dash vs hyphen variations
    - Slight wording differences with identical semantic content

    Strategy: Two-pass dedup.
    1. Prefix match: group by first 50 chars of normalized text.
    2. Word-overlap match: for remaining bullets, compute Jaccard similarity
       on word sets; merge bullets with >0.7 overlap.
    When duplicates are found, keep the MOST DETAILED version (longest after
    normalization).

    Applies to all sections EXCEPT Score Changes (Python-controlled) and
    Items Found (has its own dedup).
    """
    _SKIP_SECTIONS = {"Score Changes", "Items Found"}
    # Non-canonical sections that are stale per-episode state and should be removed
    _STALE_SECTIONS = {"Current situation", "Immediate plan"}

    sections = _parse_sections(kb_text)
    if not sections:
        return kb_text

    # Remove stale per-episode sections
    for stale in _STALE_SECTIONS:
        if stale in sections:
            logger.info("Removed stale section '%s' (%d bullets)", stale, len(sections[stale]))
            del sections[stale]

    for section_name, bullets in sections.items():
        if section_name in _SKIP_SECTIONS:
            continue
        if len(bullets) < 2:
            continue

        sections[section_name] = _dedup_bullet_list(bullets)
        if len(sections[section_name]) < len(bullets):
            logger.info(
                "Deduped section '%s': %d -> %d bullets",
                section_name, len(bullets), len(sections[section_name]),
            )

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


def _dedup_bullet_list(bullets: list[str]) -> list[str]:
    """Deduplicate a list of bullets using prefix + word-overlap matching.

    Pass 1 (prefix): Group by first 50 chars of normalized text. From each
    group, keep the longest (most detailed) entry.

    Pass 2 (word overlap): For remaining bullets, compute Jaccard similarity
    on word-sets; merge pairs with >0.7 overlap, keeping the longer one.
    """
    # Pass 1: prefix grouping
    PREFIX_LEN = 50
    groups: dict[str, list[tuple[str, str]]] = {}  # prefix -> [(norm, original)]
    for bullet in bullets:
        norm = _normalize_freetext(bullet)
        key = norm[:PREFIX_LEN]
        if key not in groups:
            groups[key] = []
        groups[key].append((norm, bullet))

    # From each prefix group, keep only the best (longest normalized text)
    after_pass1: list[str] = []
    seen_prefixes: set[str] = set()
    for bullet in bullets:
        norm = _normalize_freetext(bullet)
        key = norm[:PREFIX_LEN]
        if key in seen_prefixes:
            continue
        seen_prefixes.add(key)
        group = groups[key]
        best = max(group, key=lambda x: len(x[0]))
        after_pass1.append(best[1])

    # Pass 2: word-overlap merging for remaining bullets
    # This catches paraphrased dupes that differ in the first 50 chars.
    # Uses two metrics:
    # - Jaccard similarity (intersection/union) >= 0.55
    # - Containment: fraction of shorter bullet's words in longer >= 0.80
    # Either metric being met indicates a near-duplicate.
    JACCARD_THRESHOLD = 0.55
    CONTAINMENT_THRESHOLD = 0.75
    norms = [_normalize_freetext(b) for b in after_pass1]
    word_sets = [set(n.split()) for n in norms]
    absorbed: set[int] = set()  # indices absorbed into another bullet

    for i in range(len(after_pass1)):
        if i in absorbed:
            continue
        for j in range(i + 1, len(after_pass1)):
            if j in absorbed:
                continue
            ws_i, ws_j = word_sets[i], word_sets[j]
            union = ws_i | ws_j
            if not union:
                continue
            intersection = ws_i & ws_j
            jaccard = len(intersection) / len(union)
            # Containment: how much of the shorter set is in the longer set
            smaller = min(len(ws_i), len(ws_j))
            containment = len(intersection) / smaller if smaller > 0 else 0

            if jaccard >= JACCARD_THRESHOLD or containment >= CONTAINMENT_THRESHOLD:
                # Keep whichever is longer (more detailed); absorb the other
                if len(norms[j]) > len(norms[i]):
                    absorbed.add(i)
                    break  # i is absorbed; stop comparing i vs others
                else:
                    absorbed.add(j)

    return [b for idx, b in enumerate(after_pass1) if idx not in absorbed]


def _normalize_freetext(bullet: str) -> str:
    """Normalize a free-text bullet for near-duplicate detection.

    Strips: bullet markers, room ID annotations like (R1)/(R38)/(R215),
    trailing periods, bold markers, em-dash/hyphen normalization,
    extra whitespace, articles/determiners, and lowercases everything.
    """
    text = re.sub(r'^[\*\-\+]\s+', '', bullet.strip())
    # Remove bold markers
    text = text.replace('**', '')
    # Remove room ID annotations like (R1), (R38), (R215)
    text = re.sub(r'\s*\(R\d+\)', '', text)
    # Remove range annotations like (R18-R32)
    text = re.sub(r'\s*\(R\d+-R\d+\)', '', text)
    # Normalize em-dashes and en-dashes to hyphens
    text = text.replace('—', '-').replace('–', '-')
    # Normalize backtick-quoted commands (remove backticks for comparison)
    text = text.replace('`', '')
    # Strip trailing period(s) and whitespace
    text = text.rstrip('. ').strip()
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = text.lower()
    # Remove common articles/determiners for tighter prefix matching
    text = re.sub(r'\b(the|a|an)\b', '', text)
    # Re-collapse spaces after article removal
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
        raw_client, model = client.raw_client_for(config.knowledge_model)
        response = raw_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": _get_knowledge_prompt()}, {"role": "user", "content": user_msg}],
            temperature=0.2, max_tokens=2048,
            timeout=config.llm_request_timeout,
            **thinking_kwargs(config, config.knowledge_model, False),
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

        # Structural guardrail: deduplicate Items Found section
        content = _dedup_items_found(content)

        # Structural guardrail: deduplicate free-text sections (Puzzle Mechanics, Dangerous Areas, etc.)
        content = _dedup_freetext_sections(content)

        persist_knowledge(content, config)
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
