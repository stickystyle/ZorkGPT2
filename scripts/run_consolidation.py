"""Run memory consolidation on all locations with the current prompts.

Creates a backup before modifying, then applies consolidation to every
location (not just 5+ active like finalize_episode does).
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import instructor
from openai import OpenAI

from zorkburr.config import GameConfig
from zorkburr.actions.episode import consolidate_location
from zorkburr.llm.prompts import load_prompt  # noqa: force prompt cache clear

load_dotenv()


def main():
    config = GameConfig()
    mem_path = Path(config.memory_file)

    if not mem_path.exists():
        print("No memories file found")
        sys.exit(1)

    all_mems = json.loads(mem_path.read_text())

    # Load map for room names
    map_path = Path("data/map.json")
    rooms = json.loads(map_path.read_text()).get("rooms", {}) if map_path.exists() else {}

    kb_path = Path(config.knowledge_file)
    kb = kb_path.read_text() if kb_path.exists() else ""

    # Backup
    backup = str(mem_path) + ".pre_consolidation_bak"
    shutil.copy2(mem_path, backup)
    print(f"Backup: {backup}")

    # Build client via OpenRouter
    import os
    raw_client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    client = instructor.from_openai(raw_client)

    # Override config to use OpenRouter model
    config.agent_model = "mistralai/ministral-14b-2512"
    config.analysis_model = "mistralai/ministral-14b-2512"
    config.use_local_models = False

    total_stats = {"kept": 0, "dropped": 0, "merged": 0, "superseded": 0, "rejected": 0}

    for loc_id in sorted(all_mems.keys(), key=lambda k: -len(all_mems[k])):
        loc_mems = all_mems[loc_id]
        active = sum(1 for m in loc_mems if m.get("status") != "SUPERSEDED")
        room_name = rooms.get(loc_id, f"Room {loc_id}")

        if active == 0:
            continue

        print(f"  {room_name} (R{loc_id}): {active} active / {len(loc_mems)} total ... ", end="", flush=True)

        try:
            updated, stats = consolidate_location(
                location_id=loc_id,
                memories=loc_mems,
                knowledge_base=kb,
                client=client,
                config=config,
            )
            all_mems[loc_id] = updated
            new_active = sum(1 for m in updated if m.get("status") != "SUPERSEDED")
            print(f"→ {new_active} active (kept={stats['kept']} drop={stats['dropped']} merge={stats['merged']} sup={stats['superseded']} rej={stats['rejected']})")
            for k in total_stats:
                total_stats[k] += stats.get(k, 0)
        except Exception as e:
            print(f"ERROR: {e}")

    # Save
    mem_path.write_text(json.dumps(all_mems, indent=2))
    print(f"\nSaved to {mem_path}")
    print(f"Totals: {total_stats}")

    # Count final state
    final_active = sum(
        1 for loc_mems in all_mems.values()
        for m in loc_mems if m.get("status") != "SUPERSEDED"
    )
    final_total = sum(len(loc_mems) for loc_mems in all_mems.values())
    print(f"Final: {final_active} active / {final_total} total memories across {len(all_mems)} locations")


if __name__ == "__main__":
    main()
