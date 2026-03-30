# ZorkBurr Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite ZorkGPT as a Burr state machine that plays Zork I, with built-in persistence, tracking, and observability — replacing the monolithic orchestrator with explicit, observable action graphs.

**Architecture:** Two-level Burr graph. Outer episode graph manages episode lifecycle and cross-episode learning. Inner turn graph executes the core game loop: context assembly → agent action → critic evaluation → Jericho execution → state extraction → memory/map/objective updates. Each component is a Burr action with explicit state reads/writes. Jericho Z-machine provides ground-truth game state. Incremental build: minimal loop first, then layer features with test runs between each phase.

**Tech Stack:** Python 3.11+, Apache Burr 0.39+ (`burr[start]`), Jericho 3.3+, Instructor (structured LLM output via Pydantic), Pydantic 2, pytest

**Source Reference:** `/Volumes/workingfolder/ZorkGPT` — the original codebase being rewritten

---

## File Structure

```
/Volumes/workingfolder/ZorkBurr/
├── pyproject.toml                     # Dependencies, project config, game settings
├── .env                               # API keys (gitignored)
├── zorkburr/
│   ├── __init__.py
│   ├── app.py                         # Burr ApplicationBuilder — turn graph + episode graph
│   ├── config.py                      # GameConfig: Pydantic settings from pyproject.toml
│   ├── state.py                       # Initial state factory, state key constants
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── context.py                 # assemble_context: build agent/critic prompt context
│   │   ├── agent.py                   # generate_action: LLM call → proposed action
│   │   ├── critic.py                  # evaluate_action: object tree + LLM scoring
│   │   ├── execute.py                 # execute_action: send command to Jericho
│   │   ├── extract.py                 # extract_info: hybrid Jericho + LLM extraction
│   │   ├── results.py                 # record_results: update history, map, memory trigger
│   │   ├── memory.py                  # Memory synthesis + recording (LLM)
│   │   ├── objectives.py              # Objective discovery, completion checking (LLM)
│   │   ├── knowledge.py               # Periodic knowledge synthesis (LLM)
│   │   ├── progress.py                # Stuck detection, score tracking
│   │   └── episode.py                 # Episode init/finalize actions
│   ├── game/
│   │   ├── __init__.py
│   │   ├── jericho_interface.py        # Clean Jericho wrapper (rewritten)
│   │   └── map_graph.py               # Room/connection graph with confidence (rewritten)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                  # Instructor client factory (OpenRouter + local LLM)
│   │   ├── models.py                  # Pydantic response models (Agent, Critic, Extractor)
│   │   └── prompts.py                 # Prompt file loader
│   └── utils.py                       # Token estimation, text cleaning
├── prompts/
│   ├── agent.md                       # Agent system prompt (from ZorkGPT)
│   ├── critic.md                      # Critic system prompt (from ZorkGPT)
│   └── extractor.md                   # Extractor system prompt (from ZorkGPT)
├── roms/
│   └── zork1.z5                       # Zork I ROM (copied from ZorkGPT)
├── data/                              # Runtime data (persisted state, maps, memories)
│   └── .gitkeep
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures: jericho, config, mock LLM
│   ├── test_config.py
│   ├── test_jericho.py
│   ├── test_llm_client.py
│   ├── test_state.py
│   ├── test_utils.py
│   ├── test_map_graph.py
│   ├── test_actions/
│   │   ├── __init__.py
│   │   ├── test_execute.py
│   │   ├── test_context.py
│   │   ├── test_agent.py
│   │   ├── test_critic.py
│   │   ├── test_extract.py
│   │   ├── test_results.py
│   │   ├── test_memory.py
│   │   ├── test_objectives.py
│   │   └── test_knowledge.py
│   └── test_app.py                    # Integration: full turn graph tests
└── docs/
    └── superpowers/
        └── plans/
            └── 2026-03-30-zorkburr-rewrite.md  # This file
```

---

