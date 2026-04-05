"""Dry-run consolidation with updated prompts against current memory data.

Sends each location's memories through the consolidation LLM via OpenRouter
and reports what would be kept/dropped/merged/superseded — without modifying data.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import instructor
from openai import AsyncOpenAI, OpenAI

from zorkburr.llm.models import ConsolidationResponse
from zorkburr.llm.prompts import load_prompt

load_dotenv()

MODEL = "mistralai/ministral-14b-2512"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"


def load_memories() -> dict:
    with open(Path(__file__).parent.parent / "data" / "memories.json") as f:
        return json.load(f)


def load_knowledge() -> str:
    p = Path(__file__).parent.parent / "data" / "knowledge.md"
    return p.read_text() if p.exists() else ""


def load_map_rooms() -> dict[str, str]:
    with open(Path(__file__).parent.parent / "data" / "map.json") as f:
        return json.load(f).get("rooms", {})


def build_context(location_id: str, memories: list[dict], kb: str) -> str:
    mem_lines = []
    for m in memories:
        status_tag = " [SUPERSEDED]" if m.get("status") == "SUPERSEDED" else ""
        mem_lines.append(f"- [{m.get('title', '?')}]{status_tag}: {m.get('text', '')}")
    return (
        f"Location ID: {location_id}\n\n"
        f"Memories:\n" + "\n".join(mem_lines) + "\n\n"
        f"Current Knowledge Base:\n{kb or '(empty)'}"
    )


async def consolidate_one(
    client: instructor.Instructor,
    location_id: str,
    room_name: str,
    memories: list[dict],
    kb: str,
    prompt: str,
) -> dict:
    active = [m for m in memories if m.get("status") != "SUPERSEDED"]
    if not active:
        return {"location_id": location_id, "room": room_name, "skipped": True, "reason": "no active memories"}

    context = build_context(location_id, memories, kb)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_model=ConsolidationResponse,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
            max_tokens=2048,
        )

        actions_summary = []
        for act in response.actions:
            entry = {"action": act.action, "title": act.memory_title, "reason": act.reason}
            if act.action == "merge":
                entry["merge_with"] = act.merge_with
                entry["new_title"] = act.new_title
            elif act.action == "supersede":
                entry["correct"] = act.merge_with
            actions_summary.append(entry)

        return {
            "location_id": location_id,
            "room": room_name,
            "active_count": len(active),
            "total_count": len(memories),
            "actions": actions_summary,
            "keeps": sum(1 for a in actions_summary if a["action"] == "keep"),
            "drops": sum(1 for a in actions_summary if a["action"] == "drop"),
            "merges": sum(1 for a in actions_summary if a["action"] == "merge"),
            "supersedes": sum(1 for a in actions_summary if a["action"] == "supersede"),
        }
    except Exception as e:
        return {"location_id": location_id, "room": room_name, "error": str(e)[:200]}


def main():
    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    # Use sync client with instructor (simpler for sequential calls)
    raw_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    client = instructor.from_openai(raw_client)

    memories = load_memories()
    kb = load_knowledge()
    rooms = load_map_rooms()
    prompt = load_prompt("memory_consolidation")

    print(f"Model: {MODEL}")
    print(f"Locations with memories: {len(memories)}")
    print(f"Consolidation prompt: {len(prompt)} chars\n")

    # Process all locations (sequentially to avoid rate limits)
    results = []
    for loc_id, loc_mems in sorted(memories.items(), key=lambda x: -len(x[1])):
        active_count = sum(1 for m in loc_mems if m.get("status") != "SUPERSEDED")
        room_name = rooms.get(loc_id, f"Room {loc_id}")
        print(f"  Processing {room_name} (R{loc_id}): {active_count} active / {len(loc_mems)} total...", end=" ", flush=True)

        result = asyncio.run(consolidate_one(client, loc_id, room_name, loc_mems, kb, prompt))
        results.append(result)

        if "error" in result:
            print(f"ERROR: {result['error'][:60]}")
        elif result.get("skipped"):
            print("skipped")
        else:
            print(f"keep={result['keeps']} drop={result['drops']} merge={result['merges']} supersede={result['supersedes']}")

    # Summary
    print(f"\n{'=' * 70}")
    print("DETAILED ACTIONS")
    print(f"{'=' * 70}\n")

    total_keeps = total_drops = total_merges = total_supersedes = 0

    for r in results:
        if r.get("skipped") or "error" in r:
            continue

        has_changes = r["drops"] > 0 or r["merges"] > 0 or r["supersedes"] > 0
        if not has_changes:
            continue

        print(f"--- {r['room']} (R{r['location_id']}) ---")
        for act in r["actions"]:
            if act["action"] == "keep":
                continue  # Only show changes
            icon = {"drop": "DROP", "merge": "MERGE", "supersede": "SUPERSEDE"}[act["action"]]
            print(f"  [{icon:>10}] {act['title']}")
            print(f"             Reason: {act['reason']}")
            if act["action"] == "merge":
                print(f"             + {act['merge_with']} → {act['new_title']}")
            elif act["action"] == "supersede":
                print(f"             Correct version: {act['correct']}")
        print()

        total_keeps += r["keeps"]
        total_drops += r["drops"]
        total_merges += r["merges"]
        total_supersedes += r["supersedes"]

    print(f"{'=' * 70}")
    print(f"TOTALS: keep={total_keeps} drop={total_drops} merge={total_merges} supersede={total_supersedes}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
