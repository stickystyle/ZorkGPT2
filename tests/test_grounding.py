"""Tests for grounding validation."""
from unittest.mock import MagicMock
from zorkburr.llm.models import GroundingJudgment, GroundingValidationResponse
from zorkburr.config import GameConfig


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
