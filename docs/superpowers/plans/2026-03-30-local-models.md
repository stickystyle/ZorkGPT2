# Local Models via mlx_lm.server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace OpenRouter with a locally-managed mlx_lm.server instance running Qwen3-14B-MLX-8bit, with per-action think/no_think routing.

**Architecture:** `GameConfig` gains a `use_local_models` flag that selects between an OpenAI-compatible local client (mlx_lm.server) and OpenRouter. `MlxServer` is a context manager that owns the server subprocess for the full episode run. Three planning-heavy actions (`generate_action`, `update_objectives`, `update_knowledge`) receive a `use_thinking: bool` parameter injected at bind time; a `thinking_kwargs` helper converts that flag into `extra_body` on local runs only.

**Tech Stack:** mlx_lm (mlx_lm.server), instructor, openai SDK, pydantic-settings, pytest + unittest.mock

---

## File Map

| File | Change |
|---|---|
| `zorkburr/config.py` | Add `use_local_models`, `local_model`, `local_base_url` |
| `pyproject.toml` | Add defaults for the three new config fields |
| `zorkburr/llm/client.py` | Add `thinking_kwargs`, `effective_model`; update `create_llm_client`; remove `create_local_client` |
| `zorkburr/llm/mlx_server.py` | **New** — `MlxServer` context manager |
| `zorkburr/actions/agent.py` | Add `use_thinking: bool` param; apply `thinking_kwargs` |
| `zorkburr/actions/objectives.py` | Add `use_thinking: bool` to `update_objectives`; apply `thinking_kwargs` |
| `zorkburr/actions/knowledge.py` | Add `use_thinking: bool`; apply `thinking_kwargs` on raw client call |
| `zorkburr/app.py` | Bind `use_thinking=True/False` to relevant actions |
| `zorkburr/main.py` | Gate OpenRouter key check; wrap episode loop with `MlxServer` |
| `tests/test_config.py` | Add tests for new fields |
| `tests/test_llm_client.py` | Add tests for `thinking_kwargs`, `effective_model`, local client creation |
| `tests/test_llm_mlx_server.py` | **New** — tests for `MlxServer` subprocess lifecycle |
| `tests/test_actions/test_agent.py` | Add `use_local_models=False` to config mocks; add thinking kwarg test |
| `tests/test_actions/test_objectives.py` | Add `use_local_models=False` to config mocks; add thinking kwarg test |
| `tests/test_actions/test_knowledge.py` | Add `use_local_models=False` to config mocks; add thinking kwarg test |

---

### Task 1: Config — add local model fields

**Files:**
- Modify: `zorkburr/config.py`
- Modify: `pyproject.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_local_model_defaults():
    config = GameConfig()
    assert config.use_local_models is False
    assert config.local_model == "mlx-community/Qwen3-14B-MLX-8bit"
    assert config.local_base_url == "http://localhost:8080/v1"

def test_use_local_models_from_env(monkeypatch):
    monkeypatch.setenv("USE_LOCAL_MODELS", "true")
    config = GameConfig()
    assert config.use_local_models is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py::test_local_model_defaults tests/test_config.py::test_use_local_models_from_env -v
```

Expected: FAIL — `GameConfig` has no `use_local_models` attribute

- [ ] **Step 3: Add fields to `GameConfig`**

In `zorkburr/config.py`, add after the existing `openrouter_base_url` line (line 29):

```python
    # Local models
    use_local_models: bool = Field(default=False, alias="USE_LOCAL_MODELS")
    local_model: str = "mlx-community/Qwen3-14B-MLX-8bit"
    local_base_url: str = "http://localhost:8080/v1"
```

- [ ] **Step 4: Add defaults to `pyproject.toml`**

Add after the `openrouter_base_url` equivalent section (after line 29 in `[tool.zorkburr]`):

