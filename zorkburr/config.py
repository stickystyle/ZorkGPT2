"""Game configuration loaded from pyproject.toml and environment."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _load_tool_config() -> dict:
    """Load [tool.zorkburr] from pyproject.toml."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return {}
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("zorkburr", {})


class GameConfig(BaseSettings):
    """All game configuration. Loaded from pyproject.toml + env vars."""

    model_config = {"env_prefix": "", "extra": "ignore", "populate_by_name": True}

    # API
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Game
    max_turns_per_episode: int = 1000
    turn_delay_seconds: float = 0.0
    game_file: str = "roms/zork1.z5"

    # LLM models
    agent_model: str = "anthropic/claude-sonnet-4-20250514"
    critic_model: str = "anthropic/claude-sonnet-4-20250514"
    extractor_model: str = "anthropic/claude-haiku-4-5-20251001"
    analysis_model: str = "anthropic/claude-sonnet-4-20250514"
    memory_model: str = "anthropic/claude-haiku-4-5-20251001"

    # LLM sampling
    default_temperature: float = 1.0
    default_max_tokens: int = 4096

    # Critic
    enable_critic: bool = True
    critic_rejection_threshold: float = 0.3
    max_rejections_per_turn: int = 3

    # Periodic intervals
    objective_update_interval: int = 10
    knowledge_update_interval: int = 50

    # Progress detection
    max_turns_stuck: int = 40
    stuck_check_interval: int = 10

    # File paths
    memory_file: str = "data/memories.md"
    knowledge_file: str = "data/knowledge.md"
    map_file: str = "data/map.json"

    # Retry (flattened from [tool.zorkburr.retry])
    retry_max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_max_delay: float = 30.0

    def __init__(self, **kwargs):
        toml_data = _load_tool_config()
        retry = toml_data.pop("retry", {})
        for k, v in retry.items():
            toml_data[f"retry_{k}"] = v
        merged = {**toml_data, **kwargs}
        super().__init__(**merged)
