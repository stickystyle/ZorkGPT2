"""Context assembly: build formatted prompt context for agent/critic."""
from __future__ import annotations
from burr.core import action, State
from zorkburr.state import S

@action(
    reads=[S.GAME_RESPONSE, S.LOCATION_NAME, S.LOCATION_ID, S.INVENTORY, S.SCORE,
           S.ACTION_HISTORY, S.EXITS, S.DISCOVERED_OBJECTIVES, S.KNOWLEDGE_BASE,
           S.MEMORIES_BY_LOCATION, S.MAP_DATA, S.IN_COMBAT, S.TURN_COUNT,
           S.TURNS_SINCE_PROGRESS],
    writes=[S.FORMATTED_CONTEXT],
)
def assemble_context(state: State) -> tuple[dict, State]:
    """Build the formatted context string for the agent prompt."""
    sections = []
    sections.append(f"**Current Game State:**\n{state[S.GAME_RESPONSE]}")
    sections.append(
        f"**Location:** {state[S.LOCATION_NAME]} (ID: {state[S.LOCATION_ID]})\n"
        f"Score: {state[S.SCORE]}\n"
        f"**Turn:** {state[S.TURN_COUNT]}"
    )
    inv = state[S.INVENTORY]
    inv_str = ", ".join(inv) if inv else "(empty)"
    sections.append(f"**Inventory:** {inv_str}")

    exits = state[S.EXITS]
    if exits:
        sections.append(f"**Available Exits:** {', '.join(exits)}")

    if state[S.IN_COMBAT]:
        sections.append("**COMBAT ACTIVE — prioritize combat actions**")

    history = state[S.ACTION_HISTORY]
    if history:
        recent = history[-5:]
        history_lines = []
        for entry in recent:
            history_lines.append(
                f"  Turn {entry['turn']}: {entry['action']} -> {entry.get('response', '')[:200]}"
            )
        sections.append("**Recent Actions:**\n" + "\n".join(history_lines))

    loc_id = state[S.LOCATION_ID]
    memories = state[S.MEMORIES_BY_LOCATION]
    loc_key = str(loc_id)
    if loc_key in memories:
        loc_mems = memories[loc_key]
        if loc_mems:
            mem_lines = [f"  - {m.get('text', str(m))}" for m in loc_mems[:10]]
            sections.append("**Memories for this location:**\n" + "\n".join(mem_lines))

    objectives = state[S.DISCOVERED_OBJECTIVES]
    if objectives:
        obj_lines = [f"  - {o}" for o in objectives]
        sections.append("**Active Objectives:**\n" + "\n".join(obj_lines))

    knowledge = state[S.KNOWLEDGE_BASE]
    if knowledge:
        sections.append(f"**Strategic Knowledge:**\n{knowledge[:2000]}")

    turns_stuck = state[S.TURNS_SINCE_PROGRESS]
    if turns_stuck >= 20:
        remaining = 40 - turns_stuck  # max_turns_stuck default
        if remaining <= 5:
            sections.append(
                f"**CRITICAL: Episode ends in {remaining} turns if no progress! "
                f"Try something completely different.**"
            )
        elif remaining <= 10:
            sections.append(
                f"**WARNING: {remaining} turns until episode ends. "
                f"Change strategy — explore new areas or try new items.**"
            )

    formatted = "\n\n".join(sections)
    return {"context_length": len(formatted)}, state.update(**{S.FORMATTED_CONTEXT: formatted})


# Expose .run for test compatibility (delegates to run_and_update on the FunctionBasedAction)
assemble_context.run = assemble_context.action_function.run_and_update