```toml
use_local_models = false
local_model = "mlx-community/Qwen3-14B-MLX-8bit"
local_base_url = "http://localhost:8080/v1"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add zorkburr/config.py pyproject.toml tests/test_config.py
git commit -m "feat: add local model config fields (use_local_models, local_model, local_base_url)"
```

---

### Task 2: Client helpers — `thinking_kwargs`, `effective_model`, updated factory

**Files:**
- Modify: `zorkburr/llm/client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm_client.py`:

```python
from zorkburr.llm.client import thinking_kwargs, effective_model, create_llm_client
from zorkburr.config import GameConfig

def test_thinking_kwargs_local_thinking_on():
    config = GameConfig(use_local_models=True)
    assert thinking_kwargs(config, True) == {"extra_body": {"thinking": True}}

def test_thinking_kwargs_local_thinking_off():
    config = GameConfig(use_local_models=True)
    assert thinking_kwargs(config, False) == {"extra_body": {"thinking": False}}

def test_thinking_kwargs_openrouter_returns_empty():
    config = GameConfig(openrouter_api_key="test-key")
    assert thinking_kwargs(config, True) == {}
    assert thinking_kwargs(config, False) == {}

def test_effective_model_local():
    config = GameConfig(use_local_models=True)
    assert effective_model(config, "anthropic/claude-sonnet-4.6") == config.local_model

def test_effective_model_openrouter():
    config = GameConfig(openrouter_api_key="test-key")
    assert effective_model(config, "anthropic/claude-haiku-4.5") == "anthropic/claude-haiku-4.5"

def test_create_llm_client_local():
    config = GameConfig(use_local_models=True)
    client = create_llm_client(config)
    assert client is not None

def test_create_llm_client_openrouter():
    config = GameConfig(openrouter_api_key="test-key")
    client = create_llm_client(config)
    assert client is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_client.py::test_thinking_kwargs_local_thinking_on tests/test_llm_client.py::test_effective_model_local -v
```

Expected: FAIL — `thinking_kwargs` not defined

- [ ] **Step 3: Rewrite `zorkburr/llm/client.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_client.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/llm/client.py tests/test_llm_client.py
git commit -m "feat: add thinking_kwargs/effective_model helpers, update create_llm_client for local models"
```

---

### Task 3: `MlxServer` context manager

**Files:**
- Create: `zorkburr/llm/mlx_server.py`
- Create: `tests/test_llm_mlx_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_mlx_server.py`:

```python
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from zorkburr.config import GameConfig
from zorkburr.llm.mlx_server import MlxServer


def test_mlx_server_starts_with_correct_args():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with MlxServer(config):
            mock_popen.assert_called_once_with(
                ["mlx_lm.server", "--model", config.local_model, "--port", "8080"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def test_mlx_server_terminates_subprocess_on_exit():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with MlxServer(config):
            pass

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()


def test_mlx_server_terminates_on_exception():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with pytest.raises(RuntimeError):
            with MlxServer(config):
                raise RuntimeError("game crashed")

    mock_proc.terminate.assert_called_once()


def test_mlx_server_timeout_raises():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen", side_effect=Exception("refused")), \
         patch("zorkburr.llm.mlx_server.time.sleep"), \
         patch("zorkburr.llm.mlx_server.time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        with pytest.raises(TimeoutError, match="mlx_lm.server"):
            with MlxServer(config):
                pass
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_mlx_server.py -v
```

Expected: FAIL — `MlxServer` not found

- [ ] **Step 3: Create `zorkburr/llm/mlx_server.py`**

