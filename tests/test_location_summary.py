"""Test location summary prompt against real memory data.

Runs the summary LLM on each location's memories and displays the output
so we can iterate on prompt quality before wiring it into the pipeline.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import OpenAI

from zorkburr.llm.prompts import load_prompt

load_dotenv()

MODEL = "mistralai/ministral-14b-2512"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"


def load_memories() -> dict:
    with open(Path(__file__).parent.parent / "data" / "memories.json") as f:
        return json.load(f)


def load_map_rooms() -> dict[str, str]:
    with open(Path(__file__).parent.parent / "data" / "map.json") as f:
        return json.load(f).get("rooms", {})


def main():
    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    memories = load_memories()
    rooms = load_map_rooms()
    prompt = load_prompt("location_summary")

    print(f"Model: {MODEL}")
    print(f"Prompt ({len(prompt)} chars):\n---\n{prompt}\n---\n")

    total_chars = 0
    results = []

    for loc_id in sorted(memories.keys(), key=lambda k: -len(memories[k])):
        loc_mems = memories[loc_id]
        active = [m for m in loc_mems if m.get("status") != "SUPERSEDED"]
        if not active:
            continue

        room_name = rooms.get(loc_id, f"Room {loc_id}")

        # Build the memory text to summarize
        mem_lines = []
        for m in active:
            if "--titles-only" in sys.argv:
                mem_lines.append(f"- [{m.get('category', 'NOTE')}] {m.get('title', '?')}")
            else:
                mem_lines.append(f"- [{m.get('category', 'NOTE')}] {m.get('title', '?')}: {m.get('text', '')}")
        user_content = f"Location: {room_name} (R{loc_id})\n\nMemories:\n" + "\n".join(mem_lines)

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=100,
            )
            summary = (response.choices[0].message.content or "").strip()
        except Exception as e:
            summary = f"ERROR: {e}"

        char_count = len(summary)
        total_chars += char_count
        results.append((loc_id, room_name, len(active), summary, char_count))
        print(f"  {room_name:25s} (R{loc_id:>3s}) [{len(active)} mems] → {summary}")

    print(f"\n{'=' * 70}")
    print(f"Locations: {len(results)}")
    print(f"Total summary chars: {total_chars}")
    print(f"Avg chars/location: {total_chars / len(results):.0f}")
    print(f"Estimated tokens: ~{total_chars // 4}")
    print(f"\nAs it would appear in context:")
    print(f"{'=' * 70}")
    for loc_id, room_name, _, summary, _ in results:
        print(f"  - {room_name} (R{loc_id}): {summary}")


if __name__ == "__main__":
    main()
