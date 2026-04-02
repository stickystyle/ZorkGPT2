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

    loc_id = state[S.LOCATION_ID]
    memories = state[S.MEMORIES_BY_LOCATION]

    # Build MapGraph once for map diagram + adjacent memories
    map_data = state[S.MAP_DATA]
    mg = None
    if map_data:
        from zorkburr.game.map_graph import MapGraph
        mg = MapGraph.from_dict(map_data) if isinstance(map_data, dict) else map_data
        mermaid = mg.to_mermaid(loc_id)
        if mermaid:
            sections.append(f"## CURRENT WORLD MAP\n```mermaid\n{mermaid}\n```")

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

    loc_key = str(loc_id)
    has_any_memories = loc_key in memories and memories[loc_key]
    if has_any_memories:
        loc_mems = memories[loc_key]
        mem_lines = [f"  - {m.get('text', str(m))}" for m in loc_mems[:10]]
        sections.append(
            "**Memories for this location (from PREVIOUS episodes):**\n"
            "NOTE: The game resets completely each episode — doors close, items return "
            "to original positions, puzzles reset. Use these as guidance for WHAT TO DO, "
            "not as current state. If a memory says \"opened trap door\", you must open "
            "it again — it is NOT currently open.\n"
            + "\n".join(mem_lines)
        )

    # Adjacent room memories (1-hop neighbors from map)
    if mg:
        adjacent_mems = []
        exits_map = mg.get_exits(loc_id)
        for direction, neighbor_id in exits_map.items():
            neighbor_key = str(neighbor_id)
            if neighbor_key in memories and neighbor_key != loc_key:
                neighbor_name = mg.get_room_name(neighbor_id)
                for m in memories[neighbor_key][:5]:  # max 5 per neighbor
                    adjacent_mems.append((direction, neighbor_name, m))

        if adjacent_mems:
            # Budget: max 5 adjacent memories total, prioritize DANGER > SUCCESS > DISCOVERY > others
            category_priority = {"DANGER": 0, "SUCCESS": 1, "DISCOVERY": 2, "FAILURE": 3, "NOTE": 4}
            adjacent_mems.sort(key=lambda x: category_priority.get(x[2].get("category", "NOTE"), 4))
            adjacent_mems = adjacent_mems[:5]

            adj_lines = []
            for direction, neighbor_name, m in adjacent_mems:
                cat = m.get("category", "")
                text = m.get("text", m.get("title", str(m)))
                adj_lines.append(f"  - [{cat}] ({direction} — {neighbor_name}): {text}")
            sections.append("**Nearby memories (adjacent rooms, from PREVIOUS episodes — state has reset):**\n" + "\n".join(adj_lines))

    objectives = state[S.DISCOVERED_OBJECTIVES]
    if objectives:
        obj_lines = []
        for o in objectives:
            if isinstance(o, dict):
                loc_tag = f" [R{o['location_id']} — {o['location_name']}]" if o.get("location_id") else ""
                obj_lines.append(f"  -{loc_tag} {o['text']}")
            else:
                obj_lines.append(f"  - {o}")
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
