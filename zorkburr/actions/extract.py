"""Hybrid information extraction: Jericho for objects, LLM for exits/combat."""
from __future__ import annotations
import logging
import instructor
from zorkburr.actions import action
from burr.core import State
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import effective_model, nothink_prefix, thinking_kwargs
from zorkburr.llm.models import ExtractorResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)
_extractor_prompt: str | None = None

def _get_extractor_prompt() -> str:
    global _extractor_prompt
    if _extractor_prompt is None:
        _extractor_prompt = load_prompt("extractor")
    return _extractor_prompt

@action(
    reads=[S.GAME_RESPONSE, S.LOCATION_NAME, S.LOCATION_ID, S.IN_COMBAT],
    writes=[S.EXITS, S.IN_COMBAT, S.IS_ROOM_DESCRIPTION, S.VISIBLE_OBJECTS],
)
def extract_info(state: State, client: instructor.Instructor, jericho: JerichoInterface, config: GameConfig) -> tuple[dict, State]:
    """Extract structured game state using hybrid approach."""
    game_text = state[S.GAME_RESPONSE]
    visible_objects = jericho.get_visible_objects()

    exits = []
    in_combat = state[S.IN_COMBAT]
    is_room_description = False

    try:
        system = _get_extractor_prompt()
        user_msg = (
            f"Current Location: {state[S.LOCATION_NAME]}\n"
            f"Previous Combat State: {state[S.IN_COMBAT]}\n\n"
            f"Game Text:\n```\n{game_text}\n```"
        )
        response: ExtractorResponse = client.create(
            model=effective_model(config, config.extractor_model),
            response_model=ExtractorResponse,
            messages=[
                {"role": "system", "content": nothink_prefix(config, False) + system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=128,
            max_retries=2,
            **thinking_kwargs(config, False),
        )
        exits = response.exits
        in_combat = response.in_combat
        is_room_description = response.is_room_description
    except Exception as e:
        logger.warning(f"Extractor LLM failed: {e}")

    return (
        {"exits_found": len(exits)},
        state.update(**{
            S.EXITS: exits,
            S.IN_COMBAT: in_combat,
            S.IS_ROOM_DESCRIPTION: is_room_description,
            S.VISIBLE_OBJECTS: visible_objects,
        }),
    )
