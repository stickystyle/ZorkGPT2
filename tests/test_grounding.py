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