```python
"""Lifecycle manager for a local mlx_lm.server subprocess."""
from __future__ import annotations

import logging
import subprocess
import time
import urllib.request
from urllib.parse import urlparse

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = 120  # seconds
_POLL_INTERVAL = 2  # seconds


class MlxServer:
    """Context manager that owns the mlx_lm.server process for the duration of a run."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._process: subprocess.Popen | None = None

    def __enter__(self) -> "MlxServer":
        port = urlparse(self._config.local_base_url).port or 8080
        logger.info(f"Starting mlx_lm.server: model={self._config.local_model} port={port}")
        self._process = subprocess.Popen(
            ["mlx_lm.server", "--model", self._config.local_model, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_ready()
        logger.info("mlx_lm.server is ready")
        return self

    def __exit__(self, *args) -> None:
        if self._process is not None:
            logger.info("Stopping mlx_lm.server")
            self._process.terminate()
            self._process.wait(timeout=10)
            self._process = None

    def _wait_for_ready(self) -> None:
        url = self._config.local_base_url.rstrip("/") + "/models"
        deadline = time.monotonic() + _STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(url, timeout=2)
                return
            except Exception:
                time.sleep(_POLL_INTERVAL)
        raise TimeoutError(
            f"mlx_lm.server did not respond at {url} within {_STARTUP_TIMEOUT}s"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_mlx_server.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/llm/mlx_server.py tests/test_llm_mlx_server.py
git commit -m "feat: add MlxServer subprocess context manager"
```

---

### Task 4: Add `use_thinking` to `generate_action`

**Files:**
- Modify: `zorkburr/actions/agent.py`
- Test: `tests/test_actions/test_agent.py`

- [ ] **Step 1: Write the failing test and fix existing mocks**

In `tests/test_actions/test_agent.py`, add a new test and fix the existing config mocks to set `use_local_models=False` so `thinking_kwargs` returns `{}` for them:

```python
from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.agent import generate_action
from zorkburr.llm.models import AgentResponse
from zorkburr.state import S

def _mock_config(**kwargs):
    """Config mock with safe defaults for local-model guards."""
    defaults = dict(
        agent_model="test",
        default_temperature=1.0,
        default_max_tokens=4096,
        use_local_models=False,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)

def test_generate_action_returns_validated_response():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="I should look around", action="look", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are at the white house.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "look"
    assert "look around" in new_state[S.AGENT_REASONING]

def test_generate_action_retry_includes_feedback():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="trying something else", action="open mailbox", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are at the white house.",
        S.REJECTION_COUNT: 1,
        S.CRITIC_JUSTIFICATION: "Action 'north' was repetitive.",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 2,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "open mailbox"
    call_args = mock_client.create.call_args
    messages = call_args.kwargs.get("messages")
    user_msg = messages[-1]["content"]
    assert "rejected" in user_msg.lower() or "repetitive" in user_msg.lower()

def test_generate_action_fallback_on_error():
    mock_client = MagicMock()
    mock_client.create.side_effect = Exception("LLM error")
    state = State({
        S.FORMATTED_CONTEXT: "You are somewhere.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert new_state[S.PROPOSED_ACTION] == "look"

def test_generate_action_passes_thinking_extra_body_when_local():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="deep reasoning", action="north", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "You are in a maze.",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 5,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert call_kwargs.get("extra_body") == {"thinking": True}

def test_generate_action_no_extra_body_on_openrouter():
    mock_client = MagicMock()
    mock_client.create.return_value = AgentResponse(
        thinking="reasoning", action="south", new_objective=""
    )
    state = State({
        S.FORMATTED_CONTEXT: "context",
        S.REJECTION_COUNT: 0,
        S.CRITIC_JUSTIFICATION: "",
        S.KNOWLEDGE_BASE: "",
        S.TURN_COUNT: 1,
    })
    result, new_state = generate_action.run(
        state, client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_actions/test_agent.py -v
```

Expected: FAIL — `generate_action.run()` does not accept `use_thinking`

- [ ] **Step 3: Update `zorkburr/actions/agent.py`**

Change the function signature and `client.create` call:

