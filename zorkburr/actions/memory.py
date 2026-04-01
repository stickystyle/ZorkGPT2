"""Memory recording and synthesis: location-based action outcome memories."""
from __future__ import annotations
import logging
from dataclasses import dataclass, asdict
import instructor
from zorkburr.actions import action
from zorkburr.actions.episode import persist_memories
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.client import effective_model, nothink_prefix
from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.state import S

logger = logging.getLogger(__name__)

@dataclass
class Memory:
    category: str
    title: str
    text: str
    episode: str
    turn: int
    persistence: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status in ("ACTIVE", "TENTATIVE")

    def to_dict(self) -> dict:
        return asdict(self)

def should_synthesize(score_delta: int, location_changed: bool, died: bool) -> bool:
    return score_delta != 0 or location_changed or died

_SYNTHESIS_PROMPT = """You are a memory synthesizer for an AI playing Zork I.
Given an action and its outcome, decide if this is worth remembering.

Rules:
- DO remember: object interactions, dangers, puzzle mechanics, item discoveries, score-earning actions
- DO NOT remember: simple movement between rooms, looking around, exits/directions (tracked by map)
- Memories are stored at the SOURCE location (where the action was taken)

If should_remember=true, provide category, memory_title (3-6 words), memory_text (1-2 sentences), persistence (core|permanent|ephemeral), status (ACTIVE|TENTATIVE).
"""

@action(
    reads=[S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME, S.PRE_SCORE, S.PRE_INVENTORY,
           S.LOCATION_ID, S.SCORE, S.INVENTORY, S.GAME_OVER, S.GAME_OVER_REASON,
           S.GAME_RESPONSE, S.ACTION_TO_TAKE, S.AGENT_REASONING, S.ACTION_HISTORY,
           S.MEMORIES_BY_LOCATION, S.EPISODE_ID, S.TURN_COUNT],
    writes=[S.MEMORIES_BY_LOCATION],
)
def record_memory(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    location_changed = state[S.LOCATION_ID] != state[S.PRE_LOCATION_ID]
    died = state[S.GAME_OVER] and state[S.GAME_OVER_REASON] == "death"

    if not should_synthesize(score_delta, location_changed, died):
        return {"synthesized": False}, state

    context = (
        f"Location: {state[S.PRE_LOCATION_NAME]} (ID: {state[S.PRE_LOCATION_ID]})\n"
        f"Action: {state[S.ACTION_TO_TAKE]}\n"
        f"Agent reasoning: {state[S.AGENT_REASONING]}\n"
        f"Response: {state[S.GAME_RESPONSE][:500]}\n\n"
        f"Score change: {score_delta}\nLocation changed: {location_changed}\nDied: {died}\n"
    )

    loc_key = str(state[S.PRE_LOCATION_ID])
    existing = state[S.MEMORIES_BY_LOCATION].get(loc_key, [])
    if existing:
        mem_lines = [f"  - [{m['category']}] {m['title']}: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
        context += f"\nExisting memories at this location:\n" + "\n".join(mem_lines)

    try:
        response: MemorySynthesisResponse = client.create(
            model=effective_model(config, config.memory_model),
            response_model=MemorySynthesisResponse,
            messages=[
                {"role": "system", "content": nothink_prefix(config, False) + _SYNTHESIS_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.5, max_tokens=512, max_retries=2,
        )
        if response.should_remember:
            mem = Memory(
                category=response.category, title=response.memory_title,
                text=response.memory_text, episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT], persistence=response.persistence,
                status=response.status,
            )
            all_mems = dict(state[S.MEMORIES_BY_LOCATION])
            loc_list = list(all_mems.get(loc_key, []))
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list
            persist_memories(all_mems, config)
            return {"synthesized": True, "memory_title": mem.title}, state.update(**{S.MEMORIES_BY_LOCATION: all_mems})
    except Exception as e:
        logger.warning(f"Memory synthesis failed: {e}")

    return {"synthesized": False}, state
