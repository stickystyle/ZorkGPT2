from unittest.mock import MagicMock, patch
from burr.core import State
from zorkburr.actions.memory import record_memory, should_synthesize, Memory
from zorkburr.llm.models import LocationSummaryResponse, MemorySynthesisResponse
from zorkburr.state import S


def _mock_client_with_summary(synthesis_response):
    """Create a mock client that returns synthesis_response first, then a summary."""
    mock = MagicMock()
    mock.create.side_effect = [
        synthesis_response,
        LocationSummaryResponse(summary="test summary"),
    ]
    return mock

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
    mock_client = _mock_client_with_summary(MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Mailbox contains a leaflet.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    ))
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
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
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is False
    assert result["reason"] == "duplicate_title"
    # Memory list unchanged
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 1


def test_record_memory_allows_duplicate_title_if_superseded():
    """Dedup guard ignores SUPERSEDED memories — the title is available for reuse."""
    mock_client = _mock_client_with_summary(MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Better version.", persistence="permanent",
        status="ACTIVE", reasoning="improved",
    ))
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
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 2


def test_record_memory_increments_new_counter():
    """Memory stats 'new' counter should increment on successful synthesis."""
    mock_client = _mock_client_with_summary(MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Mailbox contains a leaflet.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    ))
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_record_memory_increments_dedup_counter():
    """Memory stats 'dedup_rejected' counter should increment on duplicate title."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Different text.", persistence="permanent",
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
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is False
    assert new_state[S.MEMORY_STATS]["dedup_rejected"] == 1


def test_memory_dataclass_has_superseded_by():
    m = Memory(category="SUCCESS", title="Old info", text="Was wrong.",
               episode="ep-1", turn=5, persistence="permanent", status="SUPERSEDED",
               superseded_by="New info")
    d = m.to_dict()
    assert d["superseded_by"] == "New info"
    assert not m.is_active  # SUPERSEDED is not active


def test_memory_dataclass_defaults_superseded_by_empty():
    m = Memory(category="SUCCESS", title="Good info", text="Still valid.",
               episode="ep-1", turn=5, persistence="permanent", status="ACTIVE")
    assert m.superseded_by == ""


def test_record_memory_context_includes_titles(monkeypatch):
    """Synthesis context should show memory titles so the LLM can reference them for supersession."""
    captured_messages = []
    def mock_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return MemorySynthesisResponse(
            should_remember=False, reasoning="test", category="NOTE",
            memory_title="", memory_text="", persistence="ephemeral", status="ACTIVE",
        )

    mock_client = MagicMock()
    mock_client.create.side_effect = mock_create
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found Mailbox",
                    "text": "Mailbox is near the house.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))

    # Check the user message sent to the LLM includes the title in bracket format
    user_msg = captured_messages[0][1]["content"]
    assert "[Found Mailbox]:" in user_msg


def test_record_memory_supersedes_old_memory():
    """When LLM returns supersedes_titles, old memories should be marked SUPERSEDED."""
    mock_client = _mock_client_with_summary(MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY",
        memory_title="Safe Descent with Lantern",
        memory_text="Staircase is safe when carrying the lantern.",
        persistence="permanent", status="ACTIVE", reasoning="corrects old info",
        supersedes_titles=["Dark Staircase Deadly"],
    ))
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "Cellar",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 10, S.INVENTORY: ["lantern"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "You carefully descend the staircase.",
        S.ACTION_TO_TAKE: "go down", S.AGENT_REASONING: "try with lantern",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DANGER", "title": "Dark Staircase Deadly",
                    "text": "Going down without light is fatal.",
                    "episode": "ep-0", "turn": 5, "persistence": "permanent",
                    "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-2", S.TURN_COUNT: 8,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    mems = new_state[S.MEMORIES_BY_LOCATION]["10"]
    # Old memory marked SUPERSEDED
    old = next(m for m in mems if m["title"] == "Dark Staircase Deadly")
    assert old["status"] == "SUPERSEDED"
    assert old["superseded_by"] == "Safe Descent with Lantern"
    # New memory added
    new = next(m for m in mems if m["title"] == "Safe Descent with Lantern")
    assert new["status"] == "ACTIVE"
    # Stats updated
    assert new_state[S.MEMORY_STATS]["superseded"] == 1
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_record_memory_ignores_nonexistent_supersede_title():
    """If supersedes_titles names a title that doesn't exist, skip it gracefully."""
    mock_client = _mock_client_with_summary(MemorySynthesisResponse(
        should_remember=True, category="NOTE",
        memory_title="New Memory",
        memory_text="Some insight.",
        persistence="permanent", status="ACTIVE", reasoning="test",
        supersedes_titles=["Nonexistent Title"],
    ))
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: [],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Something happened.",
        S.ACTION_TO_TAKE: "look", S.AGENT_REASONING: "check",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 3,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
        S.LOCATION_SUMMARIES: {},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert new_state[S.MEMORY_STATS]["superseded"] == 0
