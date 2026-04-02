from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.memory import record_memory, should_synthesize, Memory
from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.state import S

def test_memory_dataclass():
    m = Memory(category="SUCCESS", title="Opened mailbox", text="Reveals a leaflet.",
               episode="ep-1", turn=5, persistence="permanent", status="ACTIVE")
    assert m.category == "SUCCESS"
    assert m.is_active

def test_should_synthesize_on_score_change():
    assert should_synthesize(score_delta=5, location_changed=False, died=False) is True

def test_should_synthesize_on_location_change():
    assert should_synthesize(score_delta=0, location_changed=True, died=False) is True

def test_should_not_synthesize_no_change():
    assert should_synthesize(score_delta=0, location_changed=False, died=False) is False

def test_record_memory_with_synthesis():
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Mailbox contains a leaflet.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems
    assert len(mems["10"]) == 1
    assert mems["10"][0]["title"] == "Found leaflet"

def test_record_memory_skips_no_change():
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 0, S.INVENTORY: [],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Nothing happens.", S.ACTION_TO_TAKE: "look",
        S.AGENT_REASONING: "look around", S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {}, S.EPISODE_ID: "ep-1", S.TURN_COUNT: 2,
    })
    result, new_state = record_memory.run(state, client=MagicMock(), config=MagicMock())
    assert result["synthesized"] is False


def test_record_memory_rejects_duplicate_title():
    """Exact-title dedup guard: reject memory with same title as existing."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Different text but same title.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found leaflet",
                    "text": "Mailbox contains a leaflet.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is False
    assert result["reason"] == "duplicate_title"
    # Memory list unchanged
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 1


def test_record_memory_allows_duplicate_title_if_superseded():
    """Dedup guard ignores SUPERSEDED memories — the title is available for reuse."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Better version.", persistence="permanent",
        status="ACTIVE", reasoning="improved",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found leaflet",
                    "text": "Old version.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "SUPERSEDED",
                    "superseded_by": "Something else"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 2
