"""LLM client factory using Instructor for structured output."""
from __future__ import annotations

import logging

import instructor
from openai import OpenAI

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

THINKING_ACTIONS = frozenset({"generate_action", "update_objectives", "update_knowledge"})


def thinking_kwargs(config: GameConfig, use_thinking: bool) -> dict:
    """Return extra_body for Qwen3 think toggle on local runs; empty dict on OpenRouter."""
    if config.use_local_models:
        return {"extra_body": {"thinking": use_thinking}}
    return {}


def effective_model(config: GameConfig, role_model: str) -> str:
    """Return local_model when using local inference, otherwise the role-specific model."""
    return config.local_model if config.use_local_models else role_model


def create_llm_client(config: GameConfig) -> instructor.Instructor:
    if config.use_local_models:
        return instructor.from_openai(
            OpenAI(base_url=config.local_base_url, api_key="local")
        )
    return instructor.from_provider(
        f"openrouter/{config.agent_model}",
        base_url=config.openrouter_base_url,
        api_key=config.openrouter_api_key,
    )
