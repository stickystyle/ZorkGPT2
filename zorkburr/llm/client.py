"""LLM client factory using Instructor for structured output."""
from __future__ import annotations
import logging
import instructor
from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

def create_llm_client(config: GameConfig) -> instructor.Instructor:
    return instructor.from_provider(
        f"openrouter/{config.agent_model}",
        base_url=config.openrouter_base_url,
        api_key=config.openrouter_api_key,
    )

def create_local_client(base_url: str = "http://localhost:11434/v1", model: str = "llama3") -> instructor.Instructor:
    return instructor.from_provider(f"ollama/{model}", base_url=base_url, mode=instructor.Mode.JSON)
