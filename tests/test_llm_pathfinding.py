"""Test LLM pathfinding on the full Zork map at various depths.

Sends parallel requests to OpenRouter using the same model we run locally.
Compares LLM-proposed paths against BFS ground truth.

Run with:  uv run python tests/test_llm_pathfinding.py [--format mermaid|text|both]
"""
import asyncio
import json
import os
import sys
from collections import deque
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncOpenAI
from zorkburr.game.map_graph import MapGraph

load_dotenv()

MODEL = "mistralai/ministral-14b-2512"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"


def load_map() -> MapGraph:
    with open(Path(__file__).parent.parent / "data" / "map.json") as f:
        return MapGraph.from_dict(json.load(f))


def map_to_text_adjacency(mg: MapGraph) -> str:
    """Human-readable adjacency list: each room lists its exits."""
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


def bfs_shortest_path(mg: MapGraph, start: int, end: int) -> list[tuple[int, str]] | None:
    """BFS shortest path. Returns list of (room_id, direction_taken) or None."""
    if start == end:
        return []
    queue: deque[tuple[int, list[tuple[int, str]]]] = deque([(start, [])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        for direction, dest in mg.connections.get(current, {}).items():
            if dest not in visited and dest in mg.rooms:
                new_path = path + [(current, direction)]
                if dest == end:
                    return new_path
                visited.add(dest)
                queue.append((dest, new_path))
    return None


def format_path(mg: MapGraph, path: list[tuple[int, str]], end: int) -> str:
    """Format a BFS path as human-readable steps."""
    if not path:
        return "Already there"
    steps = []
    for room_id, direction in path:
        steps.append(f"{mg.get_room_name(room_id)} -> {direction}")
    steps.append(f"-> {mg.get_room_name(end)}")
    return " | ".join(steps)


def validate_path(mg: MapGraph, start: int, end: int, path_text: str) -> dict:
    """Try to parse and validate the LLM's proposed path against the graph."""
    from zorkburr.game.map_graph import normalize_direction

    # Extract direction words from the response
    lines = path_text.strip().split("\n")
    directions_found = []
    for line in lines:
        line_lower = line.lower().strip()
        # Look for direction words
        for token in line_lower.replace(",", " ").replace("→", " ").replace("->", " ").replace("|", " ").split():
            token = token.strip(".*()[]123456789. ")
            nd = normalize_direction(token)
            if nd:
                directions_found.append(nd)

    # Walk the graph following extracted directions
    current = start
    walked = []
    for d in directions_found:
        exits = mg.connections.get(current, {})
        if d in exits:
            walked.append((current, d))
            current = exits[d]
            if current == end:
                return {"valid": True, "reached_dest": True, "steps": len(walked), "directions": directions_found[:len(walked)]}
        else:
            return {"valid": False, "reached_dest": False, "stuck_at": mg.get_room_name(current),
                    "bad_direction": d, "step": len(walked) + 1, "directions_parsed": directions_found}

    return {"valid": current == end, "reached_dest": current == end, "steps": len(walked),
            "ended_at": mg.get_room_name(current), "directions_parsed": directions_found}


# Test pairs: (start_id, end_id, description)
TEST_PAIRS = [
    # Short paths (2-3 hops)
    (203, 79, "Kitchen to Behind House"),
    (215, 199, "Dam to Maintenance Room"),
    # Medium paths (4-6 hops)
    (193, 102, "Living Room to Troll Room"),
    (203, 215, "Kitchen to Dam"),
    (72, 148, "Cellar to Gallery"),
    # Long paths (7-10+ hops)
    (193, 138, "Living Room to Loud Room"),
    (201, 140, "Attic to Dam Base"),
    (88, 94, "Up a Tree to Studio"),
    (193, 65, "Living Room to Dead End (deep maze)"),
    (88, 136, "Up a Tree to End of Rainbow"),
]


async def test_pathfinding(
    client: AsyncOpenAI,
    mg: MapGraph,
    map_representation: str,
    map_format: str,
    start_id: int,
    end_id: int,
    description: str,
) -> dict:
    """Ask the LLM to pathfind and validate the result."""
    start_name = mg.get_room_name(start_id)
    end_name = mg.get_room_name(end_id)

    # Get BFS ground truth
    bfs_path = bfs_shortest_path(mg, start_id, end_id)
    bfs_len = len(bfs_path) if bfs_path is not None else -1

    if map_format == "mermaid":
        map_section = f"## COMPLETE WORLD MAP\n```mermaid\n{map_representation}\n```"
    else:
        map_section = f"## COMPLETE WORLD MAP\nEach room lists its exits and where they lead:\n\n{map_representation}"

    prompt = f"""You are navigating a text adventure game. Below is the complete map of all known rooms and connections.

{map_section}

## TASK
Find the shortest path from **{start_name}** to **{end_name}**.

List each step as a direction to move (north, south, east, west, up, down, northeast, etc.).
Format: one direction per line, numbered. Example:
1. north
2. east
3. down

Only output the directions. No explanations."""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        answer = response.choices[0].message.content or ""
    except Exception as e:
        return {"description": description, "format": map_format, "error": str(e), "bfs_hops": bfs_len}

    validation = validate_path(mg, start_id, end_id, answer)

    return {
        "description": description,
        "format": map_format,
        "start": start_name,
        "end": end_name,
        "bfs_hops": bfs_len,
        "bfs_path": format_path(mg, bfs_path, end_id) if bfs_path else "NO PATH",
        "llm_answer": answer.strip(),
        "llm_steps": validation.get("steps", "?"),
        "reached_dest": validation.get("reached_dest", False),
        "valid_path": validation.get("valid", False),
        "validation": validation,
    }


async def run_suite(client: AsyncOpenAI, mg: MapGraph, map_repr: str, fmt: str):
    """Run all test pairs against one map format."""
    tasks = [
        test_pathfinding(client, mg, map_repr, fmt, start, end, desc)
        for start, end, desc in TEST_PAIRS
    ]
    return await asyncio.gather(*tasks)


def print_results(results: list[dict], fmt: str):
    passed = 0
    optimal = 0
    for r in results:
        if "error" in r:
            status = "ERROR"
            detail = r["error"][:80]
        elif r["reached_dest"]:
            if r["llm_steps"] == r["bfs_hops"]:
                status = "OPTIMAL"
                optimal += 1
                passed += 1
            else:
                status = f"OK (+{r['llm_steps'] - r['bfs_hops']})"
                passed += 1
            detail = f"LLM={r['llm_steps']} BFS={r['bfs_hops']}"
        else:
            status = "FAIL"
            v = r["validation"]
            detail = f"BFS={r['bfs_hops']} | stuck={v.get('stuck_at', v.get('ended_at', '?'))}"

        # Truncate LLM answer for readability
        llm_short = (r.get("llm_answer", "?") or "?").replace("\n", " ")[:80]
        print(f"  [{status:>8}] {r['description']:40s} {detail}")
        print(f"           BFS: {r.get('bfs_path', '?')}")
        print(f"           LLM: {llm_short}")

    print(f"\n  => {fmt.upper()}: {passed}/{len(results)} reached, {optimal}/{len(results)} optimal\n")
    return passed, optimal


async def main():
    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    fmt_arg = "both"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        fmt_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "both"

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    mg = load_map()
    full_mermaid = mg.to_mermaid()
    text_adj = map_to_text_adjacency(mg)

    print(f"Map: {len(mg.rooms)} rooms, {sum(len(v) for v in mg.connections.values())} directed edges")
    print(f"Mermaid: {len(full_mermaid)} chars | Text adjacency: {len(text_adj)} chars")
    print(f"Model: {MODEL}")
    print(f"Test pairs: {len(TEST_PAIRS)}\n")

    formats_to_run = []
    if fmt_arg in ("mermaid", "both"):
        formats_to_run.append(("mermaid", full_mermaid))
    if fmt_arg in ("text", "both"):
        formats_to_run.append(("text", text_adj))

    # Run all formats in parallel
    all_tasks = []
    for fmt, repr_str in formats_to_run:
        all_tasks.append(run_suite(client, mg, repr_str, fmt))

    all_results = await asyncio.gather(*all_tasks)

    for (fmt, _), results in zip(formats_to_run, all_results):
        print(f"{'=' * 60}")
        print(f"  FORMAT: {fmt.upper()}")
        print(f"{'=' * 60}")
        print_results(results, fmt)


if __name__ == "__main__":
    asyncio.run(main())
