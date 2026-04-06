"""Tests for grounding validation."""
from unittest.mock import MagicMock
from zorkburr.llm.models import GroundingJudgment, GroundingValidationResponse
from zorkburr.config import GameConfig
from zorkburr.state import S, State, create_initial_state


def test_grounding_judgment_accepts():
    j = GroundingJudgment(item="Open the trapdoor", grounded=True, reason="Trapdoor mentioned in game text")
    assert j.grounded is True


def test_grounding_judgment_rejects():
    j = GroundingJudgment(item="Find the screwdriver in forest", grounded=False, reason="Screwdriver was in inventory, not found here")
    assert j.grounded is False


def test_grounding_validation_response_filters():
    resp = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Open trapdoor", grounded=True, reason="ok"),
        GroundingJudgment(item="Use screwdriver", grounded=False, reason="never seen"),
        GroundingJudgment(item="Explore cellar", grounded=True, reason="ok"),
    ])
    accepted = [j for j in resp.judgments if j.grounded]
    assert len(accepted) == 2
    assert accepted[0].item == "Open trapdoor"
    assert accepted[1].item == "Explore cellar"


def _make_action_history(entries: list[tuple[str, str]]) -> list[dict]:
    """Helper: build action history from (action, response) pairs."""
    return [{"turn": i + 1, "action": a, "response": r} for i, (a, r) in enumerate(entries)]


def test_call_grounding_validator_returns_judgments():
    from zorkburr.actions.grounding import _call_grounding_validator

    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Open trapdoor", grounded=True, reason="Trapdoor visible in room"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    history = _make_action_history([("look", "You see a trapdoor."), ("open trapdoor", "The trapdoor opens.")])

    result = _call_grounding_validator(
        client=mock_client,
        config=config,
        candidates=[{"item": "Open trapdoor"}],
        addendum="",
        action_history=history,
        location_name="Living Room",
        location_id=10,
        inventory=["lamp"],
    )
    assert len(result.judgments) == 1
    assert result.judgments[0].grounded is True
    # Verify the prompt was assembled with grounding_rules placeholder filled
    call_args = mock_client.create.call_args
    messages = call_args.kwargs["messages"]
    assert "{grounding_rules}" not in messages[0]["content"]


from zorkburr.actions.grounding import validate_memory


def _base_state_with_pending_memory() -> State:
    """Build a state with a pending memory ready for validation."""
    state = create_initial_state(episode_id="test-ep")
    return state.update(**{
        S.ACTION_HISTORY: _make_action_history([
            ("open mailbox", "Opening the small mailbox reveals a leaflet."),
        ]),
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.PRE_LOCATION_NAME: "West of House",
        S.INVENTORY: ["lamp"],
        S.TURN_COUNT: 5,
        S.PENDING_MEMORY: {
            "memory": {
                "category": "DISCOVERY",
                "title": "Leaflet in Mailbox",
                "text": "Open mailbox to find a leaflet inside.",
                "episode": "test-ep",
                "turn": 5,
                "persistence": "permanent",
                "status": "ACTIVE",
                "superseded_by": "",
            },
            "supersedes_titles": [],
            "loc_key": "10",
        },
    })


def test_validate_memory_pass_through_when_no_pending():
    """No pending memory -> no LLM call, state unchanged."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep")

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is False
    assert result["reason"] == "no_pending"
    mock_client.create.assert_not_called()


def test_validate_memory_accepted():
    """Grounded memory gets committed to MEMORIES_BY_LOCATION."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Leaflet in Mailbox", grounded=True, reason="Mailbox opened, leaflet found"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is True
    assert new_state[S.PENDING_MEMORY] is None
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems
    assert mems["10"][-1]["title"] == "Leaflet in Mailbox"
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_validate_memory_rejected():
    """Ungrounded memory gets dropped, stats updated."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Leaflet in Mailbox", grounded=False, reason="Leaflet was carried, not found here"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is False
    assert result["reason"] == "ungrounded"
    assert new_state[S.PENDING_MEMORY] is None
    # Memory NOT committed
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert mems.get("10", []) == []
    assert new_state[S.MEMORY_STATS]["grounding_rejected"] == 1


def test_validate_memory_disabled():
    """When grounding validator is disabled, commits unconditionally."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key", enable_grounding_validator=False)
    state = _base_state_with_pending_memory()

    result, new_state = validate_memory.run(state, client=mock_client, config=config)
    assert result["validated"] is True
    mock_client.create.assert_not_called()
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems


from zorkburr.actions.grounding import validate_objectives


def _base_state_with_pending_objectives() -> State:
    """Build a state with pending objectives ready for validation."""
    state = create_initial_state(episode_id="test-ep")
    return state.update(**{
        S.ACTION_HISTORY: _make_action_history([
            ("look", "You are west of a white house. There is a mailbox here."),
            ("open mailbox", "Opening the small mailbox reveals a leaflet."),
        ]),
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.INVENTORY: ["lamp"],
        S.TURN_COUNT: 10,
        S.PENDING_OBJECTIVES: [
            {"text": "Read the leaflet", "location_id": 10, "location_name": "West of House"},
            {"text": "Find the golden key in the attic", "location_id": 0, "location_name": ""},
        ],
        S.PENDING_COMPLETED_OBJECTIVES: ["Open the mailbox"],
    })


def test_validate_objectives_pass_through_when_no_pending():
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep")

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 0
    mock_client.create.assert_not_called()


