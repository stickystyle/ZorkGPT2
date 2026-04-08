"""Direct probe: call memory_synthesis LLM with a fixture and print raw output.

Bypasses validate_memory grounding and dedup — just shows what the synthesis
LLM decides. Useful to answer "does Ministral say should_remember=False?"

Usage: uv run python scripts/_probe_memory_synthesis.py <fixture.json>
"""
import json
import sys

from zorkburr.config import GameConfig
from zorkburr.llm.client import create_llm_client, thinking_kwargs
from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.actions.memory import _get_synthesis_prompt


def probe(fixture_path: str, model_override: str | None = None) -> None:
    with open(fixture_path) as f:
        fixture = json.load(f)

    state = fixture["state"]
    pre_loc_name = state["pre_location_name"]
    pre_loc_id = state["pre_location_id"]
    pre_inv = state["pre_inventory"] or []
    loc_id = state["location_id"]
    score = state["score"]
    pre_score = state["pre_score"]
    action = state["action_to_take"]
    reasoning = state["agent_reasoning"]
    response = state["game_response"]
    mems_by_loc = state.get("memories_by_location", {}) or {}

    score_delta = score - pre_score
    location_changed = loc_id != pre_loc_id
    died = state.get("game_over") and state.get("game_over_reason") == "death"

    inv_str = ", ".join(pre_inv) if pre_inv else "(empty)"
    context = (
        f"Location: {pre_loc_name} (ID: {pre_loc_id})\n"
        f"Inventory (items agent was CARRYING, not found here): {inv_str}\n"
        f"Action: {action}\n"
        f"Agent reasoning: {reasoning}\n"
        f"Response: {response[:500]}\n\n"
        f"Score change: {score_delta}\nLocation changed: {location_changed}\nDied: {died}\n"
    )
    loc_key = str(pre_loc_id)
    existing = mems_by_loc.get(loc_key, [])
    if existing:
        mem_lines = [
            f"  - [{m['title']}]: {m['text']}"
            for m in existing
            if m.get("status") != "SUPERSEDED"
        ]
        context += "\nExisting memories at this location:\n" + "\n".join(mem_lines)

    config = GameConfig()
    if model_override:
        config.memory_model = model_override
    client = create_llm_client(config)

    print("=" * 70)
    print("PROBE: memory_synthesis")
    print("=" * 70)
    print(f"Model: {config.memory_model}")
    print(f"Fixture: {fixture_path}")
    print(f"Episode: {fixture['meta']['episode_id']} t{fixture['meta']['turn']}")
    print()
    print("--- USER CONTEXT SENT TO LLM ---")
    print(context)
    print()
    print("--- GATE CHECK ---")
    print(f"  score_delta:     {score_delta}")
    print(f"  location_changed: {location_changed}")
    print(f"  died:            {died}")
    print(f"  should_synthesize → {score_delta != 0 or location_changed or died}")
    print()

    try:
        result: MemorySynthesisResponse = client.create(
            model=config.memory_model,
            response_model=MemorySynthesisResponse,
            messages=[
                {"role": "system", "content": _get_synthesis_prompt()},
                {"role": "user", "content": context},
            ],
            temperature=0.5,
            max_tokens=512,
            max_retries=2,
            **thinking_kwargs(config, config.memory_model, False),
        )
        print("--- RAW LLM RESPONSE ---")
        print(json.dumps(result.model_dump(), indent=2))
    except Exception as e:
        print(f"--- LLM CALL FAILED ---")
        print(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    fixture = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else None
    probe(fixture, model)
