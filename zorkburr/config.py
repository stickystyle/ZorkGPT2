"""Game configuration loaded from pyproject.toml and environment."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings.sources import PydanticBaseSettingsSource


def _load_tool_config() -> dict:
    """Load [tool.zorkburr] from pyproject.toml."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return {}
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("zorkburr", {})


class _TomlSettingsSource(PydanticBaseSettingsSource):
    """Load configuration from pyproject.toml [tool.zorkburr]."""

    def get_field_value(self, field):
        """Not used in this source."""
        return None, None, False

    def __call__(self):
        """Return the toml data as a settings dict."""
        toml_data = _load_tool_config()
        retry = toml_data.pop("retry", {})
        for k, v in retry.items():
            toml_data[f"retry_{k}"] = v
        return toml_data


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

    # Local models (llama-server)
    use_local_models: bool = Field(default=False, alias="USE_LOCAL_MODELS")
    local_model: str = "models/Qwen3.5-35B-A3B-Q4_K_M.gguf"
    local_base_url: str = "http://localhost:8080/v1"
    llama_server_path: str = "llama-server"
    context_size: int = 8192
    n_gpu_layers: int = -1
    n_parallel: int = 1

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
    memory_file: str = "data/memories.json"
    knowledge_file: str = "data/knowledge.md"
    map_file: str = "data/map.json"

    # Viewer / S3
    s3_bucket: str = ""
    s3_key_prefix: str = ""

    # LLM request timeout (total wall-clock seconds per request)
    llm_request_timeout: int = 300

    # Retry (flattened from [tool.zorkburr.retry])
    retry_max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_max_delay: float = 30.0

    @classmethod
    def settings_customise_sources(
        cls,
        settings_customise_sources=None,
        init_settings=None,
        env_settings=None,
        dotenv_settings=None,
        file_secret_settings=None,
    ):
        """Customize settings sources: init > env > toml > file > defaults."""
        return (
            init_settings,
            env_settings,
            _TomlSettingsSource(cls),
            dotenv_settings,
            file_secret_settings,
        )
