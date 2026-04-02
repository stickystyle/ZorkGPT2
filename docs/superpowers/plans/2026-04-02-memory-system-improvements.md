# Memory System Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate duplicate memory accumulation, add supersession so memories self-correct, and consolidate memories at end-of-episode.

**Architecture:** Three phases layered on the existing `record_memory` → `assemble_context` pipeline. Phase 1 adds guard rails (prompt rules, code dedup, ephemeral pruning, SUPERSEDED filtering). Phase 2 adds supersession (LLM marks old memories as replaced). Phase 3 adds end-of-episode consolidation (LLM reviews and cleans up each location's memories).

**Tech Stack:** Python, Pydantic (response models), Instructor (structured LLM output), Burr (state machine), pytest

**Spec:** `docs/superpowers/specs/2026-04-02-memory-system-improvements-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `zorkburr/actions/memory.py` | Modify | Dedup guard (1B), title exposure (2B), superseded_by field (2C), supersession processing (2D) |
| `zorkburr/actions/context.py` | Modify | Filter SUPERSEDED memories (1D) |
| `zorkburr/actions/episode.py` | Modify | Ephemeral pruning (1C), consolidation backup + processing (3A, 3C), observability counters |
| `zorkburr/llm/models.py` | Modify | `supersedes_titles` field (2A), consolidation models (3B) |
| `zorkburr/state.py` | Modify | Add `MEMORY_STATS` state key (1E) |
| `prompts/memory_synthesis.md` | Modify | Dedup rules (1A), supersession rules (2E) |
| `prompts/memory_consolidation.md` | Create | Consolidation prompt (3D) |
| `run_episode.py` | Modify | Memory stats in EPISODE_END log (1E) |
| `tests/test_actions/test_memory.py` | Modify | Tests for dedup guard, supersession, title format |
| `tests/test_actions/test_context.py` | Modify | Tests for SUPERSEDED filtering |
| `tests/test_actions/test_episode.py` | Modify | Tests for ephemeral pruning, consolidation |
| `tests/test_actions/test_consolidation.py` | Create | Tests for consolidation action processing |

---

## Task 1: Synthesis Prompt Dedup Rules (1A)

**Files:**
- Modify: `prompts/memory_synthesis.md`

- [ ] **Step 1: Add dedup rules to synthesis prompt**

Append after the last `DO NOT remember` line (line 16) in `prompts/memory_synthesis.md`:

```markdown

DEDUPLICATION — do NOT create memories that duplicate existing ones:
- EXACT DUPLICATES: If an existing memory has the same title, do not create another
- SEMANTIC DUPLICATES: If an existing memory conveys the same insight in different words, do not create another
  - BAD: Existing says "Window ajar behind house" -> you create "Behind house window is ajar" (same fact, different words)
  - GOOD: Existing says "Window ajar behind house" -> you create "Enter window to reach Kitchen (+10 points)" (new actionable info)
- If your new observation adds meaningful detail to an existing memory, supersede it with a better version instead of creating a separate entry
```

- [ ] **Step 2: Commit**

```bash
git add prompts/memory_synthesis.md
git commit -m "feat(memory): add dedup rules to synthesis prompt"
```

---

## Task 2: Exact-Title Dedup Guard (1B)

**Files:**
- Modify: `zorkburr/actions/memory.py:87-99`
- Test: `tests/test_actions/test_memory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_memory.py`:

```python
def test_record_memory_rejects_duplicate_title():
    """Exact-title dedup guard: reject memory with same title as existing."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Different text but same title.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found leaflet",
                    "text": "Mailbox contains a leaflet.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is False
    assert result["reason"] == "duplicate_title"
    # Memory list unchanged
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 1


def test_record_memory_allows_duplicate_title_if_superseded():
    """Dedup guard ignores SUPERSEDED memories — the title is available for reuse."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Better version.", persistence="permanent",
        status="ACTIVE", reasoning="improved",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found leaflet",
                    "text": "Old version.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "SUPERSEDED",
                    "superseded_by": "Something else"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert len(new_state[S.MEMORIES_BY_LOCATION]["10"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_memory.py::test_record_memory_rejects_duplicate_title tests/test_actions/test_memory.py::test_record_memory_allows_duplicate_title_if_superseded -v`

Expected: FAIL — no dedup guard exists yet, both memories get appended.

- [ ] **Step 3: Implement dedup guard**

In `zorkburr/actions/memory.py`, replace the block at lines 87-99:

```python
        if response.should_remember:
            mem = Memory(
                category=response.category, title=response.memory_title,
                text=response.memory_text, episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT], persistence=response.persistence,
                status=response.status,
            )
            all_mems = dict(state[S.MEMORIES_BY_LOCATION])
            loc_list = list(all_mems.get(loc_key, []))
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list
            persist_memories(all_mems, config)
            return {"synthesized": True, "memory_title": mem.title}, state.update(**{S.MEMORIES_BY_LOCATION: all_mems})
```

with:

```python
        if response.should_remember:
            all_mems = dict(state[S.MEMORIES_BY_LOCATION])
            loc_list = list(all_mems.get(loc_key, []))

            # Dedup guard: reject exact title matches against non-superseded memories
            existing_titles = {m.get("title") for m in loc_list if m.get("status") != "SUPERSEDED"}
            if response.memory_title in existing_titles:
                logger.info(f"Rejected duplicate memory title: '{response.memory_title}' at location {loc_key}")
                return {"synthesized": False, "reason": "duplicate_title"}, state

            mem = Memory(
                category=response.category, title=response.memory_title,
                text=response.memory_text, episode=state[S.EPISODE_ID],
                turn=state[S.TURN_COUNT], persistence=response.persistence,
                status=response.status,
            )
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list
            persist_memories(all_mems, config)
            return {"synthesized": True, "memory_title": mem.title}, state.update(**{S.MEMORIES_BY_LOCATION: all_mems})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_memory.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/memory.py tests/test_actions/test_memory.py
git commit -m "feat(memory): add exact-title dedup guard in record_memory"
```

---

## Task 3: Ephemeral Pruning on Episode Load (1C)

**Files:**
- Modify: `zorkburr/actions/episode.py:18-56`
- Test: `tests/test_actions/test_episode.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_episode.py`:

```python
class TestEphemeralPruning:
    def test_prunes_ephemeral_memories_on_load(self, tmp_path):
        cfg = _config(tmp_path)
        mems = {
            "10": [
                {"category": "NOTE", "title": "temp", "text": "x",
                 "episode": "ep-1", "turn": 1, "persistence": "ephemeral", "status": "ACTIVE"},
                {"category": "DISCOVERY", "title": "keep", "text": "y",
                 "episode": "ep-1", "turn": 2, "persistence": "permanent", "status": "ACTIVE"},
            ],
            "20": [
                {"category": "NOTE", "title": "also temp", "text": "z",
                 "episode": "ep-1", "turn": 3, "persistence": "ephemeral", "status": "ACTIVE"},
            ],
        }
        Path(cfg.memory_file).write_text(json.dumps(mems))
        from unittest.mock import MagicMock
        overrides = initialize_episode(MagicMock(), cfg)
        # Ephemeral memories pruned
        assert len(overrides["memories_by_location"]["10"]) == 1
        assert overrides["memories_by_location"]["10"][0]["title"] == "keep"
        # Location 20 had only ephemeral memories — should be removed entirely
        assert "20" not in overrides["memories_by_location"]

    def test_no_pruning_when_all_permanent(self, tmp_path):
        cfg = _config(tmp_path)
        mems = {
            "10": [
                {"category": "DISCOVERY", "title": "keep", "text": "y",
                 "persistence": "permanent", "status": "ACTIVE"},
            ],
        }
        Path(cfg.memory_file).write_text(json.dumps(mems))
        from unittest.mock import MagicMock
        overrides = initialize_episode(MagicMock(), cfg)
        assert len(overrides["memories_by_location"]["10"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_episode.py::TestEphemeralPruning -v`

Expected: FAIL — location 20 still present, ephemeral memory at location 10 still present.

- [ ] **Step 3: Implement ephemeral pruning**

In `zorkburr/actions/episode.py`, in `initialize_episode`, after the memory loading block (after line 53), add:

```python
            # Prune ephemeral memories from prior episodes
            raw_mems = overrides["memories_by_location"]
            cleaned = {}
            dropped = 0
            for loc_key, mems in raw_mems.items():
                kept = [m for m in mems if m.get("persistence") != "ephemeral"]
                dropped += len(mems) - len(kept)
                if kept:
                    cleaned[loc_key] = kept
            overrides["memories_by_location"] = cleaned
            if dropped:
                logger.info(f"Pruned {dropped} ephemeral memories from previous episodes")
```

Place this inside the `try` block, after `logger.info(f"Loaded {total} memories...")` and before the `except`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_episode.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/episode.py tests/test_actions/test_episode.py
git commit -m "feat(memory): prune ephemeral memories on episode load"
```

---

## Task 4: Filter SUPERSEDED in Context Assembly (1D)

**Files:**
- Modify: `zorkburr/actions/context.py:58-68` (current-location) and `:76-78` (adjacent)
- Test: `tests/test_actions/test_context.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_context.py`:

```python
def test_assemble_context_filters_superseded_memories():
    """SUPERSEDED memories should not appear in agent context."""
    state = State({
        S.GAME_RESPONSE: "You are west of a white house.",
        S.LOCATION_NAME: "West of House",
        S.INVENTORY: [],
        S.SCORE: 0,
        S.ACTION_HISTORY: [],
        S.EXITS: [],
        S.DISCOVERED_OBJECTIVES: [],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {
            "10": [
                {"category": "DISCOVERY", "title": "Old info", "text": "This is outdated.",
                 "status": "SUPERSEDED", "superseded_by": "New info"},
                {"category": "DISCOVERY", "title": "New info", "text": "This is current.",
                 "status": "ACTIVE"},
            ]
        },
        S.LOCATION_ID: 10,
        S.MAP_DATA: {},
        S.IN_COMBAT: False,
        S.TURN_COUNT: 5,
        S.TURNS_SINCE_PROGRESS: 0,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "This is current." in ctx
    assert "This is outdated." not in ctx


def test_assemble_context_filters_superseded_adjacent_memories():
    """SUPERSEDED memories in adjacent rooms should not appear."""
    map_data = {
        "rooms": {"10": "Kitchen", "42": "Forest"},
        "connections": {"10": {"north": 42}, "42": {"south": 10}},
        "confidence": {"10:north": 2, "42:south": 2},
        "failures": {},
    }
    state = State({
        S.GAME_RESPONSE: "You are in a kitchen.",
        S.LOCATION_NAME: "Kitchen",
        S.INVENTORY: [],
        S.SCORE: 5,
        S.ACTION_HISTORY: [],
        S.EXITS: ["north"],
        S.DISCOVERED_OBJECTIVES: [],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {
            "42": [
                {"category": "DANGER", "title": "Old danger", "text": "Outdated warning.",
                 "status": "SUPERSEDED", "superseded_by": "Safe now"},
                {"category": "SUCCESS", "title": "Safe now", "text": "Forest is safe.",
                 "status": "ACTIVE"},
            ]
        },
        S.LOCATION_ID: 10,
        S.MAP_DATA: map_data,
        S.IN_COMBAT: False,
        S.TURN_COUNT: 3,
        S.TURNS_SINCE_PROGRESS: 0,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "Forest is safe." in ctx
    assert "Outdated warning." not in ctx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_context.py::test_assemble_context_filters_superseded_memories tests/test_actions/test_context.py::test_assemble_context_filters_superseded_adjacent_memories -v`

Expected: FAIL — "This is outdated." / "Outdated warning." appear in context.

- [ ] **Step 3: Implement SUPERSEDED filtering**

In `zorkburr/actions/context.py`, change the current-location block (lines 58-68).

Replace line 59:

```python
        loc_mems = memories[loc_key]
```

with:

```python
        loc_mems = [m for m in memories[loc_key] if m.get("status") != "SUPERSEDED"]
```

For adjacent memories, change line 78 from:

```python
                for m in memories[neighbor_key][:5]:  # max 5 per neighbor
```

to:

```python
                neighbor_mems = [m for m in memories[neighbor_key] if m.get("status") != "SUPERSEDED"]
                for m in neighbor_mems[:5]:  # max 5 per neighbor
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_context.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/context.py tests/test_actions/test_context.py
git commit -m "fix(context): filter SUPERSEDED memories from agent context"
```

---

## Task 5: Observability — Memory Stats on EPISODE_END (1E)

**Files:**
- Modify: `zorkburr/state.py` (add MEMORY_STATS key)
- Modify: `zorkburr/actions/memory.py` (increment counters)
- Modify: `zorkburr/actions/episode.py` (initialize counters, add ephemeral count)
- Modify: `run_episode.py:52-63` (include stats in EPISODE_END)
- Test: `tests/test_actions/test_memory.py` (verify counters increment)

- [ ] **Step 1: Add MEMORY_STATS state key**

In `zorkburr/state.py`, add to class `S` after `MEMORIES_BY_LOCATION`:

```python
    MEMORY_STATS = "memory_stats"
```

And in `create_initial_state`, add after the `S.MEMORIES_BY_LOCATION: {}` line:

```python
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
```

- [ ] **Step 2: Write the failing test for counter increments**

Add to `tests/test_actions/test_memory.py`:

```python
def test_record_memory_increments_new_counter():
    """Memory stats 'new' counter should increment on successful synthesis."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Mailbox contains a leaflet.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_record_memory_increments_dedup_counter():
    """Memory stats 'dedup_rejected' counter should increment on duplicate title."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY", memory_title="Found leaflet",
        memory_text="Different text.", persistence="permanent",
        status="ACTIVE", reasoning="new info",
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found leaflet",
                    "text": "Mailbox contains a leaflet.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is False
    assert new_state[S.MEMORY_STATS]["dedup_rejected"] == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_memory.py::test_record_memory_increments_new_counter tests/test_actions/test_memory.py::test_record_memory_increments_dedup_counter -v`

Expected: FAIL — `S.MEMORY_STATS` key doesn't exist yet / counters not updated.

- [ ] **Step 4: Update prior tests to include MEMORY_STATS in state**

Adding `S.MEMORY_STATS` to the `reads` list means Burr will expect it in state. Update the state dicts in `test_record_memory_with_synthesis`, `test_record_memory_rejects_duplicate_title`, and `test_record_memory_allows_duplicate_title_if_superseded` by adding:

```python
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
```

- [ ] **Step 5: Implement counter tracking in record_memory**

In `zorkburr/actions/memory.py`:

1. Add `S.MEMORY_STATS` to the `reads` list in the `@action` decorator (line 50):

```python
    reads=[S.PRE_LOCATION_ID, S.PRE_LOCATION_NAME, S.PRE_SCORE, S.PRE_INVENTORY,
           S.LOCATION_ID, S.SCORE, S.INVENTORY, S.GAME_OVER, S.GAME_OVER_REASON,
           S.GAME_RESPONSE, S.ACTION_TO_TAKE, S.AGENT_REASONING, S.ACTION_HISTORY,
           S.MEMORIES_BY_LOCATION, S.EPISODE_ID, S.TURN_COUNT, S.MEMORY_STATS],
    writes=[S.MEMORIES_BY_LOCATION, S.MEMORY_STATS],
```

2. In the dedup guard rejection path, increment the counter and return updated state:

```python
            if response.memory_title in existing_titles:
                logger.info(f"Rejected duplicate memory title: '{response.memory_title}' at location {loc_key}")
                stats = dict(state[S.MEMORY_STATS])
                stats["dedup_rejected"] = stats.get("dedup_rejected", 0) + 1
                return {"synthesized": False, "reason": "duplicate_title"}, state.update(**{S.MEMORY_STATS: stats})
```

3. In the successful memory creation path, increment the "new" counter:

```python
            loc_list.append(mem.to_dict())
            all_mems[loc_key] = loc_list
            persist_memories(all_mems, config)
            stats = dict(state[S.MEMORY_STATS])
            stats["new"] = stats.get("new", 0) + 1
            return {"synthesized": True, "memory_title": mem.title}, state.update(
                **{S.MEMORIES_BY_LOCATION: all_mems, S.MEMORY_STATS: stats}
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_memory.py -v`

Expected: ALL PASS

- [ ] **Step 7: Add ephemeral_pruned count to initialize_episode**

In `zorkburr/actions/episode.py`, modify the ephemeral pruning block to return the pruned count. Change `initialize_episode` to return the count in overrides so `run_episode.py` can access it:

After the pruning block, add:

```python
            if dropped:
                logger.info(f"Pruned {dropped} ephemeral memories from previous episodes")
                overrides["ephemeral_pruned"] = dropped
```

- [ ] **Step 8: Add memory stats to EPISODE_END log line**

In `run_episode.py`, update `format_episode_end` (lines 52-63):

```python
def format_episode_end(
    turns: int,
    score: int,
    max_score: int,
    locations: int,
    objectives_found: int,
    reason: str,
    memory_stats: dict | None = None,
) -> str:
    line = (
        f"EPISODE_END | turns={turns} | score={score}/{max_score} | "
        f"locations={locations} | objectives_found={objectives_found} | reason={reason}"
    )
    if memory_stats:
        mem_total = memory_stats.get("total", 0)
        mem_new = memory_stats.get("new", 0)
        mem_dedup = memory_stats.get("dedup_rejected", 0)
        mem_superseded = memory_stats.get("superseded", 0)
        mem_pruned = memory_stats.get("ephemeral_pruned", 0)
        line += (
            f" | mem_total={mem_total} | mem_new={mem_new}"
            f" | mem_dedup_rejected={mem_dedup} | mem_superseded={mem_superseded}"
            f" | mem_ephemeral_pruned={mem_pruned}"
        )
    return line
```

In the `finally` block of `_run` (around line 142), compute and pass memory stats:

```python
            final_state = app.state
            finalize_episode(final_state, config, client=client)

            # Compute memory stats for EPISODE_END
            mem_stats = dict(final_state.get(S.MEMORY_STATS, {}))
            all_mems = final_state.get(S.MEMORIES_BY_LOCATION, {})
            mem_stats["total"] = sum(len(v) for v in all_mems.values())
            mem_stats["ephemeral_pruned"] = overrides.get("ephemeral_pruned", 0)

            print(
                format_episode_end(
                    turns=turn_num,
                    score=final_state[S.SCORE],
                    max_score=final_state[S.MAX_SCORE],
                    locations=len(locations_visited),
                    objectives_found=objectives_found,
                    reason=end_reason,
                    memory_stats=mem_stats,
                ),
                flush=True,
            )
```

- [ ] **Step 9: Run all tests**

Run: `uv run pytest tests/ --ignore=tests/test_llm_client.py -v`

Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add zorkburr/state.py zorkburr/actions/memory.py zorkburr/actions/episode.py run_episode.py tests/test_actions/test_memory.py
git commit -m "feat(memory): add memory stats observability to EPISODE_END log"
```

---

## Task 6: Supersession Response Model + Memory Dataclass (2A, 2C)

**Files:**
- Modify: `zorkburr/llm/models.py:27-34`
- Modify: `zorkburr/actions/memory.py:26-41`
- Test: `tests/test_actions/test_memory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_memory.py`:

```python
def test_memory_dataclass_has_superseded_by():
    m = Memory(category="SUCCESS", title="Old info", text="Was wrong.",
               episode="ep-1", turn=5, persistence="permanent", status="SUPERSEDED",
               superseded_by="New info")
    d = m.to_dict()
    assert d["superseded_by"] == "New info"
    assert not m.is_active  # SUPERSEDED is not active


def test_memory_dataclass_defaults_superseded_by_empty():
    m = Memory(category="SUCCESS", title="Good info", text="Still valid.",
               episode="ep-1", turn=5, persistence="permanent", status="ACTIVE")
    assert m.superseded_by == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_memory.py::test_memory_dataclass_has_superseded_by tests/test_actions/test_memory.py::test_memory_dataclass_defaults_superseded_by_empty -v`

Expected: FAIL — `Memory.__init__()` got unexpected keyword argument `superseded_by`.

- [ ] **Step 3: Add superseded_by to Memory dataclass**

In `zorkburr/actions/memory.py`, add field to `Memory` (after line 34):

```python
@dataclass
class Memory:
    category: str
    title: str
    text: str
    episode: str
    turn: int
    persistence: str
    status: str
    superseded_by: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in ("ACTIVE", "TENTATIVE")

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: Add supersedes_titles to MemorySynthesisResponse**

In `zorkburr/llm/models.py`, add to `MemorySynthesisResponse` (after line 34):

```python
class MemorySynthesisResponse(BaseModel):
    should_remember: bool = Field(description="Whether to remember this")
    reasoning: str = Field(description="Why or why not")
    category: str = Field(default="NOTE", description="SUCCESS|FAILURE|DISCOVERY|DANGER|NOTE")
    memory_title: str = Field(default="", description="3-6 word title")
    memory_text: str = Field(default="", description="1-2 sentence insight")
    persistence: str = Field(default="ephemeral", description="core|permanent|ephemeral")
    status: str = Field(default="ACTIVE", description="ACTIVE|TENTATIVE")
    supersedes_titles: list[str] = Field(
        default_factory=list,
        description="Exact titles of existing memories this replaces. Copy titles verbatim from the existing memories list."
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_memory.py -v`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add zorkburr/actions/memory.py zorkburr/llm/models.py tests/test_actions/test_memory.py
git commit -m "feat(memory): add supersedes_titles to response model and superseded_by to Memory"
```

---

## Task 7: Expose Titles in Synthesis Context (2B)

**Files:**
- Modify: `zorkburr/actions/memory.py:73`
- Test: `tests/test_actions/test_memory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_memory.py`:

```python
def test_record_memory_context_includes_titles(monkeypatch):
    """Synthesis context should show memory titles so the LLM can reference them for supersession."""
    captured_messages = []
    def mock_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return MemorySynthesisResponse(
            should_remember=False, reasoning="test", category="NOTE",
            memory_title="", memory_text="", persistence="ephemeral", status="ACTIVE",
        )

    mock_client = MagicMock()
    mock_client.create.side_effect = mock_create
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West of House",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: ["leaflet"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Opening the small mailbox reveals a leaflet.",
        S.ACTION_TO_TAKE: "open mailbox", S.AGENT_REASONING: "check the mailbox",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DISCOVERY", "title": "Found Mailbox",
                    "text": "Mailbox is near the house.", "episode": "ep-0",
                    "turn": 3, "persistence": "permanent", "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 5,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
    })
    record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))

    # Check the user message sent to the LLM includes the title in bracket format
    user_msg = captured_messages[0][1]["content"]
    assert "[Found Mailbox]:" in user_msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_actions/test_memory.py::test_record_memory_context_includes_titles -v`

Expected: FAIL — context currently shows `[DISCOVERY] Found Mailbox: ...` not `[Found Mailbox]: ...`.

- [ ] **Step 3: Change context format to expose titles**

In `zorkburr/actions/memory.py`, change line 73 from:

```python
        mem_lines = [f"  - [{m['category']}] {m['title']}: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
```

to:

```python
        mem_lines = [f"  - [{m['title']}]: {m['text']}" for m in existing if m.get("status") != "SUPERSEDED"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_memory.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/memory.py tests/test_actions/test_memory.py
git commit -m "feat(memory): expose memory titles in synthesis context for supersession"
```

---

## Task 8: Process Supersession in record_memory (2D)

**Files:**
- Modify: `zorkburr/actions/memory.py` (supersession logic after dedup guard)
- Test: `tests/test_actions/test_memory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_actions/test_memory.py`:

```python
def test_record_memory_supersedes_old_memory():
    """When LLM returns supersedes_titles, old memories should be marked SUPERSEDED."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="DISCOVERY",
        memory_title="Safe Descent with Lantern",
        memory_text="Staircase is safe when carrying the lantern.",
        persistence="permanent", status="ACTIVE", reasoning="corrects old info",
        supersedes_titles=["Dark Staircase Deadly"],
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "Cellar",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 10, S.INVENTORY: ["lantern"],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "You carefully descend the staircase.",
        S.ACTION_TO_TAKE: "go down", S.AGENT_REASONING: "try with lantern",
        S.ACTION_HISTORY: [],
        S.MEMORIES_BY_LOCATION: {
            "10": [{"category": "DANGER", "title": "Dark Staircase Deadly",
                    "text": "Going down without light is fatal.",
                    "episode": "ep-0", "turn": 5, "persistence": "permanent",
                    "status": "ACTIVE"}]
        },
        S.EPISODE_ID: "ep-2", S.TURN_COUNT: 8,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    mems = new_state[S.MEMORIES_BY_LOCATION]["10"]
    # Old memory marked SUPERSEDED
    old = next(m for m in mems if m["title"] == "Dark Staircase Deadly")
    assert old["status"] == "SUPERSEDED"
    assert old["superseded_by"] == "Safe Descent with Lantern"
    # New memory added
    new = next(m for m in mems if m["title"] == "Safe Descent with Lantern")
    assert new["status"] == "ACTIVE"
    # Stats updated
    assert new_state[S.MEMORY_STATS]["superseded"] == 1
    assert new_state[S.MEMORY_STATS]["new"] == 1


def test_record_memory_ignores_nonexistent_supersede_title():
    """If supersedes_titles names a title that doesn't exist, skip it gracefully."""
    mock_client = MagicMock()
    mock_client.create.return_value = MemorySynthesisResponse(
        should_remember=True, category="NOTE",
        memory_title="New Memory",
        memory_text="Some insight.",
        persistence="permanent", status="ACTIVE", reasoning="test",
        supersedes_titles=["Nonexistent Title"],
    )
    state = State({
        S.PRE_LOCATION_ID: 10, S.PRE_LOCATION_NAME: "West",
        S.PRE_SCORE: 0, S.PRE_INVENTORY: [],
        S.LOCATION_ID: 10, S.SCORE: 5, S.INVENTORY: [],
        S.GAME_OVER: False, S.GAME_OVER_REASON: "",
        S.GAME_RESPONSE: "Something happened.",
        S.ACTION_TO_TAKE: "look", S.AGENT_REASONING: "check",
        S.ACTION_HISTORY: [], S.MEMORIES_BY_LOCATION: {},
        S.EPISODE_ID: "ep-1", S.TURN_COUNT: 3,
        S.MEMORY_STATS: {"new": 0, "dedup_rejected": 0, "superseded": 0},
    })
    result, new_state = record_memory.run(state, client=mock_client, config=MagicMock(memory_model="test"))
    assert result["synthesized"] is True
    assert new_state[S.MEMORY_STATS]["superseded"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_memory.py::test_record_memory_supersedes_old_memory tests/test_actions/test_memory.py::test_record_memory_ignores_nonexistent_supersede_title -v`

Expected: FAIL — supersession logic doesn't exist yet.

- [ ] **Step 3: Implement supersession processing**

In `zorkburr/actions/memory.py`, in `record_memory`, after the dedup guard block and before creating the `Memory` instance, add supersession processing:

```python
            # Process supersession: mark old memories as replaced
            superseded_count = 0
            if response.supersedes_titles:
                for old_title in response.supersedes_titles:
                    found = False
                    for m in loc_list:
                        if m.get("title") == old_title and m.get("status") != "SUPERSEDED":
                            m["status"] = "SUPERSEDED"
                            m["superseded_by"] = response.memory_title
                            logger.info(f"Superseded memory '{old_title}' with '{response.memory_title}' at location {loc_key}")
                            superseded_count += 1
                            found = True
                            break
                    if not found:
                        logger.debug(f"Supersede target not found: '{old_title}' at location {loc_key}")
```

Then update the stats tracking in the successful return to include superseded count:

```python
            stats = dict(state[S.MEMORY_STATS])
            stats["new"] = stats.get("new", 0) + 1
            stats["superseded"] = stats.get("superseded", 0) + superseded_count
            return {"synthesized": True, "memory_title": mem.title}, state.update(
                **{S.MEMORIES_BY_LOCATION: all_mems, S.MEMORY_STATS: stats}
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_memory.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/actions/memory.py tests/test_actions/test_memory.py
git commit -m "feat(memory): process supersession in record_memory"
```

---

## Task 9: Supersession Rules in Synthesis Prompt (2E)

**Files:**
- Modify: `prompts/memory_synthesis.md`

- [ ] **Step 1: Add supersession rules to synthesis prompt**

Append after the DEDUPLICATION block added in Task 1:

```markdown

SUPERSESSION — replacing outdated memories:
- If your new memory CONTRADICTS or IMPROVES on an existing memory, list that memory's exact title in supersedes_titles
- You MUST copy the exact title from the "Existing memories" list — character-for-character
- Do NOT paraphrase, rephrase, or invent titles that look similar
- Examples:
  - Existing: "[Dark Staircase Leads to Death]: Going down without light is fatal"
    -> You discover it's safe with lantern
    -> supersede with "Safe Descent with Lantern"
  - Existing: "[Troll Blocks Passage]: Troll blocks passage — attack with sword to defeat it"
    -> You kill the troll
    -> DO NOT supersede (the troll resets each episode, the original memory is still valid guidance)
- Only supersede when the existing memory gives WRONG advice, not just when you have a related observation
```

- [ ] **Step 2: Commit**

```bash
git add prompts/memory_synthesis.md
git commit -m "feat(memory): add supersession rules to synthesis prompt"
```

---

## Task 10: Consolidation Response Model (3B)

**Files:**
- Modify: `zorkburr/llm/models.py`
- Test: `tests/test_actions/test_consolidation.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_actions/test_consolidation.py`:

```python
"""Tests for memory consolidation models and processing."""
from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse


def test_consolidation_action_keep():
    a = ConsolidationAction(action="keep", memory_title="Found Sword", reason="useful")
    assert a.action == "keep"
    assert a.merge_with == ""
    assert a.new_text == ""
    assert a.new_title == ""


def test_consolidation_action_merge():
    a = ConsolidationAction(
        action="merge", memory_title="Window Open",
        merge_with="Window Ajar", new_title="Enter via Window",
        new_text="Open window behind house to reach Kitchen.",
        reason="duplicate info",
    )
    assert a.action == "merge"
    assert a.merge_with == "Window Ajar"
    assert a.new_title == "Enter via Window"


def test_consolidation_action_drop():
    a = ConsolidationAction(action="drop", memory_title="Room Description", reason="low value")
    assert a.action == "drop"


def test_consolidation_action_supersede():
    a = ConsolidationAction(
        action="supersede", memory_title="Wrong Info",
        merge_with="Correct Info", reason="contradicted by evidence",
    )
    assert a.action == "supersede"
    assert a.merge_with == "Correct Info"


def test_consolidation_response():
    r = ConsolidationResponse(actions=[
        ConsolidationAction(action="keep", memory_title="A", reason="good"),
        ConsolidationAction(action="drop", memory_title="B", reason="junk"),
    ])
    assert len(r.actions) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_consolidation.py -v`

Expected: FAIL — `ConsolidationAction` and `ConsolidationResponse` don't exist.

- [ ] **Step 3: Add consolidation models**

In `zorkburr/llm/models.py`, add after `MemorySynthesisResponse`:

```python
class ConsolidationAction(BaseModel):
    action: str = Field(description="keep|drop|merge|supersede")
    memory_title: str = Field(description="Exact title of existing memory being acted on")
    merge_with: str = Field(default="", description="Title of the other memory (for 'merge' and 'supersede')")
    new_text: str = Field(default="", description="Rewritten text (for 'merge' only)")
    new_title: str = Field(default="", description="Title for merged memory (for 'merge' only)")
    reason: str = Field(description="Why this action was chosen")

class ConsolidationResponse(BaseModel):
    actions: list[ConsolidationAction]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_consolidation.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add zorkburr/llm/models.py tests/test_actions/test_consolidation.py
git commit -m "feat(memory): add ConsolidationAction and ConsolidationResponse models"
```

---

## Task 11: Consolidation Prompt (3D)

**Files:**
- Create: `prompts/memory_consolidation.md`

- [ ] **Step 1: Create the consolidation prompt**

Create `prompts/memory_consolidation.md`:

```markdown
You are consolidating memories for a single location in a text adventure game.
The game resets each episode — these memories are reusable guidance, not current state.

You will receive all memories at one location. Return an action for EVERY non-superseded memory.

Actions:
- keep: Memory is useful and unique. No change needed.
- drop: Memory is low-value (room description, movement log, inventory noise, score change without context). Will be permanently deleted.
- merge: Two memories say the same thing in different words. Combine into one with the best text. Specify merge_with (the other memory's title), new_title, and new_text.
- supersede: One memory gives wrong advice that another memory corrects. Put the WRONG memory's title in memory_title and the CORRECT memory's title in merge_with.

Rules:
- Every non-superseded memory MUST get exactly one action
- Do NOT add new information — only reorganize what exists
- Do NOT merge memories that cover different topics just because they're at the same location
- PRESERVE memories that tell the agent what to DO (puzzle solutions, danger warnings, item uses)
- When merging, the new_text should be the better of the two, not a combination of both
- Copy all memory titles character-for-character from the provided list
```

- [ ] **Step 2: Commit**

```bash
git add prompts/memory_consolidation.md
git commit -m "feat(memory): add consolidation prompt for end-of-episode cleanup"
```

---

## Task 12: Consolidation Processing + Backup (3A, 3C, 3E)

**Files:**
- Modify: `zorkburr/actions/episode.py` (add `consolidate_memories` function, backup, call from `finalize_episode`)
- Test: `tests/test_actions/test_consolidation.py`

- [ ] **Step 1: Write the failing tests for consolidation action processing**

Add to `tests/test_actions/test_consolidation.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

from zorkburr.actions.episode import apply_consolidation_actions, consolidate_location
from zorkburr.llm.models import ConsolidationAction


class TestApplyConsolidationActions:
    def test_keep_action(self):
        mems = [
            {"title": "Found Sword", "text": "Sword in trophy case.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 5},
        ]
        actions = [ConsolidationAction(action="keep", memory_title="Found Sword", reason="useful")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 1
        assert result[0]["title"] == "Found Sword"
        assert stats["kept"] == 1

    def test_drop_action(self):
        mems = [
            {"title": "Room Desc", "text": "A plain room.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "ephemeral", "episode": "ep-1", "turn": 2},
        ]
        actions = [ConsolidationAction(action="drop", memory_title="Room Desc", reason="junk")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len(result) == 0
        assert stats["dropped"] == 1

    def test_merge_action(self):
        mems = [
            {"title": "Window Open", "text": "Window behind house is open.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-1", "turn": 3},
            {"title": "Window Ajar", "text": "The window is ajar.", "status": "ACTIVE",
             "category": "DISCOVERY", "persistence": "permanent", "episode": "ep-2", "turn": 5},
        ]
        actions = [
            ConsolidationAction(
                action="merge", memory_title="Window Open", merge_with="Window Ajar",
                new_title="Enter via Window", new_text="Open window behind house to reach Kitchen.",
                reason="duplicates",
            ),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        # Both originals superseded, one new memory created
        superseded = [m for m in result if m["status"] == "SUPERSEDED"]
        active = [m for m in result if m["status"] == "ACTIVE"]
        assert len(superseded) == 2
        assert len(active) == 1
        assert active[0]["title"] == "Enter via Window"
        assert active[0]["episode"] == "consolidated"
        assert stats["merged"] == 1

    def test_supersede_action(self):
        mems = [
            {"title": "Wrong Info", "text": "Bad advice.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 2},
            {"title": "Correct Info", "text": "Good advice.", "status": "ACTIVE",
             "category": "SUCCESS", "persistence": "permanent", "episode": "ep-2", "turn": 4},
        ]
        actions = [
            ConsolidationAction(
                action="supersede", memory_title="Wrong Info",
                merge_with="Correct Info", reason="contradicted",
            ),
            ConsolidationAction(action="keep", memory_title="Correct Info", reason="accurate"),
        ]
        result, stats = apply_consolidation_actions(mems, actions)
        wrong = next(m for m in result if m["title"] == "Wrong Info")
        assert wrong["status"] == "SUPERSEDED"
        assert wrong["superseded_by"] == "Correct Info"
        assert stats["superseded"] == 1

    def test_missing_memory_defaults_to_keep(self):
        """Memories not mentioned in actions are kept by default."""
        mems = [
            {"title": "Mentioned", "text": "x", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 1},
            {"title": "Unmentioned", "text": "y", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": 2},
        ]
        actions = [ConsolidationAction(action="keep", memory_title="Mentioned", reason="good")]
        result, stats = apply_consolidation_actions(mems, actions)
        assert len([m for m in result if m["status"] == "ACTIVE"]) == 2
        assert stats["kept"] == 2  # 1 explicit + 1 default
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_consolidation.py::TestApplyConsolidationActions -v`

Expected: FAIL — `apply_consolidation_actions` doesn't exist.

- [ ] **Step 3: Implement `apply_consolidation_actions`**

In `zorkburr/actions/episode.py`, add after the existing imports:

```python
import shutil
import instructor
from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse
```

Then add the function:

```python
def apply_consolidation_actions(
    memories: list[dict],
    actions: list[ConsolidationAction],
) -> tuple[list[dict], dict]:
    """Apply consolidation actions to a location's memory list.

    Returns (updated_memories, stats_dict).
    """
    stats = {"kept": 0, "dropped": 0, "merged": 0, "superseded": 0}
    # Index actions by title for lookup
    action_by_title = {a.memory_title: a for a in actions}
    # Track which memories have been processed
    processed_titles = set()
    result = list(memories)  # shallow copy

    for act in actions:
        if act.action == "keep":
            stats["kept"] += 1
            processed_titles.add(act.memory_title)

        elif act.action == "drop":
            result = [m for m in result if m.get("title") != act.memory_title]
            logger.warning(f"Consolidation dropped memory: {act.memory_title} — {act.reason}")
            stats["dropped"] += 1
            processed_titles.add(act.memory_title)

        elif act.action == "merge":
            # Mark both source memories as SUPERSEDED
            for m in result:
                if m.get("title") in (act.memory_title, act.merge_with) and m.get("status") != "SUPERSEDED":
                    m["status"] = "SUPERSEDED"
                    m["superseded_by"] = act.new_title
            # Create merged memory — category from the primary memory
            primary = next((m for m in memories if m.get("title") == act.memory_title), None)
            merged = {
                "category": primary.get("category", "NOTE") if primary else "NOTE",
                "title": act.new_title,
                "text": act.new_text,
                "episode": "consolidated",
                "turn": 0,
                "persistence": "permanent",
                "status": "ACTIVE",
                "superseded_by": "",
            }
            result.append(merged)
            logger.warning(
                f"Consolidation merged '{act.memory_title}' + '{act.merge_with}' -> '{act.new_title}' — {act.reason}"
            )
            stats["merged"] += 1
            processed_titles.add(act.memory_title)
            processed_titles.add(act.merge_with)

        elif act.action == "supersede":
            for m in result:
                if m.get("title") == act.memory_title and m.get("status") != "SUPERSEDED":
                    m["status"] = "SUPERSEDED"
                    m["superseded_by"] = act.merge_with
                    logger.info(f"Consolidation superseded '{act.memory_title}' by '{act.merge_with}' — {act.reason}")
            stats["superseded"] += 1
            processed_titles.add(act.memory_title)

    # Default-keep any non-superseded memories not mentioned in actions
    for m in result:
        if m.get("title") not in processed_titles and m.get("status") != "SUPERSEDED":
            stats["kept"] += 1

    return result, stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_consolidation.py -v`

Expected: ALL PASS

- [ ] **Step 5: Write the failing test for `consolidate_location`**

Add to `tests/test_actions/test_consolidation.py`:

```python
class TestConsolidateLocation:
    def test_calls_llm_and_applies_actions(self):
        mock_client = MagicMock()
        mock_client.create.return_value = ConsolidationResponse(actions=[
            ConsolidationAction(action="keep", memory_title="Good Memory", reason="useful"),
            ConsolidationAction(action="drop", memory_title="Junk Memory", reason="noise"),
        ])
        mems = [
            {"title": "Good Memory", "text": "Useful.", "status": "ACTIVE",
             "category": "SUCCESS", "persistence": "permanent", "episode": "ep-1", "turn": 1},
            {"title": "Junk Memory", "text": "Noise.", "status": "ACTIVE",
             "category": "NOTE", "persistence": "ephemeral", "episode": "ep-1", "turn": 2},
        ]
        result, stats = consolidate_location(
            location_id="10", memories=mems, knowledge_base="# KB",
            client=mock_client, config=MagicMock(analysis_model="test"),
        )
        assert len(result) == 1
        assert result[0]["title"] == "Good Memory"
        assert stats["dropped"] == 1
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_actions/test_consolidation.py::TestConsolidateLocation -v`

Expected: FAIL — `consolidate_location` doesn't exist.

- [ ] **Step 7: Implement `consolidate_location`**

Add to `zorkburr/actions/episode.py`:

```python
from zorkburr.llm.client import effective_model, thinking_kwargs
from zorkburr.llm.prompts import load_prompt

_consolidation_prompt: str | None = None

def _get_consolidation_prompt() -> str:
    global _consolidation_prompt
    if _consolidation_prompt is None:
        _consolidation_prompt = load_prompt("memory_consolidation")
    return _consolidation_prompt


def consolidate_location(
    location_id: str,
    memories: list[dict],
    knowledge_base: str,
    client: instructor.Instructor,
    config: GameConfig,
) -> tuple[list[dict], dict]:
    """Run consolidation LLM on one location's memories. Returns (updated_memories, stats)."""
    # Build context: all memories with status markers
    mem_lines = []
    for m in memories:
        status_tag = " [SUPERSEDED]" if m.get("status") == "SUPERSEDED" else ""
        mem_lines.append(f"- [{m.get('title', '?')}]{status_tag}: {m.get('text', '')}")

    context = (
        f"Location ID: {location_id}\n\n"
        f"Memories:\n" + "\n".join(mem_lines) + "\n\n"
        f"Current Knowledge Base:\n{knowledge_base or '(empty)'}"
    )

    response: ConsolidationResponse = client.create(
        model=effective_model(config, config.analysis_model),
        response_model=ConsolidationResponse,
        messages=[
            {"role": "system", "content": _get_consolidation_prompt()},
            {"role": "user", "content": context},
        ],
        temperature=0.3, max_tokens=2048, max_retries=2,
        **thinking_kwargs(config, False),
    )

    return apply_consolidation_actions(memories, response.actions)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_consolidation.py -v`

Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add zorkburr/actions/episode.py tests/test_actions/test_consolidation.py
git commit -m "feat(memory): add consolidation action processing and LLM call"
```

---

## Task 13: Wire Consolidation into finalize_episode (3A, 3E)

**Files:**
- Modify: `zorkburr/actions/episode.py:90-116` (add backup + consolidation call to `finalize_episode`)
- Modify: `run_episode.py` (add CONSOLIDATION log line support)
- Test: `tests/test_actions/test_episode.py`

- [ ] **Step 1: Write the failing test for backup**

Add to `tests/test_actions/test_episode.py`:

```python
class TestConsolidationInFinalize:
    def test_creates_backup_before_consolidation(self, tmp_path):
        """finalize_episode should create memories.json.bak before consolidating."""
        cfg = _config(tmp_path)
        # Write initial memories (6 at one location to trigger consolidation)
        mems = {"10": [
            {"title": f"Mem {i}", "text": f"Text {i}", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": i}
            for i in range(6)
        ]}
        Path(cfg.memory_file).write_text(json.dumps(mems))

        state = create_initial_state("ep-test").update(**{
            S.MAP_DATA: {},
            S.KNOWLEDGE_BASE: "# KB",
            S.MEMORIES_BY_LOCATION: mems,
        })

        # Mock the LLM client to return all-keep actions
        from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse
        mock_client = MagicMock()
        mock_client.create.return_value = ConsolidationResponse(
            actions=[ConsolidationAction(action="keep", memory_title=f"Mem {i}", reason="good") for i in range(6)]
        )

        finalize_episode(state, cfg, client=mock_client)

        # Backup should exist
        bak_path = Path(cfg.memory_file + ".bak")
        assert bak_path.exists()
        # Backup content should match original
        assert json.loads(bak_path.read_text()) == mems

    def test_skips_consolidation_for_small_locations(self, tmp_path):
        """Locations with fewer than 5 non-SUPERSEDED memories should not be consolidated."""
        cfg = _config(tmp_path)
        mems = {"10": [
            {"title": f"Mem {i}", "text": f"Text {i}", "status": "ACTIVE",
             "category": "NOTE", "persistence": "permanent", "episode": "ep-1", "turn": i}
            for i in range(3)
        ]}
        Path(cfg.memory_file).write_text(json.dumps(mems))

        state = create_initial_state("ep-test").update(**{
            S.MAP_DATA: {},
            S.KNOWLEDGE_BASE: "# KB",
            S.MEMORIES_BY_LOCATION: mems,
        })

        mock_client = MagicMock()
        finalize_episode(state, cfg, client=mock_client)

        # LLM should NOT have been called for consolidation
        # (it may have been called for KB update — check call args)
        for call in mock_client.create.call_args_list:
            if call.kwargs.get("response_model") == ConsolidationResponse:
                raise AssertionError("Should not call consolidation for <5 memories")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions/test_episode.py::TestConsolidationInFinalize -v`

Expected: FAIL — no backup created, no consolidation integration.

- [ ] **Step 3: Implement consolidation in finalize_episode**

Replace `finalize_episode` in `zorkburr/actions/episode.py`:

```python
def finalize_episode(state: State, config: GameConfig, client=None) -> dict:
    """Save map and knowledge to disk for cross-episode persistence.

    If *client* is provided, regenerates the KB with full episode data
    before persisting, then runs memory consolidation on locations
    with 5+ active memories.

    Returns an episode summary dict.
    """
    if client is not None:
        try:
            from zorkburr.actions.knowledge import update_knowledge
            _, state = update_knowledge.run(state, client=client, config=config, use_thinking=False)
        except Exception:
            logger.warning("Final KB update failed; persisting existing KB")

    persist_map(state[S.MAP_DATA], config)
    persist_knowledge(state[S.KNOWLEDGE_BASE], config)

    # Run memory consolidation if client is available
    all_mems = dict(state[S.MEMORIES_BY_LOCATION])
    if client is not None and all_mems:
        # Backup before consolidation
        mem_path = Path(config.memory_file)
        if mem_path.exists():
            shutil.copy2(mem_path, str(mem_path) + ".bak")
            logger.info(f"Created pre-consolidation backup: {mem_path}.bak")

        kb = state[S.KNOWLEDGE_BASE]
        for loc_key, loc_mems in list(all_mems.items()):
            active_count = sum(1 for m in loc_mems if m.get("status") != "SUPERSEDED")
            if active_count < 5:
                continue
            try:
                updated, stats = consolidate_location(
                    location_id=loc_key, memories=loc_mems,
                    knowledge_base=kb, client=client, config=config,
                )
                all_mems[loc_key] = updated
                before = len(loc_mems)
                after = sum(1 for m in updated if m.get("status") != "SUPERSEDED")
                logger.info(
                    f"CONSOLIDATION | location={loc_key} | before={before} | after={after}"
                    f" | kept={stats['kept']} | merged={stats['merged']}"
                    f" | dropped={stats['dropped']} | superseded={stats['superseded']}"
                )
            except Exception as e:
                logger.warning(f"Consolidation failed for location {loc_key}: {e}")

    persist_memories(all_mems, config)

    return {
        "episode_id": state[S.EPISODE_ID],
        "turns": state[S.TURN_COUNT],
        "score": state[S.SCORE],
        "max_score": state[S.MAX_SCORE],
        "reason": state[S.GAME_OVER_REASON],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions/test_episode.py -v`

Expected: ALL PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ --ignore=tests/test_llm_client.py -v`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add zorkburr/actions/episode.py run_episode.py tests/test_actions/test_episode.py
git commit -m "feat(memory): wire consolidation into finalize_episode with backup and logging"
```

---

## Task 14: Final Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ --ignore=tests/test_llm_client.py -v`

Expected: ALL PASS

- [ ] **Step 2: Verify no import errors**

Run: `uv run python -c "from zorkburr.actions.memory import record_memory; from zorkburr.actions.episode import finalize_episode, consolidate_location, apply_consolidation_actions; from zorkburr.llm.models import ConsolidationAction, ConsolidationResponse; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
# If clean, no commit needed. If there are changes:
git add -A
git commit -m "chore: final cleanup for memory system improvements"
```
