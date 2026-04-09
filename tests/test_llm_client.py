from unittest.mock import MagicMock
from pydantic import ValidationError
import pytest
from zorkburr.llm.models import AgentResponse, CriticResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.utils import clean_action

def test_load_prompt():
    text = load_prompt("agent")
    assert len(text) > 0

def test_agent_response_model():
    r = AgentResponse(thinking="explore", action="north", new_objective="")
    assert r.action == "north"

def test_critic_response_model():
    r = CriticResponse(score=0.5, justification="good", confidence=0.8)
    assert -1.0 <= r.score <= 1.0

def test_critic_response_rejects_out_of_range():
    with pytest.raises(ValidationError):
        CriticResponse(score=2.0, justification="bad", confidence=0.5)

def test_clean_action():
    assert clean_action("  NORTH  ") == "north"
    assert clean_action('```\nnorth\n```') == "north"
    assert clean_action('"go north"') == "go north"

def test_create_llm_client():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(openrouter_api_key="test-key")
    client = create_llm_client(config)
    assert client is not None


# --- Routing helpers ---

def test_is_remote_model_remote_prefix():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import is_remote_model
    config = GameConfig(use_local_models=True)
    assert is_remote_model("remote/google/gemma-4-31b-it", config) is True


def test_is_remote_model_local_prefix():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import is_remote_model
    config = GameConfig(use_local_models=False, openrouter_api_key="test-key")
    # local/ prefix overrides even when use_local_models=False
    assert is_remote_model("local/mistralai/ministral", config) is False


def test_is_remote_model_no_prefix_local_mode():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import is_remote_model
    config = GameConfig(use_local_models=True)
    assert is_remote_model("mistralai/ministral-3-14b", config) is False


def test_is_remote_model_no_prefix_remote_mode():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import is_remote_model
    config = GameConfig(openrouter_api_key="test-key", use_local_models=False)
    assert is_remote_model("mistralai/ministral-3-14b", config) is True


def test_strip_model_prefix():
    from zorkburr.llm.client import _strip_model_prefix
    assert _strip_model_prefix("remote/google/gemma-4-31b-it") == "google/gemma-4-31b-it"
    assert _strip_model_prefix("local/mistralai/ministral") == "mistralai/ministral"
    assert _strip_model_prefix("mistralai/ministral") == "mistralai/ministral"


def test_has_remote_roles_mixed():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import _has_remote_roles
    config = GameConfig(
        use_local_models=True,
        agent_model="remote/google/gemma-4-31b-it",
        critic_model="mistralai/ministral-3-14b",
    )
    assert _has_remote_roles(config) is True


def test_has_remote_roles_all_local():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import _has_remote_roles
    config = GameConfig(
        use_local_models=True,
        agent_model="mistralai/ministral-3-14b-reasoning",
    )
    assert _has_remote_roles(config) is False


# --- Client creation ---

def test_create_llm_client_local():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(
        use_local_models=True,
        agent_model="mistralai/ministral-3-14b-reasoning",
    )
    client = create_llm_client(config)
    assert client is not None
    assert client._local is not None
    assert client._remote is None


def test_create_llm_client_openrouter():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(
        openrouter_api_key="test-key",
        use_local_models=False,
    )
    client = create_llm_client(config)
    assert client is not None
    assert client._local is None
    assert client._remote is not None


def test_create_llm_client_hybrid():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(
        use_local_models=True,
        openrouter_api_key="test-key",
        agent_model="remote/google/gemma-4-31b-it",
    )
    client = create_llm_client(config)
    assert client._local is not None
    assert client._remote is not None
