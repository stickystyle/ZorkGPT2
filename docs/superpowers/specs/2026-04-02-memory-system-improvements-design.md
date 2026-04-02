# Memory System Improvements — Design Spec

Refined from `docs/memory-system-plan.md`. Addresses duplicate accumulation, missing supersession, unused persistence/status fields, and lack of end-of-episode cleanup.

## Current State

ZorkGPT2 has two learning systems:
- **Location memories** (`MEMORIES_BY_LOCATION`): per-location records synthesized by LLM on score change, location change, or death. Persisted to `data/memories.json`. Capped at 10 per location in agent context.
- **Knowledge base** (`KNOWLEDGE_BASE`): periodic strategic summary from action history (every 25 turns). Persisted to `data/knowledge.md`.

Both feed into `assemble_context` (`zorkburr/actions/context.py`). Adjacent-room memories (1-hop via MapGraph) are already implemented.

### Known Problems

1. **Duplicate memories accumulate** — location 74 has three near-identical "Behind House Window" memories across episodes. The LLM ignores dedup guidance.
2. **No supersession** — when a memory is proven wrong or improved upon, the old one stays forever.
3. **`persistence` field is write-only** — LLM sets core/permanent/ephemeral but nothing reads it.
4. **`status` field is write-only** — SUPERSEDED value exists in the model but is never set or filtered in `assemble_context`.
5. **No end-of-episode cleanup** — memories accumulate without consolidation.

---

## Phase 1: Prompt + Guard Rails (no architecture changes)

Five independent items. No dependencies between them.

### 1A. Synthesis Prompt Dedup Rules

**File:** `prompts/memory_synthesis.md`

Add after the existing DO NOT rules:

```
DEDUPLICATION — do NOT create memories that duplicate existing ones:
- EXACT DUPLICATES: If an existing memory has the same title, do not create another
- SEMANTIC DUPLICATES: If an existing memory conveys the same insight in different words, do not create another
  - BAD: Existing says "Window ajar behind house" -> you create "Behind house window is ajar" (same fact, different words)
  - GOOD: Existing says "Window ajar behind house" -> you create "Enter window to reach Kitchen (+10 points)" (new actionable info)
- If your new observation adds meaningful detail to an existing memory, supersede it with a better version instead of creating a separate entry
```

### 1B. Exact-Title Dedup Guard

**File:** `zorkburr/actions/memory.py`

In `record_memory`, before appending the new memory:

```python
if response.should_remember:
    existing_titles = {m.get("title") for m in loc_list if m.get("status") != "SUPERSEDED"}
    if response.memory_title in existing_titles:
        logger.info(f"Rejected duplicate memory title: '{response.memory_title}' at location {loc_key}")
        return {"synthesized": False, "reason": "duplicate_title"}, state
```

Increment `mem_dedup_rejected` counter for observability (1E).

### 1C. Ephemeral Pruning on Episode Load

**File:** `zorkburr/actions/episode.py`

In `initialize_episode`, after loading memories, strip ephemeral ones from prior episodes:

```python
if "memories_by_location" in overrides:
    cleaned = {}
    dropped = 0
    for loc_key, mems in overrides["memories_by_location"].items():
        kept = [m for m in mems if m.get("persistence") != "ephemeral"]
        dropped += len(mems) - len(kept)
        if kept:
            cleaned[loc_key] = kept
    overrides["memories_by_location"] = cleaned
    if dropped:
        logger.info(f"Pruned {dropped} ephemeral memories from previous episodes")
```

### 1D. Filter SUPERSEDED in Context Assembly

**File:** `zorkburr/actions/context.py`

Filter `status != "SUPERSEDED"` from both current-location and adjacent-room memory blocks. This matches what `record_memory` already does for its own synthesis context — `assemble_context` is currently inconsistent.

In the current-location block:

```python
loc_mems = [m for m in memories[loc_key] if m.get("status") != "SUPERSEDED"]
```

Same filter when iterating `memories[neighbor_key]` for adjacent rooms.

### 1E. Observability: Memory Stats on EPISODE_END

**File:** `run_episode.py` or `finalize_episode`

Track counters during the episode and append to the existing `EPISODE_END` structured log line:

```
EPISODE_END | ... | mem_total=142 | mem_new=3 | mem_dedup_rejected=2 | mem_ephemeral_pruned=5
```

Counters: `mem_total` (after pruning), `mem_new` (created this episode), `mem_dedup_rejected` (blocked by 1B), `mem_ephemeral_pruned` (removed by 1C).

---

## Phase 2: Supersession

Depends on: Phase 1 (dedup guard and SUPERSEDED filter should exist first).

### 2A. Add `supersedes_titles` to Response Model

**File:** `zorkburr/llm/models.py`

```python
class MemorySynthesisResponse(BaseModel):
    # ... existing fields ...
    supersedes_titles: list[str] = Field(
        default_factory=list,
        description="Exact titles of existing memories this replaces. Copy titles verbatim from the existing memories list."
    )
```

### 2B. Expose Titles in Synthesis Context

**File:** `zorkburr/actions/memory.py`

Change the memory format passed to the synthesis LLM from:

```
- {text}
```

to:

```
- [{title}]: {text}
```

This is the prerequisite for the LLM to return exact titles in `supersedes_titles`.

### 2C. Add `superseded_by` to Memory Dataclass

**File:** `zorkburr/actions/memory.py`

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
    superseded_by: str = ""  # Title of memory that replaced this one
```

### 2D. Process Supersession in `record_memory`

**File:** `zorkburr/actions/memory.py`

After the dedup guard (1B) passes and before appending the new memory:

```python
if response.supersedes_titles:
    for old_title in response.supersedes_titles:
        for m in loc_list:
            if m.get("title") == old_title and m.get("status") != "SUPERSEDED":
                m["status"] = "SUPERSEDED"
                m["superseded_by"] = response.memory_title
                logger.info(f"Superseded memory '{old_title}' with '{response.memory_title}' at location {loc_key}")
