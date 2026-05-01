"""Context assembly: build formatted prompt context for agent/critic."""
from __future__ import annotations
from burr.core import action, State
from zorkburr.state import S

@action(
    reads=[S.GAME_RESPONSE, S.LOCATION_NAME, S.LOCATION_ID, S.INVENTORY, S.SCORE,
           S.ACTION_HISTORY, S.EXITS, S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES,
           S.KNOWLEDGE_BASE, S.MEMORIES_BY_LOCATION, S.MAP_DATA, S.TURN_COUNT,
           S.TURNS_SINCE_PROGRESS, S.NEXT_STEPS, S.LOCATION_SUMMARIES, S.NAV_TARGET],
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
        mermaid = mg.to_mermaid_local(loc_id)
        if mermaid:
            sections.append(f"## CURRENT WORLD MAP\n```mermaid\n{mermaid}\n```")

    # Strategic Knowledge (KB) — high priority, before plan/reasoning
    knowledge = state[S.KNOWLEDGE_BASE]
    if knowledge:
        sections.append(f"**Strategic Knowledge:**\n{knowledge}")

    # Current plan (forward-looking multi-turn intent)
    next_steps = state[S.NEXT_STEPS]
    if next_steps:
        sections.append(f"**Current Plan:** {next_steps}")

    # Recent actions with reasoning (backward-looking continuity)
    history = state[S.ACTION_HISTORY]
    if history:
        recent = history[-5:]
        history_lines = []
        for entry in recent:
            line = f"  Turn {entry['turn']}: {entry['action']} -> {entry.get('response', '')[:200]}"
            reasoning = entry.get("reasoning", "")
            if reasoning:
                line += f"\n    Thinking: {reasoning}"
            history_lines.append(line)
        sections.append("## Previous Reasoning and Actions\n" + "\n".join(history_lines))

    loc_key = str(loc_id)
    has_any_memories = loc_key in memories and memories[loc_key]
    if has_any_memories:
        loc_mems = [m for m in memories[loc_key] if m.get("status") != "SUPERSEDED"]
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
                neighbor_mems = [m for m in memories[neighbor_key] if m.get("status") != "SUPERSEDED"]
                for m in neighbor_mems[:5]:  # max 5 per neighbor
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

    # Global location summaries: one-line summaries for all explored locations
    # beyond 1-hop (current room and neighbors already shown in full above)
    summaries = state[S.LOCATION_SUMMARIES]
    if summaries and mg:
        neighbor_ids = {str(rid) for rid in mg.get_exits(loc_id).values()}
        neighbor_ids.add(loc_key)
        global_lines = []
        for rid_str in sorted(summaries.keys()):
            if rid_str in neighbor_ids or not summaries[rid_str]:
                continue
            room_name = mg.get_room_name(int(rid_str)) if int(rid_str) in mg.rooms else f"R{rid_str}"
            global_lines.append(f"  - {room_name} (R{rid_str}): {summaries[rid_str]}")
        if global_lines:
            sections.append(
                "**Explored locations (from PREVIOUS episodes, state has reset):**\n"
                + "\n".join(global_lines)
            )

    # Score event timeline for the current episode (derived from ACTION_HISTORY)
    score_event_history = state[S.ACTION_HISTORY]
    if score_event_history:
        score_events = []
        for entry in score_event_history:
            sb = entry.get("score_before")
            sa = entry.get("score_after")
            if sb is None or sa is None:
                continue
            delta = sa - sb
            if delta == 0:
                continue
            loc = entry.get("location_name", "")
            act = entry.get("action", "")
            score_events.append(
                f"t{entry.get('turn', '?')} {delta:+d} ({act} at {loc})"
            )
        if score_events:
            sections.append(
                "**Score events this episode:**\n  " + " · ".join(score_events)
            )

    # Ad-hoc navigation target set by the agent on a prior turn
    nav_target = state[S.NAV_TARGET]
    if nav_target and mg:
        target_id = 0
        try:
            target_id = int(nav_target)
            if target_id not in mg.rooms:
                target_id = 0
        except (ValueError, TypeError):
            norm = nav_target.strip().lower()
            # Exact match first, then substring
            for rid, rname in mg.rooms.items():
                if rname.strip().lower() == norm:
                    target_id = rid
                    break
            if target_id == 0:
                for rid, rname in mg.rooms.items():
                    rn = rname.strip().lower()
                    if norm in rn or rn in norm:
                        target_id = rid
                        break
        if target_id:
            target_name = mg.get_room_name(target_id)
            if target_id == loc_id:
                sections.append(
                    f"**Planned route to {target_name}:** (you are here)"
                )
            else:
                path = mg.shortest_path(loc_id, target_id)
                if path is not None:
                    steps = " → ".join(
                        f"{d} → {mg.get_room_name(rid)}" for d, rid in path
                    )
                    sections.append(
                        f"**Planned route to {target_name}:** {steps} ({len(path)} moves)"
                    )
                else:
                    sections.append(
                        f"**Planned route to {target_name}:** (no known route)"
                    )
        else:
            sections.append(
                f"**Nav target:** '{nav_target}' — could not resolve to a known location."
            )

    objectives = state[S.DISCOVERED_OBJECTIVES]
    if objectives:
        obj_lines = []
        for o in objectives:
            if isinstance(o, dict):
                loc_tag = f" [R{o['location_id']} — {o['location_name']}]" if o.get("location_id") else ""
                line = f"  -{loc_tag} {o['text']}"
                # Add pathfinding route for location-specific objectives
                target_id = o.get("location_id", 0)
                if target_id and mg:
                    if target_id == loc_id:
                        line += "\n    (you are here)"
                    else:
                        path = mg.shortest_path(loc_id, target_id)
                        if path is not None:
                            steps = " → ".join(
                                f"{d} → {mg.get_room_name(rid)}" for d, rid in path
                            )
                            line += f"\n    Route ({len(path)} moves): {steps}"
                        else:
                            line += "\n    (no known route)"
                obj_lines.append(line)
            else:
                obj_lines.append(f"  - {o}")
        sections.append("**Active Objectives:**\n" + "\n".join(obj_lines))

    # Objectives completed in the current episode (resets each episode via create_initial_state)
    completed = state[S.COMPLETED_OBJECTIVES]
    if completed:
        done_lines = []
        for rec in completed:
            if isinstance(rec, dict):
                text = rec.get("objective", str(rec))
                turn = rec.get("completed_turn", "?")
                done_lines.append(f"  - [t{turn}] {text}")
            else:
                done_lines.append(f"  - {rec}")
        sections.append("**Completed this episode:**\n" + "\n".join(done_lines))

    turns_stuck = state[S.TURNS_SINCE_PROGRESS]
    if turns_stuck >= 35:
        sections.append(
            f"**STAGNATION ALERT: Score has not changed in {turns_stuck} turns. "
            f"Current strategy is exhausted — try a fundamentally different "
            f"approach (new region, different scoring chain).**"
        )
    elif turns_stuck >= 30:
        sections.append(
            f"**No score progress for {turns_stuck} turns. Change strategy — "
            f"explore new areas, try unexamined items, or pursue a different "
            f"treasure.**"
        )

    formatted = "\n\n".join(sections)
    return {"context_length": len(formatted)}, state.update(**{S.FORMATTED_CONTEXT: formatted})


# Expose .run for test compatibility (delegates to run_and_update on the FunctionBasedAction)
assemble_context.run = assemble_context.action_function.run_and_update
