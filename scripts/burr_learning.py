"""Show learning subsystem activity: memory synthesis, KB updates, objective changes."""
import sys

from _args import parse_args, fetch_steps, get_state, get_action, in_turn_range


LEARNING_ACTIONS = {
    "record_memory",
    "update_knowledge",
    "update_objectives",
    "check_objective_completion",
}


def diff_memories(old_mems, new_mems):
    """Compare memories_by_location dicts. Return list of (loc_id, new_entries)."""
    changes = []
    for loc_id, new_list in new_mems.items():
        if not isinstance(new_list, list):
            continue
        old_list = old_mems.get(loc_id, [])
        if not isinstance(old_list, list):
            old_list = []
        if len(new_list) > len(old_list):
            new_entries = new_list[len(old_list):]
            changes.append((loc_id, new_entries))
    return changes


def _obj_key(obj):
    """Extract a comparable key from an objective (dict or string)."""
    if isinstance(obj, dict):
        return obj.get("text") or obj.get("objective") or str(obj)
    return str(obj)


def _obj_display(obj):
    """Format an objective for display."""
    if isinstance(obj, dict):
        text = obj.get("text") or obj.get("objective") or str(obj)
        loc = obj.get("location_name", "")
        turn = obj.get("completed_turn", "")
        extra = ""
        if loc:
            extra += f" [{loc}]"
        if turn:
            extra += f" (turn {turn})"
        return text + extra
    return str(obj)


def diff_objectives(old_list, new_list):
    """Return (added, removed) as display strings."""
    old_keys = {_obj_key(o) for o in (old_list or [])}
    new_keys = {_obj_key(o) for o in (new_list or [])}

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys

    # Map back to display strings
    added = [_obj_display(o) for o in (new_list or []) if _obj_key(o) in added_keys]
    removed = [_obj_display(o) for o in (old_list or []) if _obj_key(o) in removed_keys]
    return sorted(added), sorted(removed)