## Phase 1: Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `zorkburr/__init__.py`
- Create: `zorkburr/actions/__init__.py`
- Create: `zorkburr/game/__init__.py`
- Create: `zorkburr/llm/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_actions/__init__.py`
- Create: `.env`
- Create: `.gitignore`
- Create: `data/.gitkeep`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "zorkburr"
version = "0.1.0"
description = "Zork I AI player built on Apache Burr"
requires-python = ">=3.11"
dependencies = [
    "burr[start]>=0.39.0",
    "jericho>=3.3.0",
    "instructor>=1.7.0",
    "openai>=1.79.0",
    "pydantic>=2.11.0",
    "pydantic-settings>=2.11.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.zorkburr]
# Game settings
max_turns_per_episode = 1000
turn_delay_seconds = 0.0

# LLM models (OpenRouter model IDs)
agent_model = "anthropic/claude-sonnet-4-20250514"
critic_model = "anthropic/claude-sonnet-4-20250514"
extractor_model = "anthropic/claude-haiku-4-5-20251001"
analysis_model = "anthropic/claude-sonnet-4-20250514"
memory_model = "anthropic/claude-haiku-4-5-20251001"

# LLM sampling
default_temperature = 1.0
default_max_tokens = 4096

# Critic
enable_critic = true
critic_rejection_threshold = 0.3
max_rejections_per_turn = 3

# Periodic update intervals (turns)
objective_update_interval = 10
knowledge_update_interval = 50

# Progress detection
max_turns_stuck = 40
stuck_check_interval = 10

# File paths
game_file = "roms/zork1.z5"
memory_file = "data/memories.md"
knowledge_file = "data/knowledge.md"
map_file = "data/map.json"

[tool.zorkburr.retry]
max_retries = 3
initial_delay = 1.0
max_delay = 30.0
```

- [ ] **Step 2: Create package structure**

Create all `__init__.py` files (empty), `.env`, `.gitignore`, and `data/.gitkeep`:

`.env`:
```
OPENROUTER_API_KEY=your-key-here
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
data/*.json
data/*.md
!data/.gitkeep
*.egg-info/
dist/
.burr/
```

`zorkburr/__init__.py`:
```python
"""ZorkBurr: Zork I AI player built on Apache Burr."""
```

All other `__init__.py` files are empty.

- [ ] **Step 3: Copy ROM and prompt files**

```bash
cp /Volumes/workingfolder/ZorkGPT/jericho-game-suite/zork1.z5 /Volumes/workingfolder/ZorkBurr/roms/zork1.z5
cp /Volumes/workingfolder/ZorkGPT/agent.md /Volumes/workingfolder/ZorkBurr/prompts/agent.md
cp /Volumes/workingfolder/ZorkGPT/critic.md /Volumes/workingfolder/ZorkBurr/prompts/critic.md
cp /Volumes/workingfolder/ZorkGPT/extractor.md /Volumes/workingfolder/ZorkBurr/prompts/extractor.md
```

- [ ] **Step 4: Install dependencies and verify**

```bash
cd /Volumes/workingfolder/ZorkBurr && pip install -e ".[dev]"
```

Expected: Installs successfully. Verify:
```bash
python -c "import burr; import jericho; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Initialize git and commit**

```bash
cd /Volumes/workingfolder/ZorkBurr
git init
git add -A
git commit -m "feat: project scaffolding with dependencies, ROM, and prompts"
```

---

### Task 2: Configuration

**Files:**
- Create: `zorkburr/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from zorkburr.config import GameConfig


def test_load_config_from_toml():
    config = GameConfig()
    assert config.max_turns_per_episode == 1000
    assert config.agent_model == "anthropic/claude-sonnet-4-20250514"
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'zorkburr.config'`

- [ ] **Step 3: Implement GameConfig**

`zorkburr/config.py`:
```python
"""Game configuration loaded from pyproject.toml and environment."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Optional

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

    model_config = {"env_prefix": "", "extra": "ignore"}

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
        # Flatten nested retry config
        retry = toml_data.pop("retry", {})
        for k, v in retry.items():
            toml_data[f"retry_{k}"] = v
        # TOML values are defaults; kwargs override
        merged = {**toml_data, **kwargs}
        super().__init__(**merged)
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_config.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/config.py tests/test_config.py
git commit -m "feat: GameConfig with TOML + env loading"
```

---

### Task 3: LLM Client + Response Models

**Files:**
- Create: `zorkburr/llm/client.py`
- Create: `zorkburr/llm/models.py`
- Create: `zorkburr/llm/prompts.py`
- Create: `zorkburr/utils.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

`tests/test_llm_client.py`:
```python
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from zorkburr.llm.client import create_llm_client
from zorkburr.llm.models import AgentResponse, CriticResponse, ExtractorResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.config import GameConfig


def test_load_prompt():
    text = load_prompt("agent")
    assert "Zork" in text or "action" in text.lower()


def test_agent_response_model():
    r = AgentResponse(thinking="explore", action="north", new_objective="")
    assert r.action == "north"


def test_agent_response_validates():
    r = AgentResponse(thinking="", action="  LOOK  ", new_objective="find gold")
    assert r.action == "  LOOK  "  # Cleaning happens in the action, not the model


def test_critic_response_model():
    r = CriticResponse(score=0.5, justification="good action", confidence=0.8)
    assert -1.0 <= r.score <= 1.0
    assert 0.0 <= r.confidence <= 1.0


def test_critic_response_clamps_score():
    """Score outside range should fail validation."""
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        CriticResponse(score=2.0, justification="bad", confidence=0.5)


def test_extractor_response_model():
    r = ExtractorResponse(
        exits=["north", "south"],
        in_combat=False,
        is_room_description=True,
    )
    assert len(r.exits) == 2


def test_create_llm_client():
    config = GameConfig(openrouter_api_key="test-key")
    client = create_llm_client(config)
    assert client is not None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_llm_client.py -v
```
Expected: FAIL — modules not found

- [ ] **Step 3: Implement response models**

`zorkburr/llm/models.py`:
```python
"""Pydantic response models for LLM structured output via Instructor."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Agent action generation response."""
    thinking: str = Field(description="Brief reasoning about what to do next (50-200 tokens)")
    action: str = Field(description="The game command to execute (e.g., 'north', 'open mailbox')")
    new_objective: str = Field(default="", description="Optional new multi-turn objective to track")


class CriticResponse(BaseModel):
    """Critic action evaluation response."""
    score: float = Field(ge=-1.0, le=1.0, description="Action quality score from -1.0 (terrible) to 1.0 (excellent)")
    justification: str = Field(description="Why this score was given")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this evaluation")


class ExtractorResponse(BaseModel):
    """Information extraction response."""
    exits: list[str] = Field(default_factory=list, description="Available exit directions")
    in_combat: bool = Field(default=False, description="Whether combat is active")
    is_room_description: bool = Field(default=False, description="Whether the text is a full room description")


class MemorySynthesisResponse(BaseModel):
    """Memory synthesis decision."""
    should_remember: bool = Field(description="Whether this action outcome is worth remembering")
    reasoning: str = Field(description="Why or why not to remember")
    category: str = Field(default="NOTE", description="SUCCESS | FAILURE | DISCOVERY | DANGER | NOTE")
    memory_title: str = Field(default="", description="3-6 word evergreen title")
    memory_text: str = Field(default="", description="1-2 sentence actionable insight")
    persistence: str = Field(default="ephemeral", description="core | permanent | ephemeral")
    status: str = Field(default="ACTIVE", description="ACTIVE | TENTATIVE")


class ObjectiveDiscoveryResponse(BaseModel):
    """Objective discovery from gameplay analysis."""
    objectives: list[str] = Field(default_factory=list, description="Actionable objectives to pursue")
    completed: list[str] = Field(default_factory=list, description="Objectives from current list that are now complete")


class ObjectiveCompletionResponse(BaseModel):
    """Objective completion check."""
    completed_objectives: list[str] = Field(default_factory=list, description="Exact text of completed objectives")
```

- [ ] **Step 4: Implement prompts.py**

`zorkburr/llm/prompts.py`:
```python
"""Prompt file loading."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt .md file by name (e.g., 'agent' → prompts/agent.md)."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()
```

- [ ] **Step 5: Implement client.py with Instructor**

`zorkburr/llm/client.py`:
```python
"""LLM client factory using Instructor for structured output."""

from __future__ import annotations

import logging

import instructor

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)


def create_llm_client(config: GameConfig) -> instructor.Instructor:
    """Create an Instructor client for OpenRouter.

    Usage:
        client = create_llm_client(config)
        response = client.create(
            model=config.agent_model,
            response_model=AgentResponse,
            messages=[...],
            max_retries=3,
        )
        # response is a validated Pydantic object
    """
    return instructor.from_provider(
        f"openrouter/{config.agent_model}",
        base_url=config.openrouter_base_url,
        api_key=config.openrouter_api_key,
    )


def create_local_client(
    base_url: str = "http://localhost:11434/v1",
    model: str = "llama3",
) -> instructor.Instructor:
    """Create an Instructor client for local LLM (Ollama, etc.).

    Uses JSON mode since most local models don't support tool calling.
    """
    return instructor.from_provider(
        f"ollama/{model}",
        base_url=base_url,
        mode=instructor.Mode.JSON,
    )
```

- [ ] **Step 6: Implement utils.py (slimmed down — no JSON parsing needed)**

`zorkburr/utils.py`:
```python
"""Shared utilities: text processing, token estimation."""

from __future__ import annotations

import re


def clean_action(raw: str) -> str:
    """Clean LLM-generated action text for Jericho."""
    text = raw.strip().lower()
    # Remove markdown fences
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    # Remove quotes
    text = text.strip("\"'`")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars per token)."""
    return len(text) // 4
```

- [ ] **Step 7: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_llm_client.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 8: Commit**

```bash
git add zorkburr/utils.py zorkburr/llm/client.py zorkburr/llm/models.py zorkburr/llm/prompts.py tests/test_llm_client.py
git commit -m "feat: Instructor client factory, Pydantic response models, prompt loader"
```

---

### Task 4: Jericho Interface

**Files:**
- Create: `zorkburr/game/jericho_interface.py`
- Create: `tests/test_jericho.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

`tests/conftest.py`:
```python
"""Shared test fixtures."""

import pytest
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface


@pytest.fixture
def config():
    return GameConfig(openrouter_api_key="test-key")


@pytest.fixture
def jericho(config):
    """Real Jericho interface for integration tests."""
    ji = JerichoInterface(config.game_file)
    ji.start()
    yield ji
    ji.close()
```

`tests/test_jericho.py`:
```python
from zorkburr.game.jericho_interface import JerichoInterface


def test_start_returns_intro(jericho):
    # Intro text already captured during fixture start
    assert jericho.last_response is not None
    assert "white house" in jericho.last_response.lower()


def test_initial_location(jericho):
    loc_id, loc_name = jericho.get_location()
    assert isinstance(loc_id, int)
    assert loc_id > 0


def test_send_command(jericho):
    response = jericho.send_command("look")
    assert "white house" in response.lower()


def test_get_score(jericho):
    score, max_score = jericho.get_score()
    assert score == 0
    assert max_score > 0


def test_get_inventory(jericho):
    items = jericho.get_inventory()
    assert isinstance(items, list)


def test_deterministic_movement(jericho):
    """Outside the white house, movement is deterministic."""
    response = jericho.send_command("north")
    loc_id, loc_name = jericho.get_location()
    # Should have moved
    assert isinstance(loc_id, int)


def test_save_restore(jericho):
    """Save state, make changes, restore."""
    saved = jericho.save_state()
    score_before, _ = jericho.get_score()
    jericho.send_command("north")
    jericho.restore_state(saved)
    score_after, _ = jericho.get_score()
    assert score_before == score_after


def test_is_game_over_normal(jericho):
    response = jericho.send_command("look")
    game_over, reason = jericho.is_game_over(response)
    assert game_over is False


def test_get_visible_objects(jericho):
    objects = jericho.get_visible_objects()
    assert isinstance(objects, list)


def test_context_manager():
    with JerichoInterface("roms/zork1.z5") as ji:
        ji.start()
        response = ji.send_command("look")
        assert len(response) > 0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_jericho.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement JerichoInterface**

`zorkburr/game/jericho_interface.py`:
```python
"""Clean wrapper around Jericho FrotzEnv for Z-machine interaction."""

from __future__ import annotations

import logging
from typing import Optional

import jericho

logger = logging.getLogger(__name__)


class JerichoInterface:
    """Provides structured access to a Z-machine game via Jericho."""

    def __init__(self, game_file: str):
        self.game_file = game_file
        self.env: Optional[jericho.FrotzEnv] = None
        self.last_response: str = ""

    def start(self) -> str:
        """Initialize the game environment. Returns intro text."""
        self.env = jericho.FrotzEnv(self.game_file)
        intro, _ = self.env.reset()
        self.last_response = intro
        # Enable verbose mode for full room descriptions
        verbose_response, _, _, _ = self.env.step("verbose")
        return intro

    def send_command(self, command: str) -> str:
        """Execute a command and return the game's text response."""
        assert self.env is not None, "Call start() first"
        response, _, _, _ = self.env.step(command)
        self.last_response = response
        return response

    def get_location(self) -> tuple[int, str]:
        """Return (location_id, location_name) from the Z-machine."""
        assert self.env is not None
        player = self.env.get_player_object()
        parent = player.parent if player else None
        if parent:
            return parent.num, parent.name
        return 0, "Unknown"

    def get_score(self) -> tuple[int, int]:
        """Return (current_score, max_score)."""
        assert self.env is not None
        return self.env.get_score()

    def get_inventory(self) -> list[str]:
        """Return list of inventory item names."""
        assert self.env is not None
        player = self.env.get_player_object()
        if not player or not player.child:
            return []
        items = []
        obj = player.child
        while obj:
            items.append(obj.name)
            obj = obj.sibling
        return items

    def get_visible_objects(self) -> list[dict]:
        """Return visible objects in current location as [{name, num}]."""
        assert self.env is not None
        loc_id, _ = self.get_location()
        result = []
        world_objects = self.env.get_world_objects()
        for obj in world_objects:
            if obj.parent and obj.parent.num == loc_id and obj.name != "cretin":
                result.append({"name": obj.name, "num": obj.num})
                # Include contents of transparent/open containers
                child = obj.child
                while child:
                    result.append({"name": child.name, "num": child.num})
                    child = child.sibling
        return result

    def save_state(self) -> tuple:
        """Save current game state. Returns opaque state tuple."""
        assert self.env is not None
        return self.env.save()

    def restore_state(self, state: tuple) -> None:
        """Restore a previously saved game state."""
        assert self.env is not None
        self.env.restore(state)

    def is_game_over(self, response: str) -> tuple[bool, str]:
        """Check if the game has ended. Returns (is_over, reason)."""
        assert self.env is not None
        if self.env.game_over():
            if self.env.victory():
                return True, "victory"
            return True, "death"
        return False, ""

    def close(self) -> None:
        """Clean up the game environment."""
        if self.env is not None:
            self.env.close()
            self.env = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_jericho.py -v
```
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/game/jericho_interface.py tests/test_jericho.py tests/conftest.py
git commit -m "feat: Jericho interface with core game interaction API"
```

---

### Task 5: Burr State Schema

**Files:**
- Create: `zorkburr/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

`tests/test_state.py`:
```python
from burr.core import State

from zorkburr.state import create_initial_state, S


def test_create_initial_state():
    state = create_initial_state(episode_id="test-ep-1")
    assert state[S.EPISODE_ID] == "test-ep-1"
    assert state[S.TURN_COUNT] == 0
    assert state[S.GAME_OVER] is False
    assert state[S.ACTION_HISTORY] == []


def test_state_keys_are_strings():
    """All state key constants should be plain strings."""
    assert isinstance(S.TURN_COUNT, str)
    assert isinstance(S.GAME_RESPONSE, str)


def test_state_is_burr_compatible():
    state = create_initial_state()
    # Burr State supports .update() for immutable updates
    new_state = state.update(**{S.TURN_COUNT: 5})
    assert new_state[S.TURN_COUNT] == 5
    assert state[S.TURN_COUNT] == 0  # Original unchanged


def test_state_append():
    state = create_initial_state()
    new_state = state.append(**{S.ACTION_HISTORY: {"action": "look", "turn": 1}})
    assert len(new_state[S.ACTION_HISTORY]) == 1
    assert state[S.ACTION_HISTORY] == []  # Original unchanged
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_state.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement state.py**

`zorkburr/state.py`:
```python
"""Burr state schema: key constants and initial state factory."""

from __future__ import annotations

import uuid

from burr.core import State


class S:
    """State key constants. Use these instead of raw strings."""

    # Episode
    EPISODE_ID = "episode_id"
    TURN_COUNT = "turn_count"

    # Game state (from Jericho — ground truth)
    GAME_RESPONSE = "game_response"
    LOCATION_ID = "location_id"
    LOCATION_NAME = "location_name"
    INVENTORY = "inventory"
    SCORE = "score"
    MAX_SCORE = "max_score"
    GAME_OVER = "game_over"
    GAME_OVER_REASON = "game_over_reason"

    # Agent
    FORMATTED_CONTEXT = "formatted_context"
    PROPOSED_ACTION = "proposed_action"
    AGENT_REASONING = "agent_reasoning"
    NEW_OBJECTIVE = "new_objective"

    # Critic
    ACTION_TO_TAKE = "action_to_take"
    CRITIC_SCORE = "critic_score"
    CRITIC_JUSTIFICATION = "critic_justification"
    CRITIC_CONFIDENCE = "critic_confidence"
    REJECTION_COUNT = "rejection_count"
    WAS_OVERRIDDEN = "was_overridden"

    # History
    ACTION_HISTORY = "action_history"
    REASONING_HISTORY = "reasoning_history"

    # Extraction
    EXITS = "exits"
    IN_COMBAT = "in_combat"
    IS_ROOM_DESCRIPTION = "is_room_description"
    VISIBLE_OBJECTS = "visible_objects"

    # Memory
    MEMORIES_BY_LOCATION = "memories_by_location"

    # Map
    MAP_DATA = "map_data"
    VISITED_LOCATIONS = "visited_locations"

    # Objectives
    DISCOVERED_OBJECTIVES = "discovered_objectives"
    COMPLETED_OBJECTIVES = "completed_objectives"

    # Knowledge
    KNOWLEDGE_BASE = "knowledge_base"

    # Progress
    TURNS_SINCE_PROGRESS = "turns_since_progress"
    LAST_SCORE_CHANGE_TURN = "last_score_change_turn"

    # Pre-action snapshots (for memory/map recording)
    PRE_LOCATION_ID = "pre_location_id"
    PRE_LOCATION_NAME = "pre_location_name"
    PRE_SCORE = "pre_score"
    PRE_INVENTORY = "pre_inventory"


def create_initial_state(episode_id: str | None = None) -> State:
    """Create the initial Burr state for a new episode."""
    return State(
        {
            S.EPISODE_ID: episode_id or str(uuid.uuid4())[:8],
            S.TURN_COUNT: 0,
            S.GAME_RESPONSE: "",
            S.LOCATION_ID: 0,
            S.LOCATION_NAME: "",
            S.INVENTORY: [],
            S.SCORE: 0,
            S.MAX_SCORE: 0,
            S.GAME_OVER: False,
            S.GAME_OVER_REASON: "",
            S.FORMATTED_CONTEXT: "",
            S.PROPOSED_ACTION: "",
            S.AGENT_REASONING: "",
            S.NEW_OBJECTIVE: "",
            S.ACTION_TO_TAKE: "",
            S.CRITIC_SCORE: 0.0,
            S.CRITIC_JUSTIFICATION: "",
            S.CRITIC_CONFIDENCE: 0.0,
            S.REJECTION_COUNT: 0,
            S.WAS_OVERRIDDEN: False,
            S.ACTION_HISTORY: [],
            S.REASONING_HISTORY: [],
            S.EXITS: [],
            S.IN_COMBAT: False,
            S.IS_ROOM_DESCRIPTION: False,
            S.VISIBLE_OBJECTS: [],
            S.MEMORIES_BY_LOCATION: {},
            S.MAP_DATA: {},
            S.VISITED_LOCATIONS: [],
            S.DISCOVERED_OBJECTIVES: [],
            S.COMPLETED_OBJECTIVES: [],
            S.KNOWLEDGE_BASE: "",
            S.TURNS_SINCE_PROGRESS: 0,
            S.LAST_SCORE_CHANGE_TURN: 0,
            S.PRE_LOCATION_ID: 0,
            S.PRE_LOCATION_NAME: "",
            S.PRE_SCORE: 0,
            S.PRE_INVENTORY: [],
        }
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_state.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/state.py tests/test_state.py
git commit -m "feat: Burr state schema with key constants and initial state factory"
```

---

## Phase 2: Minimal Turn Loop

Goal: Agent generates actions from raw game text, executes them via Jericho. No critic, no extraction, no memory. Just play.

### Task 6: Execute Action

**Files:**
- Create: `zorkburr/actions/execute.py`
- Create: `tests/test_actions/test_execute.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_execute.py`:
```python
from burr.core import State

from zorkburr.actions.execute import execute_action
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S


def test_execute_look(jericho):
    state = State(
        {
            S.ACTION_TO_TAKE: "look",
            S.TURN_COUNT: 1,
            S.SCORE: 0,
            S.LOCATION_ID: 0,
            S.LOCATION_NAME: "",
            S.INVENTORY: [],
            S.ACTION_HISTORY: [],
            S.GAME_OVER: False,
        }
    )
    result, new_state = execute_action.run(
        state, jericho=jericho
    )
    assert "white house" in new_state[S.GAME_RESPONSE].lower()
    assert new_state[S.LOCATION_ID] > 0
    assert isinstance(new_state[S.INVENTORY], list)
    assert new_state[S.GAME_OVER] is False


def test_execute_captures_pre_state(jericho):
    state = State(
        {
            S.ACTION_TO_TAKE: "look",
            S.TURN_COUNT: 1,
            S.SCORE: 0,
            S.LOCATION_ID: 42,
            S.LOCATION_NAME: "Test Room",
            S.INVENTORY: ["lamp"],
            S.ACTION_HISTORY: [],
            S.GAME_OVER: False,
        }
    )
    _, new_state = execute_action.run(state, jericho=jericho)
    # Pre-action snapshots should capture BEFORE state
    assert new_state[S.PRE_LOCATION_ID] == 42
    assert new_state[S.PRE_LOCATION_NAME] == "Test Room"
    assert new_state[S.PRE_INVENTORY] == ["lamp"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_execute.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement execute action**

`zorkburr/actions/execute.py`:
```python
"""Execute action: send command to Jericho, capture game state."""

from __future__ import annotations

import logging

from burr.core import action, State

from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S

logger = logging.getLogger(__name__)


@action(
    reads=[
        S.ACTION_TO_TAKE,
        S.TURN_COUNT,
        S.SCORE,
        S.LOCATION_ID,
        S.LOCATION_NAME,
        S.INVENTORY,
        S.ACTION_HISTORY,
    ],
    writes=[
        S.GAME_RESPONSE,
        S.SCORE,
        S.MAX_SCORE,
        S.LOCATION_ID,
        S.LOCATION_NAME,
        S.INVENTORY,
        S.GAME_OVER,
        S.GAME_OVER_REASON,
        S.PRE_LOCATION_ID,
        S.PRE_LOCATION_NAME,
        S.PRE_SCORE,
        S.PRE_INVENTORY,
        S.ACTION_HISTORY,
        S.TURN_COUNT,
    ],
)
def execute_action(state: State, jericho: JerichoInterface) -> tuple[dict, State]:
    """Send the chosen action to Jericho and capture the resulting game state."""
    command = state[S.ACTION_TO_TAKE]
    turn = state[S.TURN_COUNT]

    # Snapshot pre-action state (at SOURCE location for memory)
    pre_loc_id = state[S.LOCATION_ID]
    pre_loc_name = state[S.LOCATION_NAME]
    pre_score = state[S.SCORE]
    pre_inventory = list(state[S.INVENTORY])

    # Execute command
    response = jericho.send_command(command)

    # Capture post-action state from Z-machine (ground truth)
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    game_over, reason = jericho.is_game_over(response)

    # Build action history entry
    history_entry = {
        "turn": turn + 1,
        "action": command,
        "response": response[:500],  # Truncate for state size
        "location_id": pre_loc_id,
        "location_name": pre_loc_name,
        "score_before": pre_score,
        "score_after": score,
    }

    result = {"response": response, "score_delta": score - pre_score}

    new_state = (
        state
        .update(
            **{
                S.GAME_RESPONSE: response,
                S.SCORE: score,
                S.MAX_SCORE: max_score,
                S.LOCATION_ID: loc_id,
                S.LOCATION_NAME: loc_name,
                S.INVENTORY: inventory,
                S.GAME_OVER: game_over,
                S.GAME_OVER_REASON: reason,
                S.PRE_LOCATION_ID: pre_loc_id,
                S.PRE_LOCATION_NAME: pre_loc_name,
                S.PRE_SCORE: pre_score,
                S.PRE_INVENTORY: pre_inventory,
                S.TURN_COUNT: turn + 1,
            }
        )
        .append(**{S.ACTION_HISTORY: history_entry})
    )

    return result, new_state
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_execute.py -v
```
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/execute.py tests/test_actions/test_execute.py
git commit -m "feat: execute_action — Jericho command execution with state capture"
```

---

### Task 7: Context Assembly (Simple)

**Files:**
- Create: `zorkburr/actions/context.py`
- Create: `tests/test_actions/test_context.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_context.py`:
```python
from burr.core import State

from zorkburr.actions.context import assemble_context
from zorkburr.state import S


def test_assemble_context_basic():
    state = State(
        {
            S.GAME_RESPONSE: "You are in a forest.",
            S.LOCATION_NAME: "Forest",
            S.INVENTORY: ["lamp", "sword"],
            S.SCORE: 10,
            S.ACTION_HISTORY: [],
            S.EXITS: [],
            S.DISCOVERED_OBJECTIVES: [],
            S.KNOWLEDGE_BASE: "",
            S.MEMORIES_BY_LOCATION: {},
            S.LOCATION_ID: 42,
            S.MAP_DATA: {},
            S.IN_COMBAT: False,
            S.TURN_COUNT: 5,
        }
    )
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "forest" in ctx.lower() or "Forest" in ctx
    assert "lamp" in ctx
    assert "Score: 10" in ctx


def test_assemble_context_with_history():
    state = State(
        {
            S.GAME_RESPONSE: "You are in a kitchen.",
            S.LOCATION_NAME: "Kitchen",
            S.INVENTORY: [],
            S.SCORE: 5,
            S.ACTION_HISTORY: [
                {"turn": 1, "action": "look", "response": "You see a house.", "location_name": "House"},
                {"turn": 2, "action": "north", "response": "You are in a kitchen.", "location_name": "Kitchen"},
            ],
            S.EXITS: ["north", "south"],
            S.DISCOVERED_OBJECTIVES: ["Find the treasure"],
            S.KNOWLEDGE_BASE: "",
            S.MEMORIES_BY_LOCATION: {},
            S.LOCATION_ID: 10,
            S.MAP_DATA: {},
            S.IN_COMBAT: False,
            S.TURN_COUNT: 3,
        }
    )
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "look" in ctx
    assert "north" in ctx.lower()
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_context.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement assemble_context**

`zorkburr/actions/context.py`:
```python
"""Context assembly: build formatted prompt context for agent/critic."""

from __future__ import annotations

from burr.core import action, State

from zorkburr.state import S


@action(
    reads=[
        S.GAME_RESPONSE,
        S.LOCATION_NAME,
        S.LOCATION_ID,
        S.INVENTORY,
        S.SCORE,
        S.ACTION_HISTORY,
        S.EXITS,
        S.DISCOVERED_OBJECTIVES,
        S.KNOWLEDGE_BASE,
        S.MEMORIES_BY_LOCATION,
        S.MAP_DATA,
        S.IN_COMBAT,
        S.TURN_COUNT,
    ],
    writes=[S.FORMATTED_CONTEXT],
)
def assemble_context(state: State) -> tuple[dict, State]:
    """Build the formatted context string for the agent prompt."""
    sections = []

    # Current game state
    sections.append(f"**Current Game State:**\n{state[S.GAME_RESPONSE]}")

    # Location and score
    sections.append(
        f"**Location:** {state[S.LOCATION_NAME]} (ID: {state[S.LOCATION_ID]})\n"
        f"**Score:** {state[S.SCORE]}\n"
        f"**Turn:** {state[S.TURN_COUNT]}"
    )

    # Inventory
    inv = state[S.INVENTORY]
    inv_str = ", ".join(inv) if inv else "(empty)"
    sections.append(f"**Inventory:** {inv_str}")

    # Available exits
    exits = state[S.EXITS]
    if exits:
        sections.append(f"**Available Exits:** {', '.join(exits)}")

    # Combat state
    if state[S.IN_COMBAT]:
        sections.append("**⚠ COMBAT ACTIVE — prioritize combat actions**")

    # Recent action history (last 5)
    history = state[S.ACTION_HISTORY]
    if history:
        recent = history[-5:]
        history_lines = []
        for entry in recent:
            history_lines.append(
                f"  Turn {entry['turn']}: {entry['action']} → "
                f"{entry['response'][:200]}"
            )
        sections.append("**Recent Actions:**\n" + "\n".join(history_lines))

    # Location memories
    loc_id = state[S.LOCATION_ID]
    memories = state[S.MEMORIES_BY_LOCATION]
    if str(loc_id) in memories or loc_id in memories:
        loc_key = str(loc_id) if str(loc_id) in memories else loc_id
        loc_mems = memories[loc_key]
        if loc_mems:
            mem_lines = [f"  - {m.get('text', m)}" for m in loc_mems[:10]]
            sections.append(
                "**Memories for this location:**\n" + "\n".join(mem_lines)
            )

    # Objectives
    objectives = state[S.DISCOVERED_OBJECTIVES]
    if objectives:
        obj_lines = [f"  - {o}" for o in objectives]
        sections.append("**Active Objectives:**\n" + "\n".join(obj_lines))

    # Knowledge base (if present)
    knowledge = state[S.KNOWLEDGE_BASE]
    if knowledge:
        sections.append(f"**Strategic Knowledge:**\n{knowledge[:2000]}")

    formatted = "\n\n".join(sections)
    return {"context_length": len(formatted)}, state.update(
        **{S.FORMATTED_CONTEXT: formatted}
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_context.py -v
```
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/context.py tests/test_actions/test_context.py
git commit -m "feat: assemble_context action — build agent prompt context"
```

---

### Task 8: Agent Action

**Files:**
- Create: `zorkburr/actions/agent.py`
- Create: `tests/test_actions/test_agent.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_agent.py`:
```python
from unittest.mock import MagicMock

from burr.core import State

from zorkburr.actions.agent import generate_action
from zorkburr.llm.models import AgentResponse
from zorkburr.utils import clean_action
from zorkburr.state import S


def test_clean_action():
    assert clean_action("  NORTH  ") == "north"
    assert clean_action('```\nnorth\n```') == "north"
    assert clean_action('"go north"') == "go north"


def test_generate_action_returns_validated_response():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="I should look around", action="look", new_objective=""
    )

    state = State(
        {
            S.FORMATTED_CONTEXT: "You are at the white house.",
            S.REJECTION_COUNT: 0,
            S.CRITIC_JUSTIFICATION: "",
            S.KNOWLEDGE_BASE: "",
            S.TURN_COUNT: 1,
        }
    )
    result, new_state = generate_action.run(
        state, client=mock_client, config=MagicMock(agent_model="test", default_temperature=1.0, default_max_tokens=4096)
    )
    assert new_state[S.PROPOSED_ACTION] == "look"
    assert "look around" in new_state[S.AGENT_REASONING]


def test_generate_action_retry_includes_feedback():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="trying something else", action="open mailbox", new_objective=""
    )

    state = State(
        {
            S.FORMATTED_CONTEXT: "You are at the white house.",
            S.REJECTION_COUNT: 1,
            S.CRITIC_JUSTIFICATION: "Action 'north' was repetitive.",
            S.KNOWLEDGE_BASE: "",
            S.TURN_COUNT: 2,
        }
    )
    result, new_state = generate_action.run(
        state, client=mock_client, config=MagicMock(agent_model="test", default_temperature=1.0, default_max_tokens=4096)
    )
    assert new_state[S.PROPOSED_ACTION] == "open mailbox"
    # Should have passed rejection feedback to LLM
    call_args = mock_client.create.call_args
    messages = call_args.kwargs.get("messages")
    user_msg = messages[-1]["content"]
    assert "rejected" in user_msg.lower() or "repetitive" in user_msg.lower()


def test_generate_action_fallback_on_error():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("LLM error")

    state = State(
        {
            S.FORMATTED_CONTEXT: "You are somewhere.",
            S.REJECTION_COUNT: 0,
            S.CRITIC_JUSTIFICATION: "",
            S.KNOWLEDGE_BASE: "",
            S.TURN_COUNT: 1,
        }
    )
    result, new_state = generate_action.run(
        state, client=mock_client, config=MagicMock(agent_model="test", default_temperature=1.0, default_max_tokens=4096)
    )
    assert new_state[S.PROPOSED_ACTION] == "look"  # Safe fallback
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_agent.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement generate_action**

`zorkburr/actions/agent.py`:
```python
"""Agent action: generate next game action via LLM with structured output."""

from __future__ import annotations

import logging

import instructor

from burr.core import action, State

from zorkburr.config import GameConfig
from zorkburr.llm.models import AgentResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S
from zorkburr.utils import clean_action

logger = logging.getLogger(__name__)

_system_prompt: str | None = None


def _get_system_prompt(knowledge_base: str = "") -> str:
    """Load and optionally enhance the agent system prompt."""
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_prompt("agent")

    prompt = _system_prompt
    if knowledge_base:
        marker = "**Output Format"
        if marker in prompt:
            guide = (
                "\n\n**STRATEGIC GUIDE FROM PREVIOUS EPISODES:**\n"
                f"{knowledge_base}\n"
                "**END OF STRATEGIC GUIDE**\n\n"
            )
            prompt = prompt.replace(marker, guide + marker)
    return prompt


@action(
    reads=[
        S.FORMATTED_CONTEXT,
        S.REJECTION_COUNT,
        S.CRITIC_JUSTIFICATION,
        S.KNOWLEDGE_BASE,
        S.TURN_COUNT,
    ],
    writes=[
        S.PROPOSED_ACTION,
        S.AGENT_REASONING,
        S.NEW_OBJECTIVE,
        S.ACTION_TO_TAKE,  # Default to proposed; critic may override
    ],
)
def generate_action(
    state: State, client: instructor.Instructor, config: GameConfig
) -> tuple[dict, State]:
    """Ask the agent LLM for the next action. Returns validated AgentResponse."""
    system = _get_system_prompt(state[S.KNOWLEDGE_BASE])

    # Build user message
    user_content = state[S.FORMATTED_CONTEXT]

    # If this is a retry after rejection, include feedback
    if state[S.REJECTION_COUNT] > 0:
        feedback = state[S.CRITIC_JUSTIFICATION]
        user_content += (
            f"\n\n**Your previous action was rejected (attempt "
            f"{state[S.REJECTION_COUNT]}).**\n"
            f"Reason: {feedback}\n"
            f"Please propose a DIFFERENT action."
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    try:
        response: AgentResponse = client.create(
            model=config.agent_model,
            response_model=AgentResponse,
            messages=messages,
            temperature=config.default_temperature,
            max_tokens=config.default_max_tokens,
            max_retries=3,
        )

        action_text = clean_action(response.action)
        reasoning = response.thinking
        new_objective = response.new_objective

    except Exception as e:
        logger.error(f"Agent LLM call failed: {e}")
        action_text = "look"
        reasoning = f"LLM error: {e}"
        new_objective = ""

    new_state = state.update(
        **{
            S.PROPOSED_ACTION: action_text,
            S.AGENT_REASONING: reasoning,
            S.NEW_OBJECTIVE: new_objective,
            S.ACTION_TO_TAKE: action_text,  # Default; critic may change this
        }
    )

    return {"action": action_text}, new_state
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_agent.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/agent.py tests/test_actions/test_agent.py
git commit -m "feat: generate_action — Instructor-based agent with validated Pydantic output"
```

---

### Task 9: Turn Graph (Minimal)

**Files:**
- Create: `zorkburr/app.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing integration test**

`tests/test_app.py`:
```python
"""Integration tests for the Burr turn graph."""

from unittest.mock import MagicMock

from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S


def test_minimal_turn_graph(jericho, config):
    """Run 3 turns with a mock LLM agent."""
    from zorkburr.llm.models import AgentResponse
    mock_client = MagicMock()
    mock_client.create.side_effect = [
        AgentResponse(thinking="explore", action="look", new_objective=""),
        AgentResponse(thinking="check mailbox", action="open mailbox", new_objective=""),
        AgentResponse(thinking="look again", action="look", new_objective=""),
    ]

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-run",
    )

    # Run 3 turns
    for _ in range(3):
        action_obj, result, state = app.step()
        if state[S.GAME_OVER]:
            break

    assert state[S.TURN_COUNT] == 3
    assert len(state[S.ACTION_HISTORY]) == 3
    assert state[S.GAME_OVER] is False


def test_turn_graph_halts_on_game_over(config):
    """Graph should halt when game_over is True."""
    from zorkburr.llm.models import AgentResponse
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(thinking="die", action="jump", new_objective="")

    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.send_command.return_value = "You have died."
    mock_jericho.get_location.return_value = (1, "Cliff")
    mock_jericho.get_score.return_value = (0, 350)
    mock_jericho.get_inventory.return_value = []
    mock_jericho.is_game_over.return_value = (True, "death")

    app = build_turn_app(
        config=config,
        jericho=mock_jericho,
        client=mock_client,
        episode_id="test-death",
    )

    # Should halt after first turn due to game_over
    last_action, last_result, final_state = app.run(
        halt_after=["execute_action"],
        halt_before=[],
        inputs={},
    )
    assert final_state[S.GAME_OVER] is True
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_app.py -v
```
Expected: FAIL — `build_turn_app` not found

- [ ] **Step 3: Implement build_turn_app**

`zorkburr/app.py`:
```python
"""Burr application builders for ZorkBurr turn and episode graphs."""

from __future__ import annotations

from burr.core import ApplicationBuilder, default, when, expr

from zorkburr.actions.agent import generate_action
from zorkburr.actions.context import assemble_context
from zorkburr.actions.execute import execute_action
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
import instructor
from zorkburr.state import S, create_initial_state


def build_turn_app(
    config: GameConfig,
    jericho: JerichoInterface,
    client: instructor.Instructor,
    episode_id: str | None = None,
    tracker: str | None = "local",
):
    """Build the minimal turn graph: context → agent → execute → loop.

    Returns a Burr Application ready to step/run.
    """
    initial_state = create_initial_state(episode_id=episode_id)

    # Seed initial game state from Jericho
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    initial_state = initial_state.update(
        **{
            S.GAME_RESPONSE: jericho.last_response,
            S.LOCATION_ID: loc_id,
            S.LOCATION_NAME: loc_name,
            S.SCORE: score,
            S.MAX_SCORE: max_score,
            S.INVENTORY: inventory,
        }
    )

    # Bind dependencies to actions
    bound_agent = generate_action.bind(client=client, config=config)
    bound_execute = execute_action.bind(jericho=jericho)

    builder = (
        ApplicationBuilder()
        .with_actions(
            assemble_context=assemble_context,
            generate_action=bound_agent,
            execute_action=bound_execute,
        )
        .with_transitions(
            ("assemble_context", "generate_action"),
            ("generate_action", "execute_action"),
            ("execute_action", "assemble_context", when(**{S.GAME_OVER: False})),
            ("execute_action", "turn_complete", when(**{S.GAME_OVER: True})),
        )
        .with_entrypoint("assemble_context")
        .with_state(initial_state)
    )

    if tracker:
        builder = builder.with_tracker(tracker)

    return builder.build()
```

**Note:** The `turn_complete` action doesn't exist yet — we need a terminal no-op action. Add it:

Update `zorkburr/app.py` to include a terminal action:

```python
from burr.core import action, State

@action(reads=[], writes=[])
def turn_complete(state: State) -> tuple[dict, State]:
    """Terminal action — game is over."""
    return {"status": "complete"}, state
```

Add `turn_complete` to the `.with_actions(...)` call.

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_app.py -v
```
Expected: Tests PASS (may need adjustments to the halt logic — the `app.run()` call needs `halt_after=["turn_complete"]` for the game-over test, and `app.step()` for the 3-turn test).

Debug and fix any issues. Common fixes:
- `app.step()` returns the action that was executed, so stepping through `assemble_context → generate_action → execute_action` is 3 steps per turn, not 1
- Adjust the loop: `for _ in range(9):` for 3 turns × 3 actions

- [ ] **Step 5: Commit**

```bash
git add zorkburr/app.py tests/test_app.py
git commit -m "feat: minimal turn graph — context → agent → execute loop"
```

---

### Task 10: Smoke Test — Play 5 Turns

**Files:**
- Create: `scripts/smoke_test.py`

- [ ] **Step 1: Create smoke test script**

`scripts/smoke_test.py`:
```python
"""Smoke test: play 5 turns of Zork with the minimal turn graph."""

import logging
import sys

from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
import instructor
from zorkburr.state import S

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

MAX_TURNS = 5


def main():
    config = GameConfig()
    if not config.openrouter_api_key:
        print("ERROR: Set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    from zorkburr.llm.client import create_llm_client
    client = create_llm_client(config)

    with JerichoInterface(config.game_file) as jericho:
        jericho.start()
        print(f"\n{'='*60}")
        print("GAME START")
        print(f"{'='*60}")
        print(jericho.last_response)
        print(f"{'='*60}\n")

        app = build_turn_app(
            config=config,
            jericho=jericho,
            client=client,
            episode_id="smoke-test",
            tracker="local",
        )

        turns_completed = 0
        while turns_completed < MAX_TURNS:
            action_obj, result, state = app.step()

            # Print when we execute an action
            if action_obj.name == "execute_action":
                turns_completed += 1
                print(f"\n--- Turn {state[S.TURN_COUNT]} ---")
                print(f"Action: {state[S.ACTION_TO_TAKE]}")
                print(f"Response: {state[S.GAME_RESPONSE][:300]}")
                print(f"Score: {state[S.SCORE]} | Location: {state[S.LOCATION_NAME]}")

            if state[S.GAME_OVER]:
                print(f"\nGAME OVER: {state[S.GAME_OVER_REASON]}")
                break

        print(f"\n{'='*60}")
        print(f"Smoke test complete. Turns: {turns_completed}, Score: {state[S.SCORE]}")
        print(f"Burr tracking UI: run 'burr' to view at http://localhost:7241")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the smoke test**

```bash
cd /Volumes/workingfolder/ZorkBurr && python scripts/smoke_test.py
```

Expected: The agent plays 5 turns of Zork. You should see:
- Game intro text (white house)
- 5 turns of actions and responses
- Score and location updates
- No crashes

If the agent gets stuck with "look" repeatedly, that's OK for the minimal loop — the critic (Phase 3) will fix that.

- [ ] **Step 3: Verify Burr tracking**

```bash
cd /Volumes/workingfolder/ZorkBurr && burr
```

Open http://localhost:7241 in browser. You should see the "smoke-test" application with step-by-step execution history.

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke_test.py
git commit -m "feat: smoke test script — play 5 turns with minimal loop"
```

---

## Phase 3: Critic Evaluation

Goal: Add action validation — fast object-tree check + LLM scoring with rejection loop.

### Task 11: Object Tree Validation

**Files:**
- Create: `zorkburr/actions/critic.py`
- Create: `tests/test_actions/test_critic.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_critic.py`:
```python
from unittest.mock import MagicMock

from zorkburr.actions.critic import validate_against_object_tree
from zorkburr.game.jericho_interface import JerichoInterface


def test_validate_take_visible_object():
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = [
        {"name": "sword", "num": 10},
        {"name": "lamp", "num": 11},
    ]
    mock_jericho.get_inventory.return_value = []

    valid, reason = validate_against_object_tree("take sword", mock_jericho)
    assert valid is True


def test_validate_take_invisible_object():
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = [
        {"name": "lamp", "num": 11},
    ]
    mock_jericho.get_inventory.return_value = []

    valid, reason = validate_against_object_tree("take sword", mock_jericho)
    assert valid is False
    assert "sword" in reason.lower()


def test_validate_single_word_passes():
    mock_jericho = MagicMock(spec=JerichoInterface)
    valid, reason = validate_against_object_tree("look", mock_jericho)
    assert valid is True


def test_validate_movement_passes():
    mock_jericho = MagicMock(spec=JerichoInterface)
    valid, reason = validate_against_object_tree("go north", mock_jericho)
    assert valid is True
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_critic.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement object tree validation**

`zorkburr/actions/critic.py`:
```python
"""Critic action: object tree validation + LLM evaluation."""

from __future__ import annotations

import logging
import re

from burr.core import action, State

import instructor

from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.models import CriticResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

# Verbs that interact with objects (require object to be visible/in inventory)
_TAKE_VERBS = {"take", "get", "grab", "pick"}
_OBJECT_VERBS = {"open", "close", "read", "examine", "drop", "put", "give", "unlock", "light", "turn"}
_MOVEMENT_WORDS = {
    "north", "south", "east", "west", "up", "down",
    "n", "s", "e", "w", "ne", "nw", "se", "sw",
    "go", "walk", "run", "climb", "enter", "exit",
}


def validate_against_object_tree(
    action_text: str, jericho: JerichoInterface
) -> tuple[bool, str]:
    """Fast validation: check if action references objects that exist.

    Returns (is_valid, reason). Single-word and movement commands always pass.
    """
    words = action_text.lower().split()
    if len(words) <= 1:
        return True, ""

    verb = words[0]

    # Movement commands always pass
    if verb in _MOVEMENT_WORDS or any(w in _MOVEMENT_WORDS for w in words):
        return True, ""

    # For take/get verbs, check if object is visible
    if verb in _TAKE_VERBS:
        target = " ".join(words[1:])
        visible = jericho.get_visible_objects()
        visible_names = {obj["name"].lower() for obj in visible}
        # Check if any visible object name contains the target
        for name in visible_names:
            if target in name or name in target:
                return True, ""
        return False, f"'{target}' is not visible in this location"

    # For other object verbs, check visible + inventory
    if verb in _OBJECT_VERBS:
        target = " ".join(words[1:])
        # Remove prepositions
        target = re.sub(r"\b(with|on|in|to|at|from|into|under)\b", "", target).strip()
        if not target:
            return True, ""

        visible = jericho.get_visible_objects()
        visible_names = {obj["name"].lower() for obj in visible}
        inv_names = {name.lower() for name in jericho.get_inventory()}
        all_names = visible_names | inv_names

        for name in all_names:
            if target in name or name in target:
                return True, ""
        return False, f"'{target}' is not visible or in inventory"

    # Unknown verb pattern — let it through
    return True, ""
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_critic.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/critic.py tests/test_actions/test_critic.py
git commit -m "feat: object tree validation for fast action rejection"
```

---

### Task 12: Critic LLM Evaluation

**Files:**
- Modify: `zorkburr/actions/critic.py`
- Modify: `tests/test_actions/test_critic.py`

- [ ] **Step 1: Write failing test for LLM evaluation**

Add to `tests/test_actions/test_critic.py`:
```python
from burr.core import State
from zorkburr.actions.critic import evaluate_action
from zorkburr.llm.models import CriticResponse
from zorkburr.state import S


def test_evaluate_action_accepts_good_action():
    mock_client = MagicMock()
    mock_client.create.return_value = CriticResponse(score=0.8, justification="Good exploration action", confidence=0.9)
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = []
    mock_jericho.get_inventory.return_value = []
    mock_config = MagicMock(
        enable_critic=True,
        critic_model="test",
        critic_rejection_threshold=0.3,
        max_rejections_per_turn=3,
        default_temperature=1.0,
        default_max_tokens=4096,
    )

    state = State(
        {
            S.PROPOSED_ACTION: "north",
            S.GAME_RESPONSE: "You are in a forest.",
            S.ACTION_HISTORY: [],
            S.EXITS: ["north", "south"],
            S.INVENTORY: [],
            S.LOCATION_NAME: "Forest",
            S.REJECTION_COUNT: 0,
            S.IN_COMBAT: False,
        }
    )
    result, new_state = evaluate_action.run(
        state, llm=mock_client, jericho=mock_jericho, config=mock_config
    )
    assert new_state[S.CRITIC_SCORE] == 0.8
    assert new_state[S.ACTION_TO_TAKE] == "north"


def test_evaluate_action_rejects_bad_action():
    mock_client = MagicMock()
    mock_client.create.return_value = CriticResponse(score=-0.5, justification="Repeating same action", confidence=0.8)
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = []
    mock_jericho.get_inventory.return_value = []
    mock_config = MagicMock(
        enable_critic=True,
        critic_model="test",
        critic_rejection_threshold=0.3,
        max_rejections_per_turn=3,
        default_temperature=1.0,
        default_max_tokens=4096,
    )

    state = State(
        {
            S.PROPOSED_ACTION: "look",
            S.GAME_RESPONSE: "You are in a forest.",
            S.ACTION_HISTORY: [{"action": "look", "turn": 1}],
            S.EXITS: ["north"],
            S.INVENTORY: [],
            S.LOCATION_NAME: "Forest",
            S.REJECTION_COUNT: 0,
            S.IN_COMBAT: False,
        }
    )
    result, new_state = evaluate_action.run(
        state, llm=mock_client, jericho=mock_jericho, config=mock_config
    )
    assert new_state[S.CRITIC_SCORE] == -0.5
    assert new_state[S.REJECTION_COUNT] == 1  # Incremented


def test_evaluate_action_critic_disabled():
    """When critic is disabled, action always passes."""
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = []
    mock_jericho.get_inventory.return_value = []
    mock_config = MagicMock(
        enable_critic=False,
        critic_rejection_threshold=0.3,
        max_rejections_per_turn=3,
    )

    state = State(
        {
            S.PROPOSED_ACTION: "north",
            S.GAME_RESPONSE: "Forest.",
            S.ACTION_HISTORY: [],
            S.EXITS: [],
            S.INVENTORY: [],
            S.LOCATION_NAME: "Forest",
            S.REJECTION_COUNT: 0,
            S.IN_COMBAT: False,
        }
    )
    result, new_state = evaluate_action.run(
        state, llm=MagicMock(), jericho=mock_jericho, config=mock_config
    )
    assert new_state[S.CRITIC_SCORE] >= 0.3  # Passes threshold
    assert new_state[S.ACTION_TO_TAKE] == "north"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_critic.py::test_evaluate_action_accepts_good_action -v
```
Expected: FAIL — `evaluate_action` not defined

- [ ] **Step 3: Implement evaluate_action**

Add to `zorkburr/actions/critic.py`:
```python
_critic_prompt: str | None = None


def _get_critic_prompt() -> str:
    global _critic_prompt
    if _critic_prompt is None:
        _critic_prompt = load_prompt("critic")
    return _critic_prompt


def _build_critic_context(state: State) -> str:
    """Build context string for the critic evaluation."""
    sections = [
        f"**Current Game State:**\n{state[S.GAME_RESPONSE]}",
        f"**Location:** {state[S.LOCATION_NAME]}",
    ]

    exits = state[S.EXITS]
    if exits:
        sections.append(f"**Available Exits:** {', '.join(exits)}")

    inv = state[S.INVENTORY]
    if inv:
        sections.append(f"**Inventory:** {', '.join(inv)}")

    history = state[S.ACTION_HISTORY]
    if history:
        recent = history[-3:]
        lines = [f"  {e['action']} → {e.get('response', '')[:150]}" for e in recent]
        sections.append("**Recent Actions:**\n" + "\n".join(lines))

    if state[S.IN_COMBAT]:
        sections.append("**⚠ COMBAT ACTIVE**")

    return "\n\n".join(sections)


@action(
    reads=[
        S.PROPOSED_ACTION,
        S.GAME_RESPONSE,
        S.ACTION_HISTORY,
        S.EXITS,
        S.INVENTORY,
        S.LOCATION_NAME,
        S.REJECTION_COUNT,
        S.IN_COMBAT,
    ],
    writes=[
        S.CRITIC_SCORE,
        S.CRITIC_JUSTIFICATION,
        S.CRITIC_CONFIDENCE,
        S.ACTION_TO_TAKE,
        S.REJECTION_COUNT,
    ],
)
def evaluate_action(
    state: State,
    llm: instructor.Instructor,
    jericho: JerichoInterface,
    config: GameConfig,
) -> tuple[dict, State]:
    """Evaluate the proposed action using object tree + LLM critic."""
    proposed = state[S.PROPOSED_ACTION]
    threshold = config.critic_rejection_threshold

    # Step 1: Fast object tree validation
    obj_valid, obj_reason = validate_against_object_tree(proposed, jericho)
    if not obj_valid:
        return (
            {"rejected_by": "object_tree"},
            state.update(
                **{
                    S.CRITIC_SCORE: -1.0,
                    S.CRITIC_JUSTIFICATION: f"Object tree: {obj_reason}",
                    S.CRITIC_CONFIDENCE: 1.0,
                    S.ACTION_TO_TAKE: proposed,
                    S.REJECTION_COUNT: state[S.REJECTION_COUNT] + 1,
                }
            ),
        )

    # Step 2: If critic disabled, auto-accept
    if not config.enable_critic:
        return (
            {"rejected_by": None},
            state.update(
                **{
                    S.CRITIC_SCORE: 0.5,
                    S.CRITIC_JUSTIFICATION: "Critic disabled",
                    S.CRITIC_CONFIDENCE: 0.5,
                    S.ACTION_TO_TAKE: proposed,
                    S.REJECTION_COUNT: state[S.REJECTION_COUNT],
                }
            ),
        )

    # Step 3: LLM evaluation
    system = _get_critic_prompt()
    context = _build_critic_context(state)
    user_msg = (
        f"{context}\n\n"
        f"**Proposed Action:** {proposed}\n\n"
        f"Evaluate this action."
    )

    try:
        response: CriticResponse = llm.create(
            model=config.critic_model,
            response_model=CriticResponse,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=config.default_temperature,
            max_tokens=config.default_max_tokens,
            max_retries=2,
        )

        score = response.score
        justification = response.justification
        confidence = response.confidence

    except Exception as e:
        logger.error(f"Critic LLM failed: {e}")
        score, justification, confidence = 0.5, f"LLM error: {e}", 0.3

    # Determine acceptance
    accepted = score >= threshold
    rejection_count = state[S.REJECTION_COUNT]
    if not accepted:
        rejection_count += 1

    return (
        {"accepted": accepted, "score": score},
        state.update(
            **{
                S.CRITIC_SCORE: score,
                S.CRITIC_JUSTIFICATION: justification,
                S.CRITIC_CONFIDENCE: confidence,
                S.ACTION_TO_TAKE: proposed,
                S.REJECTION_COUNT: rejection_count,
            }
        ),
    )
```

- [ ] **Step 4: Run all critic tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_critic.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/critic.py tests/test_actions/test_critic.py
git commit -m "feat: evaluate_action — object tree + LLM critic with rejection counting"
```

---

### Task 13: Add Critic to Turn Graph

**Files:**
- Modify: `zorkburr/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write test for critic integration**

Add to `tests/test_app.py`:
```python
def test_turn_graph_with_critic(jericho, config):
    """Critic rejects first action, agent retries, second accepted."""
    from zorkburr.llm.models import AgentResponse, CriticResponse
    mock_client = MagicMock()
    # Call sequence: agent(1), critic(reject), agent(2), critic(accept), execute
    mock_client.create.side_effect = [
        # Agent attempt 1
        AgentResponse(thinking="try jump", action="jump", new_objective=""),
        # Critic rejects
        CriticResponse(score=-0.5, justification="jumping is pointless", confidence=0.9),
        # Agent attempt 2 (retry)
        AgentResponse(thinking="try mailbox", action="open mailbox", new_objective=""),
        # Critic accepts
        CriticResponse(score=0.7, justification="good interaction", confidence=0.8),
    ]

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=mock_client,
        episode_id="test-critic",
        tracker=None,
    )

    # Step through until execute_action fires
    steps = 0
    while steps < 20:  # Safety limit
        action_obj, result, state = app.step()
        steps += 1
        if action_obj.name == "execute_action":
            break

    assert state[S.ACTION_TO_TAKE] == "open mailbox"
```

- [ ] **Step 2: Update app.py with critic transitions**

Update `zorkburr/app.py` — replace the `build_turn_app` function:

```python
from zorkburr.actions.critic import evaluate_action


def build_turn_app(
    config: GameConfig,
    jericho: JerichoInterface,
    client: instructor.Instructor,
    episode_id: str | None = None,
    tracker: str | None = "local",
):
    """Build the turn graph with critic evaluation loop.

    Graph: assemble_context → generate_action → evaluate_action
              ↑                                    ↓ (accepted or max retries)
              │                                 execute_action
              │                                    ↓
              └────────────────────────────── (if not game_over)

    Rejection loop: evaluate_action → generate_action (if rejected & retries < max)
    """
    initial_state = create_initial_state(episode_id=episode_id)

    # Seed initial game state from Jericho
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    initial_state = initial_state.update(
        **{
            S.GAME_RESPONSE: jericho.last_response,
            S.LOCATION_ID: loc_id,
            S.LOCATION_NAME: loc_name,
            S.SCORE: score,
            S.MAX_SCORE: max_score,
            S.INVENTORY: inventory,
        }
    )

    # Bind dependencies to actions
    bound_agent = generate_action.bind(client=client, config=config)
    bound_critic = evaluate_action.bind(llm=client, jericho=jericho, config=config)
    bound_execute = execute_action.bind(jericho=jericho)

    max_rejections = config.max_rejections_per_turn
    threshold = config.critic_rejection_threshold

    builder = (
        ApplicationBuilder()
        .with_actions(
            assemble_context=assemble_context,
            generate_action=bound_agent,
            evaluate_action=bound_critic,
            execute_action=bound_execute,
            turn_complete=turn_complete,
        )
        .with_transitions(
            ("assemble_context", "generate_action"),
            ("generate_action", "evaluate_action"),
            # Accepted: score >= threshold
            ("evaluate_action", "execute_action",
             expr(f"{S.CRITIC_SCORE} >= {threshold}")),
            # Max rejections reached — force accept
            ("evaluate_action", "execute_action",
             expr(f"{S.REJECTION_COUNT} >= {max_rejections}")),
            # Rejected — retry with new action
            ("evaluate_action", "generate_action", default),
            # After execution: loop or halt
            ("execute_action", "assemble_context",
             when(**{S.GAME_OVER: False})),
            ("execute_action", "turn_complete",
             when(**{S.GAME_OVER: True})),
        )
        .with_entrypoint("assemble_context")
        .with_state(initial_state)
    )

    if tracker:
        builder = builder.with_tracker(tracker)

    return builder.build()
```

- [ ] **Step 3: Run all tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_app.py -v
```
Expected: All tests PASS

- [ ] **Step 4: Run smoke test with critic**

```bash
cd /Volumes/workingfolder/ZorkBurr && python scripts/smoke_test.py
```

Expected: Agent plays 5 turns, with critic evaluations visible in Burr tracking UI. Some actions may be rejected and retried.

- [ ] **Step 5: Commit**

```bash
git add zorkburr/app.py tests/test_app.py
git commit -m "feat: critic evaluation loop with rejection transitions in turn graph"
```

---

## Phase 4: Information Extraction

Goal: Hybrid extractor — Jericho for objects/inventory/location, LLM for exits/combat/room description.

### Task 14: Hybrid Extractor Action

**Files:**
- Create: `zorkburr/actions/extract.py`
- Create: `tests/test_actions/test_extract.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_extract.py`:
```python
from unittest.mock import MagicMock

from burr.core import State

from zorkburr.actions.extract import extract_info
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.state import S


def test_extract_exits_from_llm():
    from zorkburr.llm.models import ExtractorResponse
    mock_client = MagicMock()
    mock_client.create.return_value = ExtractorResponse(
        exits=["north", "south", "west"], in_combat=False, is_room_description=True
    )
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = [{"name": "mailbox", "num": 5}]

    state = State(
        {
            S.GAME_RESPONSE: "You are standing in a forest. There are paths to the north, south, and west.",
            S.LOCATION_NAME: "Forest",
            S.LOCATION_ID: 10,
            S.IN_COMBAT: False,
        }
    )
    result, new_state = extract_info.run(
        state, client=mock_client, jericho=mock_jericho, config=MagicMock(
            extractor_model="test", default_temperature=0.0, default_max_tokens=1024
        )
    )
    assert new_state[S.EXITS] == ["north", "south", "west"]
    assert new_state[S.IS_ROOM_DESCRIPTION] is True
    assert new_state[S.IN_COMBAT] is False
    assert {"name": "mailbox", "num": 5} in new_state[S.VISIBLE_OBJECTS]


def test_extract_fallback_on_llm_error():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("API error")
    mock_jericho = MagicMock(spec=JerichoInterface)
    mock_jericho.get_visible_objects.return_value = []

    state = State(
        {
            S.GAME_RESPONSE: "Darkness.",
            S.LOCATION_NAME: "Dark",
            S.LOCATION_ID: 1,
            S.IN_COMBAT: False,
        }
    )
    result, new_state = extract_info.run(
        state, client=mock_client, jericho=mock_jericho, config=MagicMock(
            extractor_model="test", default_temperature=0.0, default_max_tokens=1024
        )
    )
    # Should not crash; exits default to empty
    assert new_state[S.EXITS] == []
    assert new_state[S.IN_COMBAT] is False
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_extract.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement extract_info**

`zorkburr/actions/extract.py`:
```python
"""Hybrid information extraction: Jericho for objects, LLM for exits/combat."""

from __future__ import annotations

import logging

from burr.core import action, State

import instructor

from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.models import ExtractorResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S

logger = logging.getLogger(__name__)

_extractor_prompt: str | None = None


def _get_extractor_prompt() -> str:
    global _extractor_prompt
    if _extractor_prompt is None:
        _extractor_prompt = load_prompt("extractor")
    return _extractor_prompt


@action(
    reads=[
        S.GAME_RESPONSE,
        S.LOCATION_NAME,
        S.LOCATION_ID,
        S.IN_COMBAT,
    ],
    writes=[
        S.EXITS,
        S.IN_COMBAT,
        S.IS_ROOM_DESCRIPTION,
        S.VISIBLE_OBJECTS,
    ],
)
def extract_info(
    state: State,
    client: instructor.Instructor,
    jericho: JerichoInterface,
    config: GameConfig,
) -> tuple[dict, State]:
    """Extract structured game state using hybrid approach."""
    game_text = state[S.GAME_RESPONSE]

    # Jericho-sourced data (instant, reliable)
    visible_objects = jericho.get_visible_objects()

    # LLM-sourced data (exits, combat, room description)
    exits = []
    in_combat = state[S.IN_COMBAT]  # Preserve previous state as fallback
    is_room_description = False

    try:
        system = _get_extractor_prompt()
        user_msg = (
            f"Current Location: {state[S.LOCATION_NAME]}\n"
            f"Previous Combat State: {state[S.IN_COMBAT]}\n\n"
            f"Game Text:\n```\n{game_text}\n```"
        )

        response: ExtractorResponse = client.create(
            model=config.extractor_model,
            response_model=ExtractorResponse,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,  # Deterministic extraction
            max_tokens=1024,
            max_retries=2,
        )

        exits = response.exits
        in_combat = response.in_combat
        is_room_description = response.is_room_description

    except Exception as e:
        logger.warning(f"Extractor LLM failed: {e}")

    return (
        {"exits_found": len(exits)},
        state.update(
            **{
                S.EXITS: exits,
                S.IN_COMBAT: in_combat,
                S.IS_ROOM_DESCRIPTION: is_room_description,
                S.VISIBLE_OBJECTS: visible_objects,
            }
        ),
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_extract.py -v
```
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/extract.py tests/test_actions/test_extract.py
git commit -m "feat: hybrid extract_info — Jericho objects + LLM exits/combat"
```

---

### Task 15: Wire Extraction into Turn Graph

**Files:**
- Modify: `zorkburr/app.py`

- [ ] **Step 1: Update build_turn_app to include extraction after execution**

Add extraction between execute_action and the loop-back. Update the transitions:

```python
from zorkburr.actions.extract import extract_info

# In build_turn_app, add:
bound_extract = extract_info.bind(client=client, jericho=jericho, config=config)

# Update .with_actions():
.with_actions(
    assemble_context=assemble_context,
    generate_action=bound_agent,
    evaluate_action=bound_critic,
    execute_action=bound_execute,
    extract_info=bound_extract,
    turn_complete=turn_complete,
)

# Update .with_transitions():
.with_transitions(
    ("assemble_context", "generate_action"),
    ("generate_action", "evaluate_action"),
    ("evaluate_action", "execute_action",
     expr(f"{S.CRITIC_SCORE} >= {threshold}")),
    ("evaluate_action", "execute_action",
     expr(f"{S.REJECTION_COUNT} >= {max_rejections}")),
    ("evaluate_action", "generate_action", default),
    # Execute → extract → loop/halt
    ("execute_action", "extract_info"),
    ("extract_info", "assemble_context",
     when(**{S.GAME_OVER: False})),
    ("extract_info", "turn_complete",
     when(**{S.GAME_OVER: True})),
)
```

- [ ] **Step 2: Run smoke test**

```bash
cd /Volumes/workingfolder/ZorkBurr && python scripts/smoke_test.py
```

Expected: Agent now has exit information in context. Actions should be more directed.

- [ ] **Step 3: Commit**

```bash
git add zorkburr/app.py
git commit -m "feat: wire extraction into turn graph — exits now inform agent context"
```

---

## Phase 5: Memory System

Goal: Record action outcomes at source locations, synthesize memories via LLM, provide location-specific context.

### Task 16: Memory Data Model

**Files:**
- Create: `zorkburr/actions/memory.py`
- Create: `tests/test_actions/test_memory.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_memory.py`:
```python
from burr.core import State
from unittest.mock import MagicMock

from zorkburr.actions.memory import record_memory, should_synthesize, Memory
from zorkburr.state import S


def test_memory_dataclass():
    m = Memory(
        category="SUCCESS",
        title="Opened mailbox",
        text="Opening the mailbox reveals a leaflet inside.",
        episode="ep-1",
        turn=5,
        persistence="permanent",
        status="ACTIVE",
    )
    assert m.category == "SUCCESS"
    assert m.is_active


def test_should_synthesize_on_score_change():
    assert should_synthesize(score_delta=5, location_changed=False, died=False) is True


def test_should_synthesize_on_location_change():
    assert should_synthesize(score_delta=0, location_changed=True, died=False) is True


def test_should_synthesize_on_death():
    assert should_synthesize(score_delta=0, location_changed=False, died=True) is True


def test_should_not_synthesize_no_change():
    assert should_synthesize(score_delta=0, location_changed=False, died=False) is False


def test_record_memory_with_synthesis():
    from zorkburr.llm.models import MemorySynthesisResponse
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True,
        category="DISCOVERY",
        memory_title="Found leaflet",
        memory_text="Mailbox contains a leaflet.",
        persistence="permanent",
        status="ACTIVE",
        reasoning="new info",
    )

    state = State(
        {
            S.PRE_LOCATION_ID: 10,
            S.PRE_LOCATION_NAME: "West of House",
            S.PRE_SCORE: 0,
            S.PRE_INVENTORY: [],
            S.LOCATION_ID: 10,
            S.SCORE: 5,
            S.INVENTORY: ["leaflet"],
            S.GAME_OVER: False,
            S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
            S.ACTION_TO_TAKE: "open mailbox",
            S.AGENT_REASONING: "check the mailbox",
            S.ACTION_HISTORY: [],
            S.MEMORIES_BY_LOCATION: {},
            S.EPISODE_ID: "ep-1",
            S.TURN_COUNT: 5,
        }
    )

    result, new_state = record_memory.run(
        state, client=mock_client, config=MagicMock(memory_model="test", default_temperature=0.5, default_max_tokens=2048)
    )
    mems = new_state[S.MEMORIES_BY_LOCATION]
    assert "10" in mems or 10 in mems
    loc_mems = mems.get("10", mems.get(10, []))
    assert len(loc_mems) == 1
    assert loc_mems[0]["title"] == "Found leaflet"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_memory.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement memory module**

`zorkburr/actions/memory.py`:
```python
"""Memory recording and synthesis: location-based action outcome memories."""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict

from burr.core import action, State

import instructor

from zorkburr.config import GameConfig
from zorkburr.llm.models import MemorySynthesisResponse
from zorkburr.state import S

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    category: str  # SUCCESS, FAILURE, DISCOVERY, DANGER, NOTE
    title: str
    text: str
    episode: str
    turn: int
    persistence: str  # core, permanent, ephemeral
    status: str  # ACTIVE, TENTATIVE, SUPERSEDED

    @property
    def is_active(self) -> bool:
        return self.status in ("ACTIVE", "TENTATIVE")

    def to_dict(self) -> dict:
        return asdict(self)


def should_synthesize(
    score_delta: int, location_changed: bool, died: bool
) -> bool:
    """Determine if memory synthesis should trigger."""
    return score_delta != 0 or location_changed or died


_SYNTHESIS_PROMPT = """You are a memory synthesizer for an AI playing Zork I.
Given an action and its outcome, decide if this is worth remembering.

Rules:
- DO remember: object interactions, dangers, puzzle mechanics, item discoveries, score-earning actions
- DO NOT remember: simple movement between rooms, looking around, exits/directions (tracked by map)
- Memories are stored at the SOURCE location (where the action was taken)

If should_remember=true, provide:
- category: SUCCESS | FAILURE | DISCOVERY | DANGER | NOTE
- memory_title: 3-6 word evergreen title
- memory_text: 1-2 sentence actionable insight
- persistence: core (first-visit observations) | permanent (game mechanics) | ephemeral (agent actions)
- status: ACTIVE (confirmed) | TENTATIVE (uncertain outcome)

Return JSON:
{"should_remember": bool, "reasoning": "...", "category": "...", "memory_title": "...", "memory_text": "...", "persistence": "...", "status": "..."}
"""


@action(
    reads=[
        S.PRE_LOCATION_ID,
        S.PRE_LOCATION_NAME,
        S.PRE_SCORE,
        S.PRE_INVENTORY,
        S.LOCATION_ID,
        S.SCORE,
        S.INVENTORY,
        S.GAME_OVER,
        S.GAME_RESPONSE,
        S.ACTION_TO_TAKE,
        S.AGENT_REASONING,
        S.ACTION_HISTORY,
        S.MEMORIES_BY_LOCATION,
        S.EPISODE_ID,
        S.TURN_COUNT,
    ],
    writes=[S.MEMORIES_BY_LOCATION],
)
def record_memory(
    state: State, client: instructor.Instructor, config: GameConfig
) -> tuple[dict, State]:
    """Evaluate action outcome and synthesize memory if warranted."""
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    location_changed = state[S.LOCATION_ID] != state[S.PRE_LOCATION_ID]
    died = state[S.GAME_OVER] and state.get(S.GAME_OVER_REASON, "") == "death"

    if not should_synthesize(score_delta, location_changed, died):
        return {"synthesized": False}, state

    # Build synthesis context
    context = (
        f"Location: {state[S.PRE_LOCATION_NAME]} (ID: {state[S.PRE_LOCATION_ID]})\n"
        f"Action: {state[S.ACTION_TO_TAKE]}\n"
        f"Agent reasoning: {state[S.AGENT_REASONING]}\n"
        f"Response: {state[S.GAME_RESPONSE][:500]}\n\n"
        f"Score change: {score_delta}\n"
        f"Location changed: {location_changed}\n"
        f"Died: {died}\n"
    )

    # Add existing memories for deduplication
    loc_key = str(state[S.PRE_LOCATION_ID])
    existing = state[S.MEMORIES_BY_LOCATION].get(loc_key, [])
    if existing:
        mem_lines = [f"  - [{m['category']}] {m['title']}: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
        context += f"\nExisting memories at this location:\n" + "\n".join(mem_lines)

    try:
        response: MemorySynthesisResponse = client.create(
            model=config.memory_model,
            response_model=MemorySynthesisResponse,
            messages=[
                {"role": "system", "content": _SYNTHESIS_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.5,
            max_tokens=2048,
            max_retries=2,
        )

        if response.should_remember:
            mem = Memory(
                category=response.category,
                title=response.memory_title,
                text=response.memory_text,
                episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT],
                persistence=response.persistence,
                status=response.status,
            )

            # Update memories dict (immutable — build new)
            all_mems = dict(state[S.MEMORIES_BY_LOCATION])
            loc_list = list(all_mems.get(loc_key, []))
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list

            return (
                {"synthesized": True, "memory_title": mem.title},
                state.update(**{S.MEMORIES_BY_LOCATION: all_mems}),
            )

    except Exception as e:
        logger.warning(f"Memory synthesis failed: {e}")

    return {"synthesized": False}, state
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_memory.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 5: Wire memory into turn graph and commit**

Update `zorkburr/app.py`: add `record_memory` action after `extract_info`, before the loop-back transition. The memory action runs every turn but only synthesizes when triggered.

```python
from zorkburr.actions.memory import record_memory

# Add to build_turn_app:
bound_memory = record_memory.bind(client=client, config=config)

# Update actions and transitions:
# extract_info → record_memory → assemble_context/turn_complete
```

```bash
git add zorkburr/actions/memory.py tests/test_actions/test_memory.py zorkburr/app.py
git commit -m "feat: memory recording with LLM synthesis at source location"
```

---

## Phase 6: Map System

Goal: Build spatial graph from movement, track exit confidence, provide map context.

### Task 17: Map Graph Data Structure

**Files:**
- Create: `zorkburr/game/map_graph.py`
- Create: `tests/test_map_graph.py`

- [ ] **Step 1: Write failing test**

`tests/test_map_graph.py`:
```python
from zorkburr.game.map_graph import MapGraph


def test_add_room():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    assert mg.has_room(10)
    assert mg.get_room_name(10) == "West of House"


def test_add_connection():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "North of House")
    mg.add_connection(10, "north", 20)
    exits = mg.get_exits(10)
    assert "north" in exits
    assert exits["north"] == 20


def test_reverse_connection():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "North of House")
    mg.add_connection(10, "north", 20)
    # Reverse connection should be auto-added
    exits = mg.get_exits(20)
    assert "south" in exits


def test_track_exit_failure():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.track_exit_failure(10, "up")
    mg.track_exit_failure(10, "up")
    mg.track_exit_failure(10, "up")
    assert mg.get_exit_failures(10, "up") == 3


def test_serialize_deserialize():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "Forest")
    mg.add_connection(10, "north", 20)

    data = mg.to_dict()
    mg2 = MapGraph.from_dict(data)
    assert mg2.has_room(10)
    assert mg2.get_exits(10)["north"] == 20


def test_get_context_for_prompt():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "Forest")
    mg.add_connection(10, "north", 20)
    ctx = mg.get_context_for_prompt(10)
    assert "north" in ctx.lower()
    assert "Forest" in ctx or "forest" in ctx.lower()
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_map_graph.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement MapGraph**

`zorkburr/game/map_graph.py`:
```python
"""Spatial map graph: rooms, connections, confidence tracking."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional


_OPPOSITE_DIRS = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "up": "down", "down": "up",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
}

_DIR_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up", "d": "down", "ne": "northeast", "nw": "northwest",
    "se": "southeast", "sw": "southwest",
    "go north": "north", "go south": "south", "go east": "east",
    "go west": "west", "go up": "up", "go down": "down",
}


def normalize_direction(action: str) -> Optional[str]:
    """Convert action string to canonical direction, or None if not movement."""
    action = action.lower().strip()
    if action in _DIR_ALIASES:
        return _DIR_ALIASES[action]
    if action in _OPPOSITE_DIRS:
        return action
    return None


class MapGraph:
    """Graph of rooms and connections with confidence tracking."""

    def __init__(self):
        self.rooms: dict[int, str] = {}  # room_id → name
        self.connections: dict[int, dict[str, int]] = defaultdict(dict)  # room_id → {dir: dest_id}
        self.connection_confidence: dict[tuple[int, str], int] = defaultdict(int)  # (room_id, dir) → verification count
        self.exit_failures: dict[tuple[int, str], int] = defaultdict(int)  # (room_id, dir) → failure count

    def add_room(self, room_id: int, name: str) -> None:
        self.rooms[room_id] = name

    def has_room(self, room_id: int) -> bool:
        return room_id in self.rooms

    def get_room_name(self, room_id: int) -> str:
        return self.rooms.get(room_id, "Unknown")

    def add_connection(
        self, from_id: int, direction: str, to_id: int
    ) -> None:
        """Add a verified connection. Auto-adds reverse if possible."""
        direction = normalize_direction(direction) or direction
        self.connections[from_id][direction] = to_id
        self.connection_confidence[(from_id, direction)] += 1

        # Auto-add reverse
        opposite = _OPPOSITE_DIRS.get(direction)
        if opposite:
            self.connections[to_id][opposite] = from_id
            self.connection_confidence[(to_id, opposite)] += 1

    def get_exits(self, room_id: int) -> dict[str, int]:
        """Return {direction: destination_id} for a room."""
        return dict(self.connections.get(room_id, {}))

    def track_exit_failure(self, room_id: int, direction: str) -> None:
        direction = normalize_direction(direction) or direction
        self.exit_failures[(room_id, direction)] += 1

    def get_exit_failures(self, room_id: int, direction: str) -> int:
        direction = normalize_direction(direction) or direction
        return self.exit_failures.get((room_id, direction), 0)

    def get_context_for_prompt(self, current_room_id: int) -> str:
        """Generate map context for agent prompt."""
        lines = []
        exits = self.get_exits(current_room_id)
        if exits:
            lines.append("**Known Exits from here:**")
            for direction, dest_id in sorted(exits.items()):
                dest_name = self.get_room_name(dest_id)
                conf = self.connection_confidence.get((current_room_id, direction), 0)
                lines.append(f"  {direction} → {dest_name} (verified {conf}x)")
        else:
            lines.append("**No mapped exits from here yet.**")

        room_name = self.get_room_name(current_room_id)
        lines.insert(0, f"**Current Room:** {room_name}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize for Burr state persistence."""
        return {
            "rooms": {str(k): v for k, v in self.rooms.items()},
            "connections": {
                str(k): v for k, v in self.connections.items()
            },
            "confidence": {
                f"{k[0]}:{k[1]}": v
                for k, v in self.connection_confidence.items()
            },
            "failures": {
                f"{k[0]}:{k[1]}": v
                for k, v in self.exit_failures.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> MapGraph:
        """Deserialize from state dict."""
        mg = cls()
        mg.rooms = {int(k): v for k, v in data.get("rooms", {}).items()}
        for room_str, exits in data.get("connections", {}).items():
            room_id = int(room_str)
            for direction, dest_id in exits.items():
                mg.connections[room_id][direction] = dest_id
        for key, count in data.get("confidence", {}).items():
            room_str, direction = key.split(":", 1)
            mg.connection_confidence[(int(room_str), direction)] = count
        for key, count in data.get("failures", {}).items():
            room_str, direction = key.split(":", 1)
            mg.exit_failures[(int(room_str), direction)] = count
        return mg
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_map_graph.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/game/map_graph.py tests/test_map_graph.py
git commit -m "feat: MapGraph — spatial graph with confidence tracking and serialization"
```

---

### Task 18: Map Update in Results Action

**Files:**
- Create: `zorkburr/actions/results.py`
- Create: `tests/test_actions/test_results.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_results.py`:
```python
from burr.core import State

from zorkburr.actions.results import record_results
from zorkburr.game.map_graph import MapGraph
from zorkburr.state import S


def test_record_results_updates_map_on_movement():
    mg = MapGraph()
    mg.add_room(10, "West of House")

    state = State(
        {
            S.PRE_LOCATION_ID: 10,
            S.PRE_LOCATION_NAME: "West of House",
            S.LOCATION_ID: 20,
            S.LOCATION_NAME: "North of House",
            S.ACTION_TO_TAKE: "north",
            S.SCORE: 0,
            S.PRE_SCORE: 0,
            S.TURN_COUNT: 3,
            S.GAME_OVER: False,
            S.MAP_DATA: mg.to_dict(),
            S.VISITED_LOCATIONS: [10],
            S.TURNS_SINCE_PROGRESS: 2,
            S.LAST_SCORE_CHANGE_TURN: 1,
            S.REJECTION_COUNT: 0,
            S.DISCOVERED_OBJECTIVES: [],
            S.COMPLETED_OBJECTIVES: [],
        }
    )
    result, new_state = record_results.run(state)

    # Map should have new room and connection
    mg2 = MapGraph.from_dict(new_state[S.MAP_DATA])
    assert mg2.has_room(20)
    assert mg2.get_exits(10).get("north") == 20
    assert 20 in new_state[S.VISITED_LOCATIONS]


def test_record_results_tracks_score_progress():
    state = State(
        {
            S.PRE_LOCATION_ID: 10,
            S.PRE_LOCATION_NAME: "West",
            S.LOCATION_ID: 10,
            S.LOCATION_NAME: "West",
            S.ACTION_TO_TAKE: "open mailbox",
            S.SCORE: 5,
            S.PRE_SCORE: 0,
            S.TURN_COUNT: 3,
            S.GAME_OVER: False,
            S.MAP_DATA: {},
            S.VISITED_LOCATIONS: [10],
            S.TURNS_SINCE_PROGRESS: 5,
            S.LAST_SCORE_CHANGE_TURN: 0,
            S.REJECTION_COUNT: 0,
            S.DISCOVERED_OBJECTIVES: [],
            S.COMPLETED_OBJECTIVES: [],
        }
    )
    result, new_state = record_results.run(state)
    assert new_state[S.TURNS_SINCE_PROGRESS] == 0  # Reset on score change
    assert new_state[S.LAST_SCORE_CHANGE_TURN] == 3


def test_record_results_resets_rejection_count():
    state = State(
        {
            S.PRE_LOCATION_ID: 10,
            S.PRE_LOCATION_NAME: "West",
            S.LOCATION_ID: 10,
            S.LOCATION_NAME: "West",
            S.ACTION_TO_TAKE: "look",
            S.SCORE: 0,
            S.PRE_SCORE: 0,
            S.TURN_COUNT: 2,
            S.GAME_OVER: False,
            S.MAP_DATA: {},
            S.VISITED_LOCATIONS: [10],
            S.TURNS_SINCE_PROGRESS: 1,
            S.LAST_SCORE_CHANGE_TURN: 0,
            S.REJECTION_COUNT: 2,
            S.DISCOVERED_OBJECTIVES: [],
            S.COMPLETED_OBJECTIVES: [],
        }
    )
    _, new_state = record_results.run(state)
    assert new_state[S.REJECTION_COUNT] == 0  # Reset for next turn
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_results.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement record_results**

`zorkburr/actions/results.py`:
```python
"""Record results: update map, track progress, reset per-turn state."""

from __future__ import annotations

from burr.core import action, State

from zorkburr.game.map_graph import MapGraph, normalize_direction
from zorkburr.state import S


@action(
    reads=[
        S.PRE_LOCATION_ID,
        S.PRE_LOCATION_NAME,
        S.LOCATION_ID,
        S.LOCATION_NAME,
        S.ACTION_TO_TAKE,
        S.SCORE,
        S.PRE_SCORE,
        S.TURN_COUNT,
        S.GAME_OVER,
        S.MAP_DATA,
        S.VISITED_LOCATIONS,
        S.TURNS_SINCE_PROGRESS,
        S.LAST_SCORE_CHANGE_TURN,
        S.REJECTION_COUNT,
        S.DISCOVERED_OBJECTIVES,
        S.COMPLETED_OBJECTIVES,
    ],
    writes=[
        S.MAP_DATA,
        S.VISITED_LOCATIONS,
        S.TURNS_SINCE_PROGRESS,
        S.LAST_SCORE_CHANGE_TURN,
        S.REJECTION_COUNT,
    ],
)
def record_results(state: State) -> tuple[dict, State]:
    """Update map from movement, track progress, reset per-turn counters."""
    pre_loc = state[S.PRE_LOCATION_ID]
    cur_loc = state[S.LOCATION_ID]
    action_text = state[S.ACTION_TO_TAKE]
    score_delta = state[S.SCORE] - state[S.PRE_SCORE]
    turn = state[S.TURN_COUNT]

    # --- Map update ---
    mg = MapGraph.from_dict(state[S.MAP_DATA]) if state[S.MAP_DATA] else MapGraph()

    # Ensure current room exists
    if not mg.has_room(cur_loc):
        mg.add_room(cur_loc, state[S.LOCATION_NAME])

    # If location changed, record connection
    moved = pre_loc != cur_loc and pre_loc != 0
    if moved:
        direction = normalize_direction(action_text)
        if direction:
            if not mg.has_room(pre_loc):
                mg.add_room(pre_loc, state[S.PRE_LOCATION_NAME])
            mg.add_connection(pre_loc, direction, cur_loc)

    # Track visited locations
    visited = list(state[S.VISITED_LOCATIONS])
    if cur_loc not in visited:
        visited.append(cur_loc)

    # --- Progress tracking ---
    turns_since = state[S.TURNS_SINCE_PROGRESS]
    last_score_turn = state[S.LAST_SCORE_CHANGE_TURN]

    if score_delta != 0:
        turns_since = 0
        last_score_turn = turn
    else:
        turns_since += 1

    return (
        {"moved": moved, "score_delta": score_delta},
        state.update(
            **{
                S.MAP_DATA: mg.to_dict(),
                S.VISITED_LOCATIONS: visited,
                S.TURNS_SINCE_PROGRESS: turns_since,
                S.LAST_SCORE_CHANGE_TURN: last_score_turn,
                S.REJECTION_COUNT: 0,  # Reset for next turn
            }
        ),
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_results.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 5: Wire into turn graph and commit**

Update `zorkburr/app.py`: insert `record_results` and `record_memory` between `extract_info` and the loop-back. The full chain becomes:

```
execute_action → extract_info → record_results → record_memory → assemble_context/turn_complete
```

Update transitions accordingly, with `record_memory` being the action that checks `game_over` for the loop/halt decision.

```bash
git add zorkburr/actions/results.py tests/test_actions/test_results.py zorkburr/app.py
git commit -m "feat: record_results action — map updates, progress tracking"
```

---

## Phase 7: Objectives

### Task 19: Objective Actions

**Files:**
- Create: `zorkburr/actions/objectives.py`
- Create: `tests/test_actions/test_objectives.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_objectives.py`:
```python
from unittest.mock import MagicMock
from burr.core import State

from zorkburr.actions.objectives import update_objectives, check_objective_completion
from zorkburr.state import S


def test_update_objectives_discovers_new():
    from zorkburr.llm.models import ObjectiveDiscoveryResponse
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=["Find the treasure", "Explore the forest"], completed=[]
    )

    state = State(
        {
            S.DISCOVERED_OBJECTIVES: [],
            S.COMPLETED_OBJECTIVES: [],
            S.ACTION_HISTORY: [{"action": "look", "response": "forest", "turn": 1}],
            S.GAME_RESPONSE: "You are in a forest.",
            S.SCORE: 0,
            S.LOCATION_NAME: "Forest",
            S.TURN_COUNT: 10,
            S.KNOWLEDGE_BASE: "",
        }
    )
    _, new_state = update_objectives.run(
        state, client=mock_client, config=MagicMock(analysis_model="test", default_temperature=0.7, default_max_tokens=2048)
    )
    assert "Find the treasure" in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 2


def test_check_completion_marks_done():
    from zorkburr.llm.models import ObjectiveCompletionResponse
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveCompletionResponse(
        completed_objectives=["Open the mailbox"]
    )

    state = State(
        {
            S.DISCOVERED_OBJECTIVES: ["Open the mailbox", "Find treasure"],
            S.COMPLETED_OBJECTIVES: [],
            S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
            S.ACTION_TO_TAKE: "open mailbox",
            S.TURN_COUNT: 5,
            S.SCORE: 5,
        }
    )
    _, new_state = check_objective_completion.run(
        state, client=mock_client, config=MagicMock(analysis_model="test", default_temperature=0.0, default_max_tokens=1024)
    )
    assert "Open the mailbox" not in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1
    assert new_state[S.COMPLETED_OBJECTIVES][0]["objective"] == "Open the mailbox"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_objectives.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement objective actions**

`zorkburr/actions/objectives.py`:
```python
"""Objective discovery, completion checking, and refinement."""

from __future__ import annotations

import logging

from burr.core import action, State

import instructor

from zorkburr.config import GameConfig
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.state import S

logger = logging.getLogger(__name__)

_DISCOVERY_PROMPT = """You are analyzing a Zork I game session to discover objectives.
Based on the recent gameplay, identify 1-5 actionable objectives the player should pursue.
Objectives should be specific and achievable (e.g., "Open the trapdoor" not "Win the game").
"""

_COMPLETION_PROMPT = """Given the most recent action and response in Zork I, determine which objectives (if any) have been completed.
Only mark objectives as completed if there is clear evidence in the game response.
"""


@action(
    reads=[
        S.DISCOVERED_OBJECTIVES,
        S.COMPLETED_OBJECTIVES,
        S.ACTION_HISTORY,
        S.GAME_RESPONSE,
        S.SCORE,
        S.LOCATION_NAME,
        S.TURN_COUNT,
        S.KNOWLEDGE_BASE,
    ],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def update_objectives(
    state: State, client: instructor.Instructor, config: GameConfig
) -> tuple[dict, State]:
    """Discover new objectives from recent gameplay."""
    recent_actions = state[S.ACTION_HISTORY][-10:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} → {a.get('response', '')[:200]}"
        for a in recent_actions
    )

    current_objectives = state[S.DISCOVERED_OBJECTIVES]
    user_msg = (
        f"Current location: {state[S.LOCATION_NAME]}\n"
        f"Score: {state[S.SCORE]}\n"
        f"Current objectives: {current_objectives}\n\n"
        f"Recent gameplay:\n{action_summary}"
    )

    try:
        response: ObjectiveDiscoveryResponse = client.create(
            model=config.analysis_model,
            response_model=ObjectiveDiscoveryResponse,
            messages=[
                {"role": "system", "content": _DISCOVERY_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=2048,
            max_retries=2,
        )

        new_objectives = response.objectives
        completed = set(response.completed)
        if True:  # Replaces old `if parsed:` — Instructor always returns validated model

            # Merge: keep existing non-completed + add new unique
            updated = [o for o in current_objectives if o not in completed]
            for o in new_objectives:
                if o not in updated:
                    updated.append(o)

            # Cap at 15 objectives
            updated = updated[:15]

            # Record completions
            completed_records = list(state[S.COMPLETED_OBJECTIVES])
            for obj in completed:
                completed_records.append({
                    "objective": obj,
                    "completed_turn": state[S.TURN_COUNT],
                })

            return (
                {"new_count": len(new_objectives)},
                state.update(**{
                    S.DISCOVERED_OBJECTIVES: updated,
                    S.COMPLETED_OBJECTIVES: completed_records,
                }),
            )
    except Exception as e:
        logger.warning(f"Objective update failed: {e}")

    return {"new_count": 0}, state


@action(
    reads=[
        S.DISCOVERED_OBJECTIVES,
        S.COMPLETED_OBJECTIVES,
        S.GAME_RESPONSE,
        S.ACTION_TO_TAKE,
        S.TURN_COUNT,
        S.SCORE,
    ],
    writes=[S.DISCOVERED_OBJECTIVES, S.COMPLETED_OBJECTIVES],
)
def check_objective_completion(
    state: State, client: instructor.Instructor, config: GameConfig
) -> tuple[dict, State]:
    """Check if any objectives were completed by the last action."""
    objectives = state[S.DISCOVERED_OBJECTIVES]
    if not objectives:
        return {"completed": []}, state

    user_msg = (
        f"Active objectives: {objectives}\n\n"
        f"Action taken: {state[S.ACTION_TO_TAKE]}\n"
        f"Game response: {state[S.GAME_RESPONSE][:500]}\n"
        f"Current score: {state[S.SCORE]}"
    )

    try:
        response: ObjectiveCompletionResponse = client.create(
            model=config.analysis_model,
            response_model=ObjectiveCompletionResponse,
            messages=[
                {"role": "system", "content": _COMPLETION_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=1024,
            max_retries=2,
        )

        completed = set(response.completed_objectives)
        if completed:
                remaining = [o for o in objectives if o not in completed]
                records = list(state[S.COMPLETED_OBJECTIVES])
                for obj in completed:
                    records.append({
                        "objective": obj,
                        "completed_turn": state[S.TURN_COUNT],
                    })
                return (
                    {"completed": list(completed)},
                    state.update(**{
                        S.DISCOVERED_OBJECTIVES: remaining,
                        S.COMPLETED_OBJECTIVES: records,
                    }),
                )
    except Exception as e:
        logger.warning(f"Completion check failed: {e}")

    return {"completed": []}, state
```

- [ ] **Step 4: Run tests**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_objectives.py -v
```
Expected: All 2 tests PASS

- [ ] **Step 5: Wire into turn graph with conditional transitions and commit**

Update `zorkburr/app.py`:
- Add `update_objectives` as a conditional action after `record_memory`
- Add `check_objective_completion` to run every turn (lightweight — skips if no objectives)
- Use `should_update_objectives` flag set in `record_results` based on `turn_count % interval`

Add to `record_results` writes: a `should_update_objectives` state key, computed as `turn % config.objective_update_interval == 0`.

Transitions:
```python
("record_memory", "check_objective_completion"),
("check_objective_completion", "update_objectives",
 when(should_update_objectives=True)),
("check_objective_completion", "assemble_context",
 when(**{S.GAME_OVER: False})),
("check_objective_completion", "turn_complete",
 when(**{S.GAME_OVER: True})),
("update_objectives", "assemble_context", default),
```

```bash
git add zorkburr/actions/objectives.py tests/test_actions/test_objectives.py zorkburr/app.py
git commit -m "feat: objective discovery and completion checking with periodic updates"
```

---

## Phase 8: Knowledge Management

### Task 20: Knowledge Synthesis Action

**Files:**
- Create: `zorkburr/actions/knowledge.py`
- Create: `tests/test_actions/test_knowledge.py`

- [ ] **Step 1: Write failing test**

`tests/test_actions/test_knowledge.py`:
```python
from unittest.mock import MagicMock
from burr.core import State

from zorkburr.actions.knowledge import update_knowledge
from zorkburr.state import S


def test_update_knowledge_synthesizes():
    mock_client = MagicMock()
    # Knowledge uses the underlying OpenAI client for free-text
    mock_raw = MagicMock()
    mock_client.client = mock_raw
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        "## Strategic Insights\n"
        "- The mailbox contains a leaflet with game instructions\n"
        "- Explore around the house before going inside\n"
    )
    mock_raw.chat.completions.create.return_value = mock_response

    state = State(
        {
            S.KNOWLEDGE_BASE: "",
            S.ACTION_HISTORY: [
                {"turn": i, "action": f"action_{i}", "response": f"resp_{i}"}
                for i in range(1, 11)
            ],
            S.DISCOVERED_OBJECTIVES: ["Find treasure"],
            S.COMPLETED_OBJECTIVES: [],
            S.SCORE: 10,
            S.TURN_COUNT: 50,
            S.MEMORIES_BY_LOCATION: {},
        }
    )
    _, new_state = update_knowledge.run(
        state, client=mock_client, config=MagicMock(analysis_model="test", default_temperature=0.7, default_max_tokens=4096)
    )
    assert "mailbox" in new_state[S.KNOWLEDGE_BASE].lower()
    assert len(new_state[S.KNOWLEDGE_BASE]) > 0
```

- [ ] **Step 2: Implement**

`zorkburr/actions/knowledge.py`:
```python
"""Periodic knowledge synthesis: distill gameplay into strategic insights."""

from __future__ import annotations

import logging

from burr.core import action, State

import instructor

from zorkburr.config import GameConfig
from zorkburr.state import S

logger = logging.getLogger(__name__)

_KNOWLEDGE_PROMPT = """You are a strategic analyst for an AI playing Zork I.
Analyze the recent gameplay and produce a concise strategic guide.
Focus on: key discoveries, puzzle insights, dangerous areas, useful items, unexplored areas.
Integrate with any existing knowledge — don't duplicate, update.
Return the full updated strategic guide as markdown text (not JSON).
"""


@action(
    reads=[
        S.KNOWLEDGE_BASE,
        S.ACTION_HISTORY,
        S.DISCOVERED_OBJECTIVES,
        S.COMPLETED_OBJECTIVES,
        S.SCORE,
        S.TURN_COUNT,
        S.MEMORIES_BY_LOCATION,
    ],
    writes=[S.KNOWLEDGE_BASE],
)
def update_knowledge(
    state: State, client: instructor.Instructor, config: GameConfig
) -> tuple[dict, State]:
    """Synthesize strategic knowledge from recent gameplay.

    Note: Knowledge is free-form markdown, not structured output.
    We use Instructor's underlying OpenAI client for this call.
    """
    recent = state[S.ACTION_HISTORY][-50:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} → {a.get('response', '')[:150]}"
        for a in recent
    )

    existing = state[S.KNOWLEDGE_BASE]
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n"
        f"Objectives: {state[S.DISCOVERED_OBJECTIVES]}\n"
        f"Completed: {[o['objective'] for o in state[S.COMPLETED_OBJECTIVES]]}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\n"
        f"Recent gameplay:\n{action_summary}"
    )

    try:
        # Use the underlying OpenAI client for free-text response
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=config.analysis_model,
            messages=[
                {"role": "system", "content": _KNOWLEDGE_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or ""
        return (
            {"knowledge_length": len(content)},
            state.update(**{S.KNOWLEDGE_BASE: content}),
        )
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
```

- [ ] **Step 3: Run test, wire into graph, commit**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/test_actions/test_knowledge.py -v
```
Expected: PASS

Wire `update_knowledge` as a conditional action after `update_objectives` / `check_objective_completion`, triggered by `should_update_knowledge` flag (set in `record_results` when `turn % knowledge_interval == 0`).

```bash
git add zorkburr/actions/knowledge.py tests/test_actions/test_knowledge.py zorkburr/app.py
git commit -m "feat: periodic knowledge synthesis action"
```

---

## Phase 9: Episode Management

### Task 21: Episode Init/Finalize Actions

**Files:**
- Create: `zorkburr/actions/episode.py`

- [ ] **Step 1: Implement episode actions**

`zorkburr/actions/episode.py`:
```python
"""Episode lifecycle: initialization and finalization."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from burr.core import action, State

from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.game.map_graph import MapGraph
from zorkburr.state import S, create_initial_state

logger = logging.getLogger(__name__)


@action(reads=[], writes=list(vars(S).values()))
def initialize_episode(
    state: State,
    jericho: JerichoInterface,
    config: GameConfig,
    episode_number: int = 1,
) -> tuple[dict, State]:
    """Initialize a new episode: start Jericho, create fresh state, load persisted data."""
    episode_id = f"ep-{episode_number}-{uuid.uuid4().hex[:6]}"

    # Start game
    jericho.start()

    # Create fresh state
    new_state = create_initial_state(episode_id=episode_id)

    # Seed from Jericho
    loc_id, loc_name = jericho.get_location()
    score, max_score = jericho.get_score()
    inventory = jericho.get_inventory()
    new_state = new_state.update(**{
        S.GAME_RESPONSE: jericho.last_response,
        S.LOCATION_ID: loc_id,
        S.LOCATION_NAME: loc_name,
        S.SCORE: score,
        S.MAX_SCORE: max_score,
        S.INVENTORY: inventory,
    })

    # Load persisted map if exists
    map_path = Path(config.map_file)
    if map_path.exists():
        try:
            mg = MapGraph.from_dict(json.loads(map_path.read_text()))
            new_state = new_state.update(**{S.MAP_DATA: mg.to_dict()})
            logger.info(f"Loaded map with {len(mg.rooms)} rooms")
        except Exception as e:
            logger.warning(f"Failed to load map: {e}")

    # Load persisted knowledge if exists
    kb_path = Path(config.knowledge_file)
    if kb_path.exists():
        new_state = new_state.update(**{S.KNOWLEDGE_BASE: kb_path.read_text()})

    return {"episode_id": episode_id}, new_state


@action(
    reads=[
        S.EPISODE_ID,
        S.TURN_COUNT,
        S.SCORE,
        S.MAX_SCORE,
        S.MAP_DATA,
        S.KNOWLEDGE_BASE,
        S.DISCOVERED_OBJECTIVES,
        S.COMPLETED_OBJECTIVES,
        S.GAME_OVER_REASON,
    ],
    writes=[],
)
def finalize_episode(
    state: State,
    config: GameConfig,
) -> tuple[dict, State]:
    """Save map and knowledge to disk for cross-episode persistence."""
    # Save map
    if state[S.MAP_DATA]:
        map_path = Path(config.map_file)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(state[S.MAP_DATA], indent=2))
        logger.info(f"Saved map to {map_path}")

    # Save knowledge
    if state[S.KNOWLEDGE_BASE]:
        kb_path = Path(config.knowledge_file)
        kb_path.parent.mkdir(parents=True, exist_ok=True)
        kb_path.write_text(state[S.KNOWLEDGE_BASE])
        logger.info(f"Saved knowledge to {kb_path}")

    summary = {
        "episode_id": state[S.EPISODE_ID],
        "turns": state[S.TURN_COUNT],
        "score": state[S.SCORE],
        "max_score": state[S.MAX_SCORE],
        "reason": state[S.GAME_OVER_REASON],
        "objectives_completed": len(state[S.COMPLETED_OBJECTIVES]),
    }
    logger.info(f"Episode complete: {summary}")

    return summary, state
```

- [ ] **Step 2: Create main entry point with episode loop**

Create `zorkburr/main.py`:
```python
"""Main entry point: run ZorkBurr episodes."""

from __future__ import annotations

import argparse
import logging
import sys

from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.actions.episode import initialize_episode, finalize_episode
from zorkburr.state import S

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("zorkburr")


def run_episode(
    config: GameConfig,
    jericho: JerichoInterface,
    client: instructor.Instructor,
    episode_number: int,
) -> dict:
    """Run a single episode and return summary."""
    # Initialize
    jericho.start()
    logger.info(f"=== Episode {episode_number} starting ===")

    app = build_turn_app(
        config=config,
        jericho=jericho,
        llm=llm,
        episode_id=f"ep-{episode_number}",
        tracker="local",
    )

    # Run until game over or max turns
    try:
        while True:
            action_obj, result, state = app.step()

            if action_obj.name == "execute_action":
                turn = state[S.TURN_COUNT]
                if turn % 10 == 0:
                    logger.info(
                        f"Turn {turn} | Score: {state[S.SCORE]} | "
                        f"Location: {state[S.LOCATION_NAME]}"
                    )

            if state[S.GAME_OVER]:
                logger.info(f"Game over: {state[S.GAME_OVER_REASON]}")
                break

            if state[S.TURN_COUNT] >= config.max_turns_per_episode:
                logger.info("Max turns reached")
                break

            # Stuck detection
            if (
                state[S.TURNS_SINCE_PROGRESS] >= config.max_turns_stuck
                and state[S.TURN_COUNT] % config.stuck_check_interval == 0
            ):
                logger.info("Stuck — ending episode")
                break

    except KeyboardInterrupt:
        logger.info("Interrupted")

    # Finalize
    summary, _ = finalize_episode.run(state, config=config)
    return summary


def main():
    parser = argparse.ArgumentParser(description="ZorkBurr: AI Zork Player")
    parser.add_argument("--episodes", type=int, default=1, help="Number of episodes")
    args = parser.parse_args()

    config = GameConfig()
    if not config.openrouter_api_key:
        print("Set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    from zorkburr.llm.client import create_llm_client
    client = create_llm_client(config)

    for ep in range(1, args.episodes + 1):
        with JerichoInterface(config.game_file) as jericho:
            summary = run_episode(config, jericho, llm, ep)
            print(f"\nEpisode {ep}: {summary}")

    print(f"\nBurr tracking: run 'burr' to view at http://localhost:7241")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test multi-episode run and commit**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m zorkburr.main --episodes 1
```

Expected: Runs one episode, saves map and knowledge to `data/`.

```bash
git add zorkburr/actions/episode.py zorkburr/main.py
git commit -m "feat: episode lifecycle + main entry point with multi-episode support"
```

---

## Phase 10: Progress Detection & Polish

### Task 22: Stuck Detection and Warnings

**Files:**
- Create: `zorkburr/actions/progress.py`

- [ ] **Step 1: Implement progress tracking in context assembly**

Add stuck warnings to `assemble_context` — when `turns_since_progress > stuck_warning_threshold`, add escalating urgency warnings to the formatted context.

Update `zorkburr/actions/context.py` to read `S.TURNS_SINCE_PROGRESS` and append warnings:

```python
# In assemble_context, after objectives section:
turns_stuck = state[S.TURNS_SINCE_PROGRESS]
if turns_stuck >= 20:  # Warning threshold
    remaining = 40 - turns_stuck  # max_turns_stuck - current
    if remaining <= 5:
        sections.append(
            f"**🚨 CRITICAL: Episode ends in {remaining} turns if no progress! "
            f"Try something completely different.**"
        )
    elif remaining <= 10:
        sections.append(
            f"**⚠ WARNING: {remaining} turns until episode ends. "
            f"Change strategy — explore new areas or try new items.**"
        )
```

- [ ] **Step 2: Add max turns check to record_results**

In `record_results`, add a `should_terminate` flag to state when stuck threshold is reached. The main loop checks this alongside `game_over`.

Add to state.py:
```python
SHOULD_TERMINATE = "should_terminate"
```

- [ ] **Step 3: Test with controlled scenario and commit**

Write a test that runs 45 turns with a mock LLM that always returns "look", verify the episode terminates due to stuck detection.

```bash
git add zorkburr/actions/progress.py zorkburr/actions/context.py zorkburr/state.py
git commit -m "feat: stuck detection with escalating warnings and episode termination"
```

---

### Task 23: Burr Persistence Setup

**Files:**
- Modify: `zorkburr/app.py`

- [ ] **Step 1: Add SQLite persistence to build_turn_app**

```python
from burr.core.persistence import SQLitePersister

def build_turn_app(..., persist: bool = True):
    ...
    if persist:
        persister = SQLitePersister.from_values(
            db_path="data/burr_state.db",
            table_name="zorkburr_state",
        )
        persister.initialize()
        builder = builder.with_state_persister(persister)
    ...
```

- [ ] **Step 2: Verify persistence works**

Run a few turns, kill the process, verify state can be loaded:

```bash
python -c "
from burr.core.persistence import SQLitePersister
p = SQLitePersister.from_values(db_path='data/burr_state.db', table_name='zorkburr_state')
p.initialize()
data = p.list_app_ids('default')
print(f'Persisted apps: {data}')
"
```

- [ ] **Step 3: Commit**

```bash
git add zorkburr/app.py
git commit -m "feat: SQLite state persistence via Burr persister"
```

---

### Task 24: Final Integration — Complete Turn Graph

**Files:**
- Modify: `zorkburr/app.py`

- [ ] **Step 1: Finalize the complete turn graph**

Ensure `build_turn_app` includes all actions and transitions:

```python
def build_turn_app(
    config: GameConfig,
    jericho: JerichoInterface,
    client: instructor.Instructor,
    episode_id: str | None = None,
    tracker: str | None = "local",
    persist: bool = False,
):
    """Build the complete turn graph with all features.

    Graph flow:
      assemble_context → generate_action → evaluate_action
                                               ↓ accepted
      [← rejected, retry]                 execute_action
                                               ↓
                                          extract_info
                                               ↓
                                         record_results
                                               ↓
                                         record_memory
                                               ↓
                                    check_objective_completion
                                               ↓
                           [if objectives due] update_objectives
                                               ↓
                           [if knowledge due]  update_knowledge
                                               ↓
                               [game_over?] → turn_complete
                               [else]       → assemble_context
    """
    # ... full implementation with all bound actions and transitions
```

The complete transition set:
```python
.with_transitions(
    # Core loop
    ("assemble_context", "generate_action"),
    ("generate_action", "evaluate_action"),

    # Critic: accept or reject
    ("evaluate_action", "execute_action",
     expr(f"{S.CRITIC_SCORE} >= {threshold}")),
    ("evaluate_action", "execute_action",
     expr(f"{S.REJECTION_COUNT} >= {max_rejections}")),
    ("evaluate_action", "generate_action", default),

    # Post-execution pipeline
    ("execute_action", "extract_info"),
    ("extract_info", "record_results"),
    ("record_results", "record_memory"),
    ("record_memory", "check_objective_completion"),

    # Periodic: objectives
    ("check_objective_completion", "update_objectives",
     when(should_update_objectives=True)),
    ("check_objective_completion", "check_knowledge_update",
     default),

    ("update_objectives", "check_knowledge_update"),

    # Periodic: knowledge
    ("check_knowledge_update", "update_knowledge",
     when(should_update_knowledge=True)),
    ("check_knowledge_update", "turn_complete",
     when(**{S.GAME_OVER: True})),
    ("check_knowledge_update", "assemble_context", default),

    ("update_knowledge", "turn_complete",
     when(**{S.GAME_OVER: True})),
    ("update_knowledge", "assemble_context", default),

    # Terminal
    ("turn_complete",),  # No outgoing transitions — halts
)
```

Note: `check_knowledge_update` is a lightweight routing action that just checks the flag — it can be a simple no-op action or combined with `record_results`.

- [ ] **Step 2: Run full smoke test**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m zorkburr.main --episodes 1
```

Watch for 50+ turns with all features active. Verify in Burr UI that all actions appear in the graph.

- [ ] **Step 3: Commit**

```bash
git add zorkburr/app.py
git commit -m "feat: complete turn graph with all actions, critic loop, and periodic updates"
```

---

### Task 25: Smoke Test — Full System

- [ ] **Step 1: Run multi-turn test**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m zorkburr.main --episodes 2
```

Expected:
- Episode 1 runs, discovers some rooms, maybe earns some points
- Map and knowledge saved to `data/`
- Episode 2 starts with loaded map and knowledge
- Agent makes better decisions in Episode 2 due to knowledge

- [ ] **Step 2: View in Burr tracking UI**

```bash
burr
```

Open http://localhost:7241. Verify:
- Both episodes visible as separate applications
- Step-by-step state visible for each action
- Transitions visible in graph view
- Can click any step to see state before/after

- [ ] **Step 3: Run test suite**

```bash
cd /Volumes/workingfolder/ZorkBurr && python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: ZorkBurr v0.1 — complete Burr-based Zork player"
```

---

## Implementation Notes

### Key Architectural Decisions

1. **Flat Burr state** — All game state in one Burr State dict. State keys defined as constants in `S` class. No separate GameState class.

2. **Function-based actions with bind()** — Dependencies (Jericho, Instructor client, config) injected via `action.bind()`, not class constructors. Cleaner, more testable.

3. **Instructor for all LLM calls** — Every LLM interaction uses `client.create(response_model=PydanticModel)` for validated structured output with auto-retry on validation failures. Supports OpenRouter and local LLMs (Ollama) via `instructor.from_provider()`. Knowledge synthesis is the only exception (free-text output uses the underlying OpenAI client).

4. **Explicit transitions** — The graph IS the orchestrator. No orchestrator class. Control flow expressed as Burr transitions with `when()` / `expr()` conditions.

5. **Source location memory** — Memories stored at the location where the action was taken (pre-action state), not the destination. Enables cross-episode learning.

6. **Hybrid extraction** — Jericho for ground truth (objects, inventory, location, score), LLM only for semantic parsing (exits, combat, room descriptions).

7. **Periodic updates as conditional transitions** — `record_results` sets `should_update_objectives` / `should_update_knowledge` flags. Transitions route to update actions conditionally.

8. **Episode management as Python loop** — For the PoC, episodes managed by a simple loop in `main.py` with persistence between episodes via disk files. Outer Burr graph can be added later.

### What's NOT Transferred from ZorkGPT

- `infrastructure/` — No AWS deployment
- Custom HTTP LLM client — Replaced by Instructor (structured output + auto-retry)
- Manual JSON parsing (`extract_json`, `strip_markdown_fences`, `create_json_schema`) — Replaced by Instructor + Pydantic response models
- Langfuse integration — Replaced by Burr tracking
- S3 state export — Replaced by Burr SQLite persistence
- Manager base class pattern — Replaced by Burr action pattern
- `process_turn()` / `should_process_turn()` stubs — Not needed (Burr transitions)
- All dead code identified in deep dives
- `current_room_name_for_map` deprecated field
- State export to JSON files — Replaced by Burr persistence

### Testing Strategy

- **Unit tests**: Mock LLM, test each action independently with Burr State
- **Integration tests**: Real Jericho + mock LLM, test deterministic game scenarios
- **Smoke tests**: Real LLM + real Jericho, short runs (5-10 turns)
- **Burr UI**: Visual verification of graph execution and state flow