```python
from zorkburr.llm.client import effective_model, thinking_kwargs

@action(
    reads=[S.FORMATTED_CONTEXT, S.REJECTION_COUNT, S.CRITIC_JUSTIFICATION, S.KNOWLEDGE_BASE, S.TURN_COUNT],
    writes=[S.PROPOSED_ACTION, S.AGENT_REASONING, S.NEW_OBJECTIVE, S.ACTION_TO_TAKE],
)
def generate_action(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    """Ask the agent LLM for the next action. Returns validated AgentResponse."""
    system = _get_system_prompt(state[S.KNOWLEDGE_BASE])
    user_content = state[S.FORMATTED_CONTEXT]

    if state[S.REJECTION_COUNT] > 0:
        feedback = state[S.CRITIC_JUSTIFICATION]
        user_content += (
            f"\n\n**Your previous action was rejected (attempt {state[S.REJECTION_COUNT]}).**\n"
            f"Reason: {feedback}\nPlease propose a DIFFERENT action."
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    try:
        response: AgentResponse = client.create(
            model=effective_model(config, config.agent_model),
            response_model=AgentResponse,
            messages=messages,
            temperature=config.default_temperature,
            max_tokens=config.default_max_tokens,
            max_retries=3,
            **thinking_kwargs(config, use_thinking),
        )
        action_text = clean_action(response.action)
        reasoning = response.thinking
        new_objective = response.new_objective
    except Exception as e:
        logger.error(f"Agent LLM call failed: {e}")
        action_text = "look"
        reasoning = f"LLM error: {e}"
        new_objective = ""

    new_state = state.update(**{
        S.PROPOSED_ACTION: action_text,
        S.AGENT_REASONING: reasoning,
        S.NEW_OBJECTIVE: new_objective,
        S.ACTION_TO_TAKE: action_text,
    })
    return {"action": action_text}, new_state


generate_action.run = generate_action.action_function.run_and_update
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_actions/test_agent.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/agent.py tests/test_actions/test_agent.py
git commit -m "feat: add use_thinking param to generate_action with extra_body injection"
```

---

### Task 5: Add `use_thinking` to `update_objectives`

**Files:**
- Modify: `zorkburr/actions/objectives.py`
- Test: `tests/test_actions/test_objectives.py`

- [ ] **Step 1: Write the failing test and fix existing mocks**

Replace `tests/test_actions/test_objectives.py`:

```python
from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.objectives import update_objectives, check_objective_completion
from zorkburr.llm.models import ObjectiveDiscoveryResponse, ObjectiveCompletionResponse
from zorkburr.state import S


def _mock_config(**kwargs):
    defaults = dict(analysis_model="test", use_local_models=False)
    defaults.update(kwargs)
    return MagicMock(**defaults)


def test_update_objectives_discovers_new():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(
        objectives=["Find the treasure", "Explore the forest"], completed=[]
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [{"action": "look", "response": "forest", "turn": 1}],
        S.GAME_RESPONSE: "You are in a forest.", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
    })
    _, new_state = update_objectives.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert "Find the treasure" in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.DISCOVERED_OBJECTIVES]) == 2


def test_check_completion_marks_done():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveCompletionResponse(
        completed_objectives=["Open the mailbox"]
    )
    state = State({
        S.DISCOVERED_OBJECTIVES: ["Open the mailbox", "Find treasure"],
        S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "Opening the mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.TURN_COUNT: 5, S.SCORE: 5,
    })
    _, new_state = check_objective_completion.run(
        state, client=mock_client, config=MagicMock()
    )
    assert "Open the mailbox" not in new_state[S.DISCOVERED_OBJECTIVES]
    assert len(new_state[S.COMPLETED_OBJECTIVES]) == 1


def test_check_completion_no_objectives():
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.GAME_RESPONSE: "test", S.ACTION_TO_TAKE: "look",
        S.TURN_COUNT: 1, S.SCORE: 0,
    })
    result, new_state = check_objective_completion.run(
        state, client=MagicMock(), config=MagicMock()
    )
    assert result["completed"] == []


def test_update_objectives_passes_thinking_extra_body():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(objectives=[], completed=[])
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [], S.GAME_RESPONSE: "test", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
    })
    update_objectives.run(
        state, client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert call_kwargs.get("extra_body") == {"thinking": True}


def test_update_objectives_no_extra_body_on_openrouter():
    mock_client = MagicMock()
    mock_client.create.return_value = ObjectiveDiscoveryResponse(objectives=[], completed=[])
    state = State({
        S.DISCOVERED_OBJECTIVES: [], S.COMPLETED_OBJECTIVES: [],
        S.ACTION_HISTORY: [], S.GAME_RESPONSE: "test", S.SCORE: 0,
        S.LOCATION_NAME: "Forest", S.TURN_COUNT: 10, S.KNOWLEDGE_BASE: "",
    })
    update_objectives.run(
        state, client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_client.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_actions/test_objectives.py -v
```

