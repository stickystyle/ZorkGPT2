# Local Models via mlx_lm.server

**Date:** 2026-03-30
**Status:** Approved

## Overview

Replace OpenRouter with a locally-running mlx_lm.server instance for ZorkBurr LLM inference. The server runs on the same machine as ZorkBurr, starts with the process, and stays up for the full session (all episodes). OpenRouter remains available as an alternative — configuration selects one or the other, no fallback logic.

Target model: **Qwen3-14B-MLX-8bit** — single model serving all action roles, using Qwen3's `/think` toggle to switch between deep reasoning (planning turns) and fast inference (extraction turns).

## Config Changes

Three new fields added to `GameConfig` and `[tool.zorkburr]` in `pyproject.toml`:

| Field | Default | Description |
|---|---|---|
| `use_local_models` | `false` | When true, ignore OpenRouter fields and use local server |
| `local_model` | `"mlx-community/Qwen3-14B-MLX-8bit"` | MLX model identifier passed to mlx_lm.server |
| `local_base_url` | `"http://localhost:8080/v1"` | OpenAI-compatible endpoint for local server |

When `use_local_models = true`, the five role-based model fields (`agent_model`, `critic_model`, etc.) are unused — all calls go to `local_model`.

The OpenRouter API key validation in `main.py` is gated on `not config.use_local_models`.

## Server Lifecycle (`zorkburr/llm/mlx_server.py`)

`MlxServer` is a context manager that owns the mlx_lm.server subprocess for the duration of the ZorkBurr process.

- `__enter__`: launches `mlx_lm.server --model <local_model> --port 8080` via `subprocess.Popen` (port extracted from `local_base_url`), then polls `GET /v1/models` until the server responds (configurable timeout, raises on failure)
- `__exit__`: terminates the subprocess, ensuring cleanup even on crash or KeyboardInterrupt

In `main()`, the episode loop is extracted into a helper and the server wraps it:

```python
if config.use_local_models:
    with MlxServer(config):
        _run_episodes(config, args)
else:
    _run_episodes(config, args)
```

Startup time (~30–90s for a 14B model) is acceptable: episodes run for hours, so the one-time cost is negligible.

## Client Factory (`zorkburr/llm/client.py`)

`create_llm_client(config)` is the single entry point for both modes:

```python
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

The existing `create_local_client` stub (Ollama format) is removed.

## Think/No_Think Toggle

Qwen3's thinking mode is controlled via `extra_body={"thinking": True/False}` in the API call. Actions are split by cognitive demand:

| Mode | Actions |
|---|---|
| **Thinking ON** | `generate_action`, `update_objectives`, `update_knowledge` |
| **Thinking OFF** | `extract_info`, `record_memory`, `evaluate_action` |

A helper in `llm/client.py`:

```python
THINKING_ACTIONS = frozenset({"generate_action", "update_objectives", "update_knowledge"})

def thinking_kwargs(config: GameConfig, use_thinking: bool) -> dict:
    if config.use_local_models:
        return {"extra_body": {"thinking": use_thinking}}
    return {}
```

Each thinking-aware action receives `use_thinking: bool` via `bind()` in `app.py`. The action passes `**thinking_kwargs(config, use_thinking)` into its `client.create(...)` call. On OpenRouter, `thinking_kwargs` returns `{}` — no change to existing behavior.

## Files Changed

| File | Change |
|---|---|
| `zorkburr/config.py` | Add `use_local_models`, `local_model`, `local_base_url` |
| `pyproject.toml` | Add defaults for new config fields |
| `zorkburr/llm/mlx_server.py` | New — `MlxServer` context manager |
| `zorkburr/llm/client.py` | Replace `create_local_client` stub, update `create_llm_client` to branch on local vs OpenRouter, add `THINKING_ACTIONS` and `thinking_kwargs` |
| `zorkburr/app.py` | Bind `use_thinking` to thinking-aware actions |
| `zorkburr/actions/agent.py` | Accept and apply `use_thinking` |
| `zorkburr/actions/objectives.py` | Accept and apply `use_thinking` |
| `zorkburr/actions/knowledge.py` | Accept and apply `use_thinking` |
| `zorkburr/main.py` | Gate OpenRouter key check, wrap loop with `MlxServer` |

## Out of Scope

- Two-model configurations (14B+9B, 32B+4B) — revisit after validating single-model performance
- Remote server support (192.168.10.109) — not needed if running locally
- Automatic model download — assumes model is already present in MLX cache
