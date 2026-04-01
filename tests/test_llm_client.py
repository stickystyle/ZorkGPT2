from unittest.mock import MagicMock
from pydantic import ValidationError
import pytest
from zorkburr.llm.models import AgentResponse, CriticResponse, ExtractorResponse
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

def test_extractor_response_model():
    r = ExtractorResponse(exits=["north", "south"], in_combat=False, is_room_description=True)
    assert len(r.exits) == 2

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


def test_effective_model_local():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import effective_model
    config = GameConfig(use_local_models=True)
    assert effective_model(config, "anthropic/claude-sonnet-4.6") == config.local_model


def test_effective_model_openrouter():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import effective_model
    config = GameConfig(openrouter_api_key="test-key", use_local_models=False)
    assert effective_model(config, "anthropic/claude-haiku-4.5") == "anthropic/claude-haiku-4.5"


def test_create_llm_client_local():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(use_local_models=True)
    client = create_llm_client(config)
    assert client is not None


def test_create_llm_client_openrouter():
    from zorkburr.config import GameConfig
    from zorkburr.llm.client import create_llm_client
    config = GameConfig(openrouter_api_key="test-key")
    client = create_llm_client(config)
    assert client is not None