Expected: FAIL — `update_objectives.run()` does not accept `use_thinking`

- [ ] **Step 3: Update `update_objectives` in `zorkburr/actions/objectives.py`**

Add the import at the top and update only `update_objectives` (not `check_objective_completion`):

```python
from zorkburr.llm.client import effective_model, thinking_kwargs
```

Change the function signature:

```python
def update_objectives(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
```

Change the `client.create` call to:

```python
        response: ObjectiveDiscoveryResponse = client.create(
            model=effective_model(config, config.analysis_model),
            response_model=ObjectiveDiscoveryResponse,
            messages=[{"role": "system", "content": _DISCOVERY_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=2048, max_retries=2,
            **thinking_kwargs(config, use_thinking),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_actions/test_objectives.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/objectives.py tests/test_actions/test_objectives.py
git commit -m "feat: add use_thinking param to update_objectives"
```

---

### Task 6: Add `use_thinking` to `update_knowledge`

**Files:**
- Modify: `zorkburr/actions/knowledge.py`
- Test: `tests/test_actions/test_knowledge.py`

- [ ] **Step 1: Write the failing test and fix existing mocks**

Replace `tests/test_actions/test_knowledge.py`:

```python
from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.knowledge import update_knowledge
from zorkburr.state import S


def _mock_config(**kwargs):
    defaults = dict(analysis_model="test", use_local_models=False)
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _base_state():
    return State({
        S.KNOWLEDGE_BASE: "",
        S.ACTION_HISTORY: [{"turn": i, "action": f"a{i}", "response": f"r{i}"} for i in range(1, 11)],
        S.DISCOVERED_OBJECTIVES: ["Find treasure"],
        S.COMPLETED_OBJECTIVES: [],
        S.SCORE: 10, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })


def test_update_knowledge_synthesizes():
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_client.client = mock_raw
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "## Strategic Insights\n- The mailbox contains a leaflet\n"
    mock_raw.chat.completions.create.return_value = mock_response

    _, new_state = update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert "mailbox" in new_state[S.KNOWLEDGE_BASE].lower()


def test_update_knowledge_fallback_on_error():
    mock_client = MagicMock()
    mock_client.client.chat.completions.create.side_effect = Exception("API error")
    state = State({
        S.KNOWLEDGE_BASE: "existing",
        S.ACTION_HISTORY: [], S.DISCOVERED_OBJECTIVES: [],
        S.COMPLETED_OBJECTIVES: [], S.SCORE: 0, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })

    result, new_state = update_knowledge.run(
        state, client=mock_client, config=_mock_config(), use_thinking=False
    )
    assert result["knowledge_length"] == 0
    assert new_state[S.KNOWLEDGE_BASE] == "existing"


def test_update_knowledge_passes_thinking_extra_body():
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_client.client = mock_raw
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "insights"
    mock_raw.chat.completions.create.return_value = mock_response

    update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(use_local_models=True), use_thinking=True
    )
    call_kwargs = mock_raw.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("extra_body") == {"thinking": True}


def test_update_knowledge_no_extra_body_on_openrouter():
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_client.client = mock_raw
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "insights"
    mock_raw.chat.completions.create.return_value = mock_response

    update_knowledge.run(
        _base_state(), client=mock_client, config=_mock_config(use_local_models=False), use_thinking=True
    )
    call_kwargs = mock_raw.chat.completions.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_actions/test_knowledge.py -v
```

