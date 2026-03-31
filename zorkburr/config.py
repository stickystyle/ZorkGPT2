"""Game configuration loaded from pyproject.toml and environment."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "extra": "ignore",
        "populate_by_name": True,
        "case_sensitive": False,
    }

    # API
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Local models
    use_local_models: bool = Field(default=False, alias="USE_LOCAL_MODELS")
    local_model: str = "mlx-community/Qwen3-14B-MLX-8bit"
    local_base_url: str = "http://localhost:8080/v1"

    # Game
    max_turns_per_episode: int = 1000
    turn_delay_seconds: float = 0.0
    game_file: str = "roms/zork1.z5"

    # LLM models
    agent_model: str = "anthropic/claude-sonnet-4.6"
    critic_model: str = "anthropic/claude-sonnet-4.6"
    extractor_model: str = "anthropic/claude-haiku-4.5"
    analysis_model: str = "anthropic/claude-sonnet-4.6"
    memory_model: str = "anthropic/claude-haiku-4.5"

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

    # Viewer / S3
    s3_bucket: str = ""
    s3_key_prefix: str = ""

    # Retry (flattened from [tool.zorkburr.retry])
    retry_max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_max_delay: float = 30.0

    def __init__(self, **kwargs):
        # Load toml data first, but let env vars override (they're handled by pydantic-settings)
        toml_data = _load_tool_config()
        retry = toml_data.pop("retry", {})
        for k, v in retry.items():
            toml_data[f"retry_{k}"] = v

        # Check env vars and override toml data if present
        # This mirrors pydantic-settings behavior with aliases
        env_overrides = {}
        if os.getenv("USE_LOCAL_MODELS"):
            env_overrides["use_local_models"] = os.getenv("USE_LOCAL_MODELS").lower() == "true"

        # Merge: kwargs take precedence over env, which takes precedence over toml
        merged = {**toml_data, **env_overrides, **kwargs}
        super().__init__(**merged)