def main():
    args = parse_args()
    app_id = args["app_id"]
    if not app_id:
        print(
            "Usage: python3 scripts/burr_learning.py <app_id> [--turns START-END]",
            file=sys.stderr,
        )
        sys.exit(1)

    turns_filter = args["turns"]
    steps = fetch_steps(app_id)
    if not steps:
        print("No steps found.", file=sys.stderr)
        sys.exit(1)

    print("=== Learning System Activity ===")
    print()

    # Tracking for summary
    total_new_memories = 0
    mem_categories = {}
    total_dedup = 0
    total_superseded = 0
    kb_updates = 0
    kb_net_delta = 0
    objectives_discovered_total = 0
    objectives_completed_total = 0

    prev_state = {}
    shown_any = False

    for step in steps:
        action = get_action(step)
        if action not in LEARNING_ACTIONS:
            # Still track state for diffing
            st = get_state(step)
            if st:
                prev_state = st
            continue

        state = get_state(step)
        if not state:
            continue

        turn = state.get("turn_count")
        if turn is None:
            continue
        if not in_turn_range(turn, turns_filter):
            prev_state = state
            continue

        location = state.get("location_name", "?")
        score = state.get("score", 0)
        pre_score = prev_state.get("score", 0) if prev_state else 0
        score_delta = score - pre_score if isinstance(score, (int, float)) and isinstance(pre_score, (int, float)) else 0

        if action == "record_memory":
            old_mems = prev_state.get("memories_by_location", {}) if prev_state else {}
            new_mems = state.get("memories_by_location", {})
            changes = diff_memories(old_mems, new_mems)
            mem_stats = state.get("memory_stats", {})

            if changes:
                score_str = f" (score +{score_delta})" if score_delta > 0 else ""
                print(f"--- Turn {turn} [{location}]{score_str} ---")
                print(f"  [record_memory]")
                for loc_id, new_entries in changes:
                    print(f"    NEW at loc {loc_id}:")
                    for m in new_entries:
                        cat = m.get("category", "?")
                        title = m.get("title", "untitled")
                        text = m.get("text", "")
                        status = m.get("status", "?")
                        print(f'      [{cat}] "{title}"')
                        if text:
                            display = text[:200] + "..." if len(text) > 200 else text
                            print(f"      Text: {display}")
                        total_new_memories += 1
                        mem_categories[cat] = mem_categories.get(cat, 0) + 1
                if mem_stats:
                    parts = []
                    for k in ("new", "dedup_rejected", "superseded", "ephemeral_pruned"):
                        if k in mem_stats:
                            parts.append(f"{k}={mem_stats[k]}")
                    if parts:
                        print(f"    Stats: {' '.join(parts)}")
                    total_dedup += mem_stats.get("dedup_rejected", 0)
                    total_superseded += mem_stats.get("superseded", 0)
                print()
                shown_any = True
            # Skip no-change record_memory to reduce noise

        elif action == "update_knowledge":
            old_kb = prev_state.get("knowledge_base", "") if prev_state else ""
            new_kb = state.get("knowledge_base", "")
            old_len = len(old_kb) if old_kb else 0
            new_len = len(new_kb) if new_kb else 0
            delta = new_len - old_len

            print(f"--- Turn {turn} (knowledge update) ---")
            print(f"  [update_knowledge]")
            if old_kb != new_kb:
                sign = "+" if delta >= 0 else ""
                print(f"    KB: {old_len} -> {new_len} chars ({sign}{delta})")
                kb_updates += 1
                kb_net_delta += delta
                # Show a snippet of what's new if KB grew
                if new_len > old_len and new_kb:
                    # Simple heuristic: show last N chars of the new KB
                    tail = new_kb[-(min(abs(delta) + 50, 300)):]
                    lines = tail.strip().split("\n")
                    preview_lines = lines[-5:] if len(lines) > 5 else lines
                    print("    New content (tail):")
                    for line in preview_lines:
                        print(f"      {line}")
            else:
                print("    KB unchanged")
            print()
            shown_any = True

        elif action in ("update_objectives", "check_objective_completion"):
            old_disc = prev_state.get("discovered_objectives", []) if prev_state else []
            new_disc = state.get("discovered_objectives", [])
            old_comp = prev_state.get("completed_objectives", []) if prev_state else []
            new_comp = state.get("completed_objectives", [])

            added_disc, removed_disc = diff_objectives(old_disc, new_disc)
            added_comp, removed_comp = diff_objectives(old_comp, new_comp)

            has_changes = added_disc or removed_disc or added_comp or removed_comp

            # update_objectives is infrequent — always show
            # check_objective_completion runs every turn — only show when changed
            if action == "check_objective_completion" and not has_changes:
                prev_state = state
                continue

            label = "objective update" if action == "update_objectives" else "objective check"
            print(f"--- Turn {turn} ({label}) [{location}] ---")
            print(f"  [{action}]")
            if added_disc:
                for o in added_disc:
                    print(f'    ADDED: "{o}"')
                objectives_discovered_total += len(added_disc)
            if removed_disc:
                for o in removed_disc:
                    print(f'    REMOVED: "{o}"')
            if added_comp:
                for o in added_comp:
                    print(f'    COMPLETED: "{o}"')
                objectives_completed_total += len(added_comp)
            if not has_changes:
                print("    No changes")
            print(f"    Total: {len(new_disc)} discovered, {len(new_comp)} completed")
            print()
            shown_any = True

        prev_state = state

    if not shown_any:
        print("  (no learning activity found in the given range)")
        print()

    # Summary
    print("=== Summary ===")
    cat_str = ", ".join(f"{k}={v}" for k, v in sorted(mem_categories.items(), key=lambda x: -x[1]))
    print(f"  Memories created: {total_new_memories}" + (f" (by category: {cat_str})" if cat_str else ""))
    if total_dedup or total_superseded:
        print(f"  Memories dedup rejected: {total_dedup} | Superseded: {total_superseded}")
    sign = "+" if kb_net_delta >= 0 else ""
    print(f"  KB updates: {kb_updates}" + (f" (net {sign}{kb_net_delta} chars)" if kb_updates else ""))
    print(f"  Objectives discovered: {objectives_discovered_total} | Completed: {objectives_completed_total}")
    print()


if __name__ == "__main__":
    main()