def test_validate_objectives_filters_ungrounded():
    """Only grounded objectives get committed; ungrounded ones are dropped."""
    mock_client = MagicMock()
    mock_client.create.return_value = GroundingValidationResponse(judgments=[
        GroundingJudgment(item="Read the leaflet", grounded=True, reason="Leaflet found in mailbox"),
        GroundingJudgment(item="Find the golden key in the attic", grounded=False, reason="No attic or key seen"),
    ])
    config = GameConfig(openrouter_api_key="test-key")
    state = _base_state_with_pending_objectives()

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 1
    assert result["rejected"] == 1
    assert new_state[S.PENDING_OBJECTIVES] is None
    assert new_state[S.PENDING_COMPLETED_OBJECTIVES] is None
    # Only grounded objective committed
    obj_texts = [o["text"] if isinstance(o, dict) else o for o in new_state[S.DISCOVERED_OBJECTIVES]]
    assert "Read the leaflet" in obj_texts
    assert "Find the golden key in the attic" not in obj_texts
    # Completed objectives always committed
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1
    assert new_state[S.COMPLETED_OBJECTIVES][0]["objective"] == "Open the mailbox"


def test_validate_objectives_completions_committed_without_pending():
    """Completed objectives are committed even when no new objectives are pending."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.TURN_COUNT: 10,
        S.PENDING_OBJECTIVES: None,
        S.PENDING_COMPLETED_OBJECTIVES: ["Explore the house"],
    })

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    mock_client.create.assert_not_called()
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1


def test_validate_objectives_disabled():
    """When grounding validator is disabled, commits all objectives unconditionally."""
    mock_client = MagicMock()
    config = GameConfig(openrouter_api_key="test-key", enable_grounding_validator=False)
    state = _base_state_with_pending_objectives()

    result, new_state = validate_objectives.run(state, client=mock_client, config=config)
    assert result["validated"] == 2
    mock_client.create.assert_not_called()
    obj_texts = [o["text"] if isinstance(o, dict) else o for o in new_state[S.DISCOVERED_OBJECTIVES]]
    assert "Read the leaflet" in obj_texts
    assert "Find the golden key in the attic" in obj_texts


from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.actions.memory import record_memory


def test_record_memory_writes_pending_instead_of_committing():
    """record_memory should set PENDING_MEMORY instead of writing to MEMORIES_BY_LOCATION."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True,
        reasoning="Score changed",
        category="SUCCESS",
        memory_title="Mailbox Leaflet Found",
        memory_text="Open mailbox to find leaflet.",
        persistence="permanent",
        status="ACTIVE",
        supersedes_titles=[],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.PRE_LOCATION_ID: 10,
        S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0,
        S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10,
        S.SCORE: 10,  # Score changed -> triggers synthesis
        S.INVENTORY: [],
        S.GAME_OVER: False,
        S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox",
        S.AGENT_REASONING: "Check the mailbox",
        S.ACTION_HISTORY: _make_action_history([("open mailbox", "Opening the mailbox reveals a leaflet.")]),
        S.TURN_COUNT: 5,
    })

    result, new_state = record_memory.run(state, client=mock_client, config=config)
    assert result["synthesized"] is True
    # Memory should be in PENDING_MEMORY, NOT in MEMORIES_BY_LOCATION
    assert new_state[S.PENDING_MEMORY] is not None
    assert new_state[S.PENDING_MEMORY]["memory"]["title"] == "Mailbox Leaflet Found"
    assert new_state[S.PENDING_MEMORY]["loc_key"] == "10"
    # MEMORIES_BY_LOCATION should be unchanged (empty)
    assert new_state[S.MEMORIES_BY_LOCATION] == {}


from zorkburr.actions.objectives import update_objectives
from zorkburr.llm.models import ObjectiveDiscoveryResponse, Objective


def test_update_objectives_writes_pending():
    """update_objectives should set PENDING_OBJECTIVES instead of committing directly."""
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=[Objective(text="Read the leaflet", location_id=10, location_name="West of House")],
        completed=["Open the mailbox"],
    )
    config = GameConfig(openrouter_api_key="test-key")
    state = create_initial_state(episode_id="test-ep").update(**{
        S.ACTION_HISTORY: _make_action_history([("open mailbox", "Opening reveals a leaflet.")]),
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.SCORE: 10,
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 10,
        S.TURN_COUNT: 10,
        S.KNOWLEDGE_BASE: "",
        S.MAP_DATA: {"rooms": {"10": "West of House"}},
        S.DISCOVERED_OBJECTIVES: [{"text": "Open the mailbox", "location_id": 10, "location_name": "West of House"}],
    })

    result, new_state = update_objectives.run(state, client=mock_client, config=config, use_thinking=False)
    assert result["new_count"] == 1
    # New objectives should be PENDING, not committed
    assert new_state[S.PENDING_OBJECTIVES] is not None
    assert len(new_state[S.PENDING_OBJECTIVES]) == 1
    assert new_state[S.PENDING_OBJECTIVES][0]["text"] == "Read the leaflet"
    # Completions should be pending too
    assert new_state[S.PENDING_COMPLETED_OBJECTIVES] == ["Open the mailbox"]
    # DISCOVERED_OBJECTIVES should be unchanged (still has the old one)
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 1
    assert new_state[S.DISCOVERED_OBJECTIVES][0]["text"] == "Open the mailbox"
