"""Shared test fixtures."""
import pytest
from zorkburr.game.jericho_interface import JerichoInterface

@pytest.fixture
def config():
    # Minimal config for tests that need it
    class MinConfig:
        game_file = "roms/zork1.z5"
        openrouter_api_key = "test-key"
    return MinConfig()

@pytest.fixture
def jericho():
    ji = JerichoInterface("roms/zork1.z5")
    ji.start()
    yield ji
    ji.close()
