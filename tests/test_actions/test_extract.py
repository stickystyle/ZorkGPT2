from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.extract import extract_info
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.models import ExtractorResponse
from zorkburr.state import S

def test_extract_exits_from_jericho():
    mock_client = MagicMock()
    mock_client.create.return_value = ExtractorResponse(
        exits=["north"], in_combat=False, is_room_description=True
    )
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = [{"name": "mailbox", "num": 5}]
    mock_jericho.get_valid_exits.return_value = ["east", "north", "south", "west"]

    state = State({
        S.GAME_RESPONSE: "You are standing in a forest.",
        S.LOCATION_NAME: "Forest",
        S.LOCATION_ID: 10,
        S.IN_COMBAT: False,
    })
    result, new_state = extract_info.run(
        state, client=mock_client, jericho=mock_jericho,
        config=MagicMock(extractor_model="test")
    )
    # Exits come from Jericho (ground truth), not LLM
    assert new_state[S.EXITS] == ["east", "north", "south", "west"]
    assert new_state[S.IS_ROOM_DESCRIPTION] is True
    assert new_state[S.IN_COMBAT] is False
    assert {"name": "mailbox", "num": 5} in new_state[S.VISIBLE_OBJECTS]

def test_extract_fallback_on_llm_error():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("API error")
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = []
    mock_jericho.get_valid_exits.return_value = ["north", "south"]

    state = State({
        S.GAME_RESPONSE: "Darkness.",
        S.LOCATION_NAME: "Dark",
        S.LOCATION_ID: 1,
        S.IN_COMBAT: False,
    })
    result, new_state = extract_info.run(
        state, client=mock_client, jericho=mock_jericho,
        config=MagicMock(extractor_model="test")
    )
    # Exits still come from Jericho even when LLM fails
    assert new_state[S.EXITS] == ["north", "south"]
    assert new_state[S.IN_COMBAT] is False
