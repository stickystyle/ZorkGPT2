"""Memory recording and synthesis: location-based action outcome memories."""
from __future__ import annotations
import logging
from dataclasses import dataclass, asdict
import instructor
from langfuse import observe
from zorkburr.actions import action
from zorkburr.actions.episode import persist_memories
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.llm.client import effective_model, thinking_kwargs
from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

_synthesis_prompt: str | None = None

def _get_synthesis_prompt() -> str:
    global _synthesis_prompt
    if _synthesis_prompt is None:
        _synthesis_prompt = load_prompt("memory_synthesis")
    return _synthesis_prompt

@dataclass
class Memory:
    category: str
    title: str
    text: str
    episode: str
    turn: int
    persistence: str
    status: str
    superseded_by: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in ("ACTIVE", "TENTATIVE")

    def to_dict(self) -> dict:
        return asdict(self)

def should_synthesize(score_delta: int, location_changed: bool, died: bool) -> bool:
    return score_delta != 0 or location_changed or died

@action(
    reads=[S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME, S.PRE_SCORE, S.PRE_INVENTORY,
           S.LOCATION_ID, S.SCORE, S.INVENTORY, S.GAME_OVER, S.GAME_OVER_REASON,
           S.GAME_RESPONSE, S.ACTION_TO_TAKE, S.AGENT_REASONING, S.ACTION_HISTORY,
           S.MEMORIES_BY_LOCATION, S.EPISODE_ID, S.TURN_COUNT, S.MEMORY_STATS],
    writes=[S.MEMORIES_BY_LOCATION, S.MEMORY_STATS],
)
@observe(capture_input=False)
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
        mem_lines = [f"  - [{m['title']}]: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
        context += f"\nExisting memories at this location:\n" + "\n".join(mem_lines)

    try:
        response: MemorySynthesisResponse = client.create(
            model=effective_model(config, config.memory_model),
            response_model=MemorySynthesisResponse,
            messages=[
                {"role": "system", "content": _get_synthesis_prompt()},
                {"role": "user", "content": context},
            ],
            temperature=0.5, max_tokens=512, max_retries=2,
            **thinking_kwargs(config, False),
        )
        if response.should_remember:
            all_mems = dict(state[S.MEMORIES_BY_LOCATION])
            loc_list = list(all_mems.get(loc_key, []))

            # Dedup guard: reject exact title matches against non-superseded memories
            existing_titles = {m.get("title") for m in loc_list if m.get("status") != "SUPERSEDED"}
            if response.memory_title in existing_titles:
                logger.info(f"Rejected duplicate memory title: '{response.memory_title}' at location {loc_key}")
                stats = dict(state[S.MEMORY_STATS])
                stats["dedup_rejected"] = stats.get("dedup_rejected", 0) + 1
                return {"synthesized": False, "reason": "duplicate_title"}, state.update(**{S.MEMORY_STATS: stats})

            # Process supersession: mark old memories as replaced
            superseded_count = 0
            if response.supersedes_titles:
                for old_title in response.supersedes_titles:
                    found = False
                    for m in loc_list:
                        if m.get("title") == old_title and m.get("status") != "SUPERSEDED":
                            m["status"] = "SUPERSEDED"
                            m["superseded_by"] = response.memory_title
                            logger.info(f"Superseded memory '{old_title}' with '{response.memory_title}' at location {loc_key}")
                            superseded_count += 1
                            found = True
                            break
                    if not found:
                        logger.debug(f"Supersede target not found: '{old_title}' at location {loc_key}")

            mem = Memory(
                category=response.category, title=response.memory_title,
                text=response.memory_text, episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT], persistence=response.persistence,
                status=response.status,
            )
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list
            persist_memories(all_mems, config)
            stats = dict(state[S.MEMORY_STATS])
            stats["new"] = stats.get("new", 0) + 1
            stats["superseded"] = stats.get("superseded", 0) + superseded_count
            return {"synthesized": True, "memory_title": mem.title}, state.update(
                **{S.MEMORIES_BY_LOCATION: all_mems, S.MEMORY_STATS: stats}
            )
    except Exception as e:
        logger.warning(f"Memory synthesis failed: {e}")

    return {"synthesized": False}, state
