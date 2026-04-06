"""Tests for grounding validation."""
from zorkburr.llm.models import GroundingJudgment, GroundingValidationResponse


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
