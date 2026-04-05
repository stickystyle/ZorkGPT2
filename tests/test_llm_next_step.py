"""Test LLM next-step navigation: given a map and destination, pick the correct direction.

This matches the actual game loop — the agent picks ONE direction per turn, then gets
feedback. We test whether the model can pick the BFS-optimal next step from various
positions on the map, using both 2-hop local and full map views.
"""
import asyncio
import json
import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncOpenAI
from zorkburr.game.map_graph import MapGraph, normalize_direction

load_dotenv()

MODEL = "mistralai/ministral-14b-2512"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"


def load_map() -> MapGraph:
    with open(Path(__file__).parent.parent / "data" / "map.json") as f:
        return MapGraph.from_dict(json.load(f))


def bfs_next_step(mg: MapGraph, start: int, end: int) -> tuple[str | None, int]:
    """Return (optimal_direction, total_hops) for the first step of BFS shortest path."""
    if start == end:
        return None, 0
    queue: deque[tuple[int, str, int]] = deque()  # (current, first_dir, hops)
    visited = {start}
    for direction, dest in mg.connections.get(start, {}).items():
        if dest == end:
            return direction, 1
        if dest in mg.rooms:
            visited.add(dest)
            queue.append((dest, direction, 1))
    while queue:
        current, first_dir, hops = queue.popleft()
        for direction, dest in mg.connections.get(current, {}).items():
            if dest == end:
                return first_dir, hops + 1
            if dest not in visited and dest in mg.rooms:
                visited.add(dest)
                queue.append((dest, first_dir, hops + 1))
    return None, -1


def map_to_text_adjacency(mg: MapGraph) -> str:
    lines = []
    for room_id in sorted(mg.rooms.keys()):
        name = mg.rooms[room_id]
        exits = mg.connections.get(room_id, {})
        if exits:
            exit_strs = [f"{d} → {mg.get_room_name(dest)}" for d, dest in sorted(exits.items())]
            lines.append(f"{name}: {', '.join(exit_strs)}")
        else:
            lines.append(f"{name}: (no known exits)")
    return "\n".join(lines)


# Test cases: (start_id, dest_id, description)
# Mix of short and long distances — but we only ask for the NEXT step
TEST_CASES = [
    # 1-hop (trivial — direction is directly visible)
    (203, 79, "Kitchen → Behind House", 1),
    (193, 72, "Living Room → Cellar", 1),
    # 2-hop (need to look one room ahead)
    (193, 102, "Living Room → Troll Room", 2),
    (215, 199, "Dam → Maintenance Room", 2),
    (72, 148, "Cellar → Gallery", 2),
    # 3-hop
    (203, 41, "Kitchen → East-West Passage", 3),
    (201, 102, "Attic → Troll Room", 3),
    # 5-7 hop (agent needs global map awareness to pick the right first step)
    (193, 215, "Living Room → Dam", 5),
    (88, 94, "Up a Tree → Studio", 7),
    (201, 140, "Attic → Dam Base", 7),
    (193, 65, "Living Room → Dead End (maze)", 7),
    (88, 136, "Up a Tree → End of Rainbow", 7),
    # Tricky: multiple paths, one is shorter
    (79, 193, "Behind House → Living Room", 2),  # west→west vs north→south→...
    (50, 138, "Reservoir South → Loud Room", 3),  # southeast→down vs east→...
]


