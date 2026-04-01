from zorkburr.config import GameConfig


def test_load_config_from_toml():
    config = GameConfig()
    assert config.max_turns_per_episode == 1000
    # agent_model comes from pyproject.toml [tool.zorkburr] when use_local_models=true
    assert config.agent_model == "qwen/qwen3-14b"
    assert config.enable_critic is True
    assert config.critic_rejection_threshold == 0.3
    assert config.game_file == "roms/zork1.z5"


def test_config_retry_defaults():
    config = GameConfig()
    assert config.retry_max_retries == 3
    assert config.retry_initial_delay == 1.0


def test_config_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    config = GameConfig()
    assert config.openrouter_api_key == "test-key-123"


def test_local_model_from_toml():
    config = GameConfig()
    # pyproject.toml sets use_local_models = true
    assert config.use_local_models is True
    assert config.local_model == "models/Qwen3-14B-Q5_K_M.gguf"
    assert config.local_base_url == "http://localhost:8887/v1"


def test_use_local_models_from_env(monkeypatch):
    monkeypatch.setenv("USE_LOCAL_MODELS", "true")
    config = GameConfig()
    assert config.use_local_models is True