Expected: FAIL — `update_knowledge.run()` does not accept `use_thinking`

- [ ] **Step 3: Update `zorkburr/actions/knowledge.py`**

Add import and update function:

```python
from zorkburr.llm.client import effective_model, thinking_kwargs

@action(
    reads=[S.KNOWLEDGE_BASE, S.ACTION_HISTORY, S.DISCOVERED_OBJECTIVES,
           S.COMPLETED_OBJECTIVES, S.SCORE, S.TURN_COUNT, S.MEMORIES_BY_LOCATION],
    writes=[S.KNOWLEDGE_BASE],
)
def update_knowledge(state: State, client: instructor.Instructor, config: GameConfig, use_thinking: bool = False) -> tuple[dict, State]:
    recent = state[S.ACTION_HISTORY][-50:]
    action_summary = "\n".join(
        f"Turn {a['turn']}: {a['action']} -> {a.get('response', '')[:150]}" for a in recent
    )
    existing = state[S.KNOWLEDGE_BASE]
    user_msg = (
        f"Score: {state[S.SCORE]} | Turn: {state[S.TURN_COUNT]}\n"
        f"Objectives: {state[S.DISCOVERED_OBJECTIVES]}\n"
        f"Completed: {[o['objective'] for o in state[S.COMPLETED_OBJECTIVES]]}\n\n"
        f"Existing knowledge:\n{existing or '(none yet)'}\n\nRecent gameplay:\n{action_summary}"
    )
    try:
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=effective_model(config, config.analysis_model),
            messages=[{"role": "system", "content": _KNOWLEDGE_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.7, max_tokens=4096,
            **thinking_kwargs(config, use_thinking),
        )
        content = response.choices[0].message.content or ""
        return {"knowledge_length": len(content)}, state.update(**{S.KNOWLEDGE_BASE: content})
    except Exception as e:
        logger.warning(f"Knowledge update failed: {e}")
        return {"knowledge_length": 0}, state
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_actions/test_knowledge.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/knowledge.py tests/test_actions/test_knowledge.py
git commit -m "feat: add use_thinking param to update_knowledge"
```

---

### Task 7: Wire `use_thinking` bindings in `app.py`

**Files:**
- Modify: `zorkburr/app.py`
- Test: `tests/test_app.py` (verify existing tests still pass)

- [ ] **Step 1: Run existing app tests to establish baseline**

```bash
pytest tests/test_app.py -v
```

Note which tests pass. All should pass before this change.

- [ ] **Step 2: Update bindings in `zorkburr/app.py`**

Change the three thinking-action bindings (lines 58, 64, 65):

```python
    bound_agent = generate_action.bind(client=client, config=config, use_thinking=True)
    bound_critic = evaluate_action.bind(llm=client, jericho=jericho, config=config)
    bound_execute = execute_action.bind(jericho=jericho)
    bound_extract = extract_info.bind(client=client, jericho=jericho, config=config)
    bound_memory = record_memory.bind(client=client, config=config)
    bound_completion = check_objective_completion.bind(client=client, config=config)
    bound_objectives = update_objectives.bind(client=client, config=config, use_thinking=True)
    bound_knowledge = update_knowledge.bind(client=client, config=config, use_thinking=True)
```

- [ ] **Step 3: Run app tests to verify nothing broke**

```bash
pytest tests/test_app.py -v
```

Expected: same results as baseline

- [ ] **Step 4: Run the full test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/app.py
git commit -m "feat: bind use_thinking=True to planning actions in turn graph"
```

---

### Task 8: Update `main.py` — server lifecycle and key guard

**Files:**
- Modify: `zorkburr/main.py`

- [ ] **Step 1: Run existing main-related tests to establish baseline**

```bash
pytest tests/ -k "main or episode" -v
```

Note the passing tests.

- [ ] **Step 2: Rewrite `zorkburr/main.py`**

```python
"""Main entry point: run ZorkBurr episodes."""
from __future__ import annotations