async def test_next_step(
    client: AsyncOpenAI,
    mg: MapGraph,
    map_repr: str,
    map_format: str,
    start_id: int,
    dest_id: int,
    description: str,
    expected_hops: int,
) -> dict:
    """Ask the LLM: you are at X, you want to reach Y — which direction do you move?"""
    start_name = mg.get_room_name(start_id)
    dest_name = mg.get_room_name(dest_id)

    optimal_dir, total_hops = bfs_next_step(mg, start_id, dest_id)
    if optimal_dir is None:
        return {"description": description, "format": map_format, "error": "no BFS path"}

    # Get all valid first steps that lead to shortest paths (there may be ties)
    optimal_dirs = set()
    shortest = total_hops
    for direction, next_room in mg.connections.get(start_id, {}).items():
        _, hops_from_next = bfs_next_step(mg, next_room, dest_id)
        if hops_from_next >= 0 and hops_from_next + 1 == shortest:
            optimal_dirs.add(direction)

    exits = mg.connections.get(start_id, {})
    exit_list = ", ".join(f"{d} → {mg.get_room_name(dest)}" for d, dest in sorted(exits.items()))

    if map_format == "mermaid":
        map_section = f"## WORLD MAP\n```mermaid\n{map_repr}\n```"
    else:
        map_section = f"## WORLD MAP\n{map_repr}"

    prompt = f"""You are playing a text adventure game. You need to navigate from your current location to a destination.

{map_section}

## CURRENT LOCATION
**{start_name}**
Available exits: {exit_list}

## DESTINATION
**{dest_name}** ({total_hops} moves away)

Which single direction should you move NEXT to get closer to {dest_name}?
Reply with just the direction (e.g., "north"). One word only."""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
        )
        answer = (response.choices[0].message.content or "").strip().lower()
    except Exception as e:
        return {"description": description, "format": map_format, "error": str(e)}

    # Parse the answer — take first direction word found
    chosen = None
    for token in answer.replace(",", " ").replace(".", " ").split():
        nd = normalize_direction(token.strip("*\"'`"))
        if nd:
            chosen = nd
            break

    is_valid = chosen in exits
    is_optimal = chosen in optimal_dirs

    return {
        "description": description,
        "format": map_format,
        "hops": total_hops,
        "optimal_dirs": sorted(optimal_dirs),
        "chosen": chosen,
        "raw_answer": answer[:60],
        "is_valid": is_valid,
        "is_optimal": is_optimal,
    }


async def run_suite(client, mg, map_repr, fmt):
    tasks = [
        test_next_step(client, mg, map_repr, fmt, s, d, desc, h)
        for s, d, desc, h in TEST_CASES
    ]
    return await asyncio.gather(*tasks)


def print_results(results, fmt):
    valid = 0
    optimal = 0
    total = len(results)

    # Group by hop distance
    by_hops = {}
    for r in results:
        h = r.get("hops", "?")
        by_hops.setdefault(h, []).append(r)

    for hops in sorted(by_hops.keys()):
        print(f"\n  --- {hops}-hop destinations ---")
        for r in by_hops[hops]:
            if "error" in r:
                status = "ERROR"
                detail = r["error"][:60]
            elif r["is_optimal"]:
                status = "OPTIMAL"
                optimal += 1
                valid += 1
                detail = f"chose={r['chosen']} optimal={r['optimal_dirs']}"
            elif r["is_valid"]:
                status = "VALID"
                valid += 1
                detail = f"chose={r['chosen']} optimal={r['optimal_dirs']}"
            else:
                status = "WRONG"
                detail = f"chose={r['chosen']} optimal={r['optimal_dirs']} raw='{r['raw_answer']}'"
            print(f"    [{status:>7}] {r['description']:45s} {detail}")

    print(f"\n  => {fmt.upper()}: {valid}/{total} valid, {optimal}/{total} optimal\n")
    return valid, optimal


async def main():
    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    mg = load_map()

    # Generate map representations
    full_mermaid = mg.to_mermaid()
    text_full = map_to_text_adjacency(mg)

    print(f"Map: {len(mg.rooms)} rooms")
    print(f"Model: {MODEL}")
    print(f"Test: {len(TEST_CASES)} next-step navigation decisions")
    print(f"Formats: full mermaid ({len(full_mermaid)} chars), full text ({len(text_full)} chars)\n")

    # Run both formats in parallel
    mermaid_results, text_results = await asyncio.gather(
        run_suite(client, mg, full_mermaid, "mermaid"),
        run_suite(client, mg, text_full, "text"),
    )

    # Also test local mermaid (2-hop) — the current system
    local_tasks = []
    for s, d, desc, h in TEST_CASES:
        local_mermaid = mg.to_mermaid_local(s, depth=2)
        local_tasks.append(
            test_next_step(client, mg, local_mermaid, "local-2hop", s, d, desc, h)
        )
    local_results = await asyncio.gather(*local_tasks)

    for fmt, results in [("mermaid (full)", mermaid_results),
                          ("text (full)", text_results),
                          ("mermaid (2-hop local)", local_results)]:
        print(f"{'=' * 65}")
        print(f"  FORMAT: {fmt}")
        print(f"{'=' * 65}")
        print_results(results, fmt)


if __name__ == "__main__":
    asyncio.run(main())
