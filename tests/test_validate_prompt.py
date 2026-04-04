"""Tests for validate_prompt.py — replay and validation logic."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _make_fixture(action_type="generate_action", role="problem", **state_overrides):
    """Build a minimal fixture dict for testing."""
    base_state = {
        "formatted_context": "You are at the house.",
        "rejection_count": 0,
        "critic_justification": "",
        "knowledge_base": "",
        "turn_count": 5,
    }
    base_state.update(state_overrides)
    return {
        "meta": {
            "app_id": "test",
            "episode_id": "ep01",
            "turn": 5,
            "extracted_at": "2026-04-04T00:00:00Z",
            "role": role,
            "problem_description": "Agent did something bad" if role == "problem" else "",
        },
        "action_type": action_type,
        "state": base_state,
        "original_output": {
            "proposed_action": "examine mailbox",
            "agent_reasoning": "check the mailbox",
            "next_steps": "",
            "new_objective": "",
        },
    }


def test_replay_generate_action():
    from validate_prompt import replay_fixture
    from zorkburr.llm.models import AgentResponse

    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="I should go north", action="north", next_steps="", new_objective=""
    )
    mock_config = MagicMock(
        agent_model="test", default_temperature=1.0, default_max_tokens=4096,
        use_local_models=False,
    )

    fixture = _make_fixture()
    new_output = replay_fixture(fixture, client=mock_client, config=mock_config)

    assert new_output is not None
    assert new_output["proposed_action"] == "north"
    assert "go north" in new_output["agent_reasoning"]


def test_structural_check_problem_action_changed():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "go north", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is True


def test_structural_check_problem_action_same():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "examine mailbox", "agent_reasoning": "check", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is False


def test_structural_check_healthy_allows_same_action():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="healthy")
    new_output = {"proposed_action": "examine mailbox", "agent_reasoning": "check", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is True


def test_structural_check_fallback_fails():
    from validate_prompt import structural_check

    fixture = _make_fixture(role="healthy")
    new_output = {"proposed_action": "look", "agent_reasoning": "LLM error: timeout", "next_steps": "", "new_objective": ""}
    result = structural_check(fixture, new_output)
    assert result["passed"] is False


def test_structural_check_replay_error():
    from validate_prompt import structural_check

    fixture = _make_fixture()
    new_output = {"_error": "Connection refused"}
    result = structural_check(fixture, new_output)
    assert result["passed"] is False
    assert "Connection refused" in result["detail"]


def test_judge_problem_pass():
    from validate_prompt import judge_fixture

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "PASS: The new output addresses the memory issue."
    mock_client.client.chat.completions.create.return_value = mock_response

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "I recall this area", "next_steps": "", "new_objective": ""}
    mock_config = MagicMock(analysis_model="test", use_local_models=False, local_model="test", llm_request_timeout=60)

    result = judge_fixture(fixture, new_output, client=mock_client, config=mock_config)
    assert result["passed"] is True


def test_judge_problem_fail():
    from validate_prompt import judge_fixture

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "FAIL: The agent still ignores location memories."
    mock_client.client.chat.completions.create.return_value = mock_response

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north", "agent_reasoning": "go north", "next_steps": "", "new_objective": ""}
    mock_config = MagicMock(analysis_model="test", use_local_models=False, local_model="test", llm_request_timeout=60)

    result = judge_fixture(fixture, new_output, client=mock_client, config=mock_config)
    assert result["passed"] is False


def test_judge_error_returns_fail():
    from validate_prompt import judge_fixture

    mock_client = MagicMock()
    mock_client.client.chat.completions.create.side_effect = Exception("timeout")

    fixture = _make_fixture(role="problem")
    new_output = {"proposed_action": "north"}
    mock_config = MagicMock(analysis_model="test", use_local_models=False, local_model="test", llm_request_timeout=60)

    result = judge_fixture(fixture, new_output, client=mock_client, config=mock_config)
    assert result["passed"] is False
    assert "timeout" in result["detail"]