import argparse
import logging
import sys

from zorkburr.actions.episode import finalize_episode, initialize_episode
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.llm.mlx_server import MlxServer
from zorkburr.state import S

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("zorkburr")


def run_episode(
    config: GameConfig,
    jericho: JerichoInterface,
    client,
    episode_number: int,
) -> dict:
    """Run a single episode and return a summary dict."""
    jericho.start()
    logger.info(f"=== Episode {episode_number} starting ===")

    overrides = initialize_episode(jericho, config, episode_number)

    app = build_turn_app(
        config=config,
        jericho=jericho,
        client=client,
        episode_id=f"ep-{episode_number}",
        tracker="local",
    )

    if overrides:
        app._state = app.state.update(**overrides)

    state = app.state
    try:
        while True:
            action_obj, result, state = app.step()
            if action_obj.name == "execute_action":
                turn = state[S.TURN_COUNT]
                if turn % 10 == 0 or turn <= 3:
                    logger.info(
                        f"Turn {turn} | Score: {state[S.SCORE]} "
                        f"| Location: {state[S.LOCATION_NAME]}"
                    )
            if state[S.GAME_OVER]:
                logger.info(f"Game over: {state[S.GAME_OVER_REASON]}")
                break
            if state[S.TURN_COUNT] >= config.max_turns_per_episode:
                logger.info("Max turns reached")
                break
            if (
                state[S.TURNS_SINCE_PROGRESS] >= config.max_turns_stuck
                and state[S.TURN_COUNT] % config.stuck_check_interval == 0
            ):
                logger.info("Stuck — ending episode")
                break
    except KeyboardInterrupt:
        logger.info("Interrupted")

    return finalize_episode(state, config)


def _run_episodes(config: GameConfig, args: argparse.Namespace) -> None:
    client = create_llm_client(config)
    for ep in range(1, args.episodes + 1):
        with JerichoInterface(config.game_file) as jericho:
            summary = run_episode(config, jericho, client, ep)
            print(f"\nEpisode {ep}: {summary}")
    print("\nBurr tracking: run 'burr' to view at http://localhost:7241")


def main():
    parser = argparse.ArgumentParser(description="ZorkBurr: AI Zork Player")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=None)
    args = parser.parse_args()

    config = GameConfig()
    if args.max_turns:
        config.max_turns_per_episode = args.max_turns

    if not config.use_local_models and (
        not config.openrouter_api_key or config.openrouter_api_key == "your-key-here"
    ):
        print("Set OPENROUTER_API_KEY in .env (or set use_local_models = true)")
        sys.exit(1)

    if config.use_local_models:
        with MlxServer(config):
            _run_episodes(config, args)
    else:
        _run_episodes(config, args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add zorkburr/main.py
git commit -m "feat: gate OpenRouter key check, wrap episode loop with MlxServer when use_local_models=true"
```

---

## Verification

- [ ] **Run full test suite one final time**

```bash
pytest -v --tb=short
```

Expected: all PASS, no failures

- [ ] **Smoke-test local mode config loads correctly**

```bash
python -c "
from zorkburr.config import GameConfig
import os; os.environ['USE_LOCAL_MODELS'] = 'true'
c = GameConfig()
print('use_local_models:', c.use_local_models)
print('local_model:', c.local_model)
print('local_base_url:', c.local_base_url)
"
```

Expected output:
```
use_local_models: True
local_model: mlx-community/Qwen3-14B-MLX-8bit
local_base_url: http://localhost:8080/v1
```

> **Note on `extra_body` field name:** The `thinking` key in `thinking_kwargs` matches mlx_lm.server's Qwen3 API. If the server uses a different field (e.g. `enable_thinking`), update `thinking_kwargs` in `zorkburr/llm/client.py` — that is the only place this is defined.
