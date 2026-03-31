# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests (MUST use uv run — pytest is not on system PATH)
uv run pytest tests/

# Run a single test
uv run pytest tests/test_state.py::test_create_initial_state -v

# Run tests excluding LLM client tests (requires API key)
uv run pytest tests/ --ignore=tests/test_llm_client.py

# Install dependencies
pip install -e ".[dev]"

# Run the orchestrator (starts a monitored episode loop)
/zork-orchestrator   # Claude Code slash command

# Run a single episode manually
uv run run_episode.py --max-turns 100 --episode-id test01
```

## Configuration

All game settings live in `pyproject.toml` under `[tool.zorkburr]`. `GameConfig` (Pydantic settings) loads from there, then `.env`, then environment variables. Key values: `agent_model`, `critic_model`, `critic_rejection_threshold`, `max_rejections_per_turn`, `objective_update_interval`, `knowledge_update_interval`. API key goes in `.env` as `OPENROUTER_API_KEY`.

## Architecture

### The Burr Turn Graph

ZorkBurr is a Burr state machine that plays Zork I. One "turn" is a full pass through the graph:

```
assemble_context → generate_action → evaluate_action ──────────────────────────────────────┐
                                          │ (rejected, retry)                               │
                                          └──────────────────→ generate_action              │
                                          │ (accepted OR max rejections)                    │
                                     execute_action → extract_info → record_results         │
                                          → record_memory → check_objective_completion       │
                                          → [update_objectives every N turns]               │
                                          → [update_knowledge every N turns]                │
                                          → assemble_context (next turn) ───────────────────┘
```

The critic (`evaluate_action`) can reject the agent's proposed action up to `max_rejections_per_turn` times before forcing acceptance. `record_results` always resets `REJECTION_COUNT` to 0.

### State

`zorkburr/state.py` defines all state keys as constants on the `S` class. The `State` object is immutable — every action returns a new state via `state.update(**{...})`. Key state groups:
- **Per-turn transients:** `PROPOSED_ACTION`, `CRITIC_SCORE`, `REJECTION_COUNT`, `FORMATTED_CONTEXT`
- **Game truth (from Jericho):** `LOCATION_ID`, `LOCATION_NAME`, `SCORE`, `INVENTORY`, `GAME_OVER`
- **Pre-action snapshots:** `PRE_LOCATION_ID`, `PRE_SCORE`, `PRE_INVENTORY` — snapped by `execute_action` before sending to Jericho, used by `record_memory` to detect what changed
- **Accumulated learning:** `MEMORIES_BY_LOCATION`, `KNOWLEDGE_BASE`, `MAP_DATA`, `DISCOVERED_OBJECTIVES`

### Memory vs. Knowledge Base

Two distinct learning systems:
- **Memories** (`record_memory`, `MEMORIES_BY_LOCATION`): per-location records of significant outcomes (object interactions, dangers, puzzle mechanics). Synthesized by LLM after every action that scores points, changes location, or causes death. Keyed by `location_id`.
- **Knowledge Base** (`update_knowledge`, `KNOWLEDGE_BASE`): a periodic strategic summary distilled from recent action history. Updated every `knowledge_update_interval` turns. Free-form markdown injected at the bottom of `assemble_context`.

Both feed into `assemble_context` and are visible to the agent each turn.

### Project Thesis

**The agent learns to play through experience — not hard-coded knowledge.** Game-specific facts (puzzle solutions, item locations, walkthrough steps) must never appear in prompts. Prompts teach reasoning strategies only. Game-specific knowledge accumulates in `MEMORIES_BY_LOCATION` and `KNOWLEDGE_BASE` through gameplay. When modifying prompts, ask: "would this instruction apply to a different text adventure?" If not, it doesn't belong in the prompt.

### LLM Integration

All LLM calls use [Instructor](https://github.com/instructor-ai/instructor) for structured Pydantic output with auto-retry. Client is created via `create_llm_client(config)` in `zorkburr/llm/client.py` using `instructor.from_provider()`. Response models are in `zorkburr/llm/models.py`. Prompts are markdown files in `prompts/` loaded via `zorkburr/llm/prompts.py`.

For local models (Ollama/mlx_lm), set `USE_LOCAL_MODELS=true` in `.env` and configure `local_model` / `local_base_url`.

### Jericho Interface

`JerichoInterface` (`zorkburr/game/jericho_interface.py`) wraps Jericho's `FrotzEnv`. Must call `jericho.start()` before use. The Z-machine is the ground truth — `LOCATION_NAME`, `SCORE`, `INVENTORY`, and `GAME_OVER` all come from Jericho, not from LLM parsing. ROM file: `roms/zork1.z5`.

### Application Builder

`build_turn_app()` in `zorkburr/app.py` wires everything together via Burr's `ApplicationBuilder`. It accepts `tracker` (default `"local"` for Burr's UI) and `persist` (SQLite via `data/burr_state.db`). The Burr tracking UI runs at `http://localhost:7241` when tracker is active.

### Orchestrator

`run_episode.py` is the CLI entry point — runs one episode and emits structured log lines to stdout:
- Per-turn: `TURN N | loc=... | score=.../... | critic=... | rejections=... | action=...`
- On exit: `EPISODE_END | turns=... | score=... | locations=... | objectives_found=... | reason=...`

The `/zork-orchestrator` slash command (`.claude/commands/zork-orchestrator.md`) runs Claude as a monitor-improve loop: it polls episode logs, detects performance problems, and dispatches Opus subagents to improve prompts and config — one change per episode to measure effect.