```

Increment `mem_superseded` counter for observability.

### 2E. Supersession Rules in Synthesis Prompt

**File:** `prompts/memory_synthesis.md`

Add after the dedup rules:

```
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

### Phase 2 Observability

Add `mem_superseded` counter to the EPISODE_END log line:

```
EPISODE_END | ... | mem_superseded=1
```

---

## Phase 3: End-of-Episode Consolidation

Depends on: Phase 2 (consolidator uses supersession to mark memories).

A new step in `finalize_episode` that deduplicates and cleans up memories after each episode.

### 3A. Pre-Consolidation Backup

**File:** `zorkburr/actions/episode.py`

Before consolidation runs, copy `memories.json` to `memories.json.bak`. One snapshot per episode (overwritten each time — the previous episode's backup is stale once new memories exist).

### 3B. Consolidation Response Model

**File:** `zorkburr/llm/models.py`

```python
class ConsolidationAction(BaseModel):
    action: str = Field(description="keep|drop|merge|supersede")
    memory_title: str = Field(description="Exact title of existing memory being acted on")
    merge_with: str = Field(default="", description="Title of the other memory (for 'merge' only)")
    new_text: str = Field(default="", description="Rewritten text (for 'merge' only)")
    new_title: str = Field(default="", description="Title for merged memory (for 'merge' only)")
    reason: str = Field(description="Why this action was chosen")

class ConsolidationResponse(BaseModel):
    actions: list[ConsolidationAction]
```

**Validation rule:** Every non-SUPERSEDED memory at the location must appear exactly once in the actions list. If a memory is missing from the response, it defaults to "keep".

### 3C. Action Processing

**File:** `zorkburr/actions/episode.py` (new function)

For each location with 5+ non-SUPERSEDED memories, call the analysis model with all memories at that location (including SUPERSEDED for context, clearly marked) plus the current KB.

Action semantics:

- **keep**: No change.
- **drop**: Remove from list. Log at WARNING with full memory content.
- **merge**: Mark both source memories SUPERSEDED (`superseded_by = new_title`). Create a new memory with `episode = "consolidated"`, the new title/text, category from the primary memory (the one named in `memory_title`, not `merge_with`), `persistence = "permanent"`, `status = "ACTIVE"`. Log at WARNING with both originals and the merged result.
- **supersede**: The memory in `memory_title` is the loser — mark it SUPERSEDED. `merge_with` names the winning memory that replaces it (set as `superseded_by`). Log at INFO.

After processing all actions, persist the updated memories to disk.

### 3D. Consolidation Prompt

**File:** `prompts/memory_consolidation.md`

```
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

### 3E. Observability: CONSOLIDATION Log Line

Per-location log line:

```
CONSOLIDATION | location={id} | before={n} | after={n} | kept={n} | merged={n} | dropped={n} | superseded={n}
```

Add `mem_consolidated` counter to the EPISODE_END log line (total memories affected by consolidation across all locations).

---

## Implementation Order

| Phase | Item | Effort | Impact | Dependencies |
|---|---|---|---|---|
| 1 | 1A: Synthesis dedup prompt rules | Prompt-only | Prevents new duplicates | None |
| 1 | 1B: Exact-title dedup guard | ~10 lines | Safety net for LLM failures | None |
| 1 | 1C: Ephemeral pruning on load | ~10 lines | Cleans up low-value memories | None |
| 1 | 1D: Filter SUPERSEDED in context | ~5 lines | Correctness fix | None |
| 1 | 1E: Memory stats on EPISODE_END | ~15 lines | Observability baseline | None |
| 2 | 2A: `supersedes_titles` on response model | ~3 lines | Enables supersession | None |
| 2 | 2B: Expose titles in synthesis context | ~3 lines | LLM can reference memories by title | None |
| 2 | 2C: `superseded_by` on Memory dataclass | ~3 lines | Tracks what replaced what | None |
| 2 | 2D: Process supersession in record_memory | ~15 lines | Memories self-correct | 2A, 2C |
| 2 | 2E: Supersession prompt rules | Prompt-only | Teaches LLM when/how to supersede | 2A, 2B |
| 3 | 3A: Pre-consolidation backup | ~5 lines | Safety net | None |
| 3 | 3B: Consolidation response model | ~15 lines | Structured consolidator output | None |
| 3 | 3C: Action processing | ~60 lines | Dedup + cleanup across episodes | 3B, Phase 2 |
| 3 | 3D: Consolidation prompt | Prompt-only | Guides the consolidator | None |
| 3 | 3E: CONSOLIDATION log line | ~10 lines | Per-location audit trail | 3C |

Phase 1 items are independent and ship together. Phase 2 items 2A-2C are independent; 2D and 2E depend on them. Phase 3 depends on Phase 2 (consolidator uses supersession).

---

## What NOT to Build

- **TENTATIVE confirmation/promotion** — The LLM never produces TENTATIVE memories. If the consolidator (3D) starts producing them, revisit then.
- **TENTATIVE display differentiation** — No point building display logic for a status that is never created. Revisit alongside TENTATIVE confirmation if needed.
- **`invalidation_reason` field** — Supersession via `superseded_by` is enough.
- **Per-turn LLM memory retrieval** — Location-keying + adjacent-room retrieval is the right index for a spatial game.
- **Memory-to-KB promotion** — The KB rebuilds from action history every 25 turns. If the agent keeps rediscovering something, it shows up in the action log and the KB captures it naturally. Revisit only if there's a concrete scenario where important cross-episode patterns aren't reaching the agent.
