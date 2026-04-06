# AI Game-Playing Research Survey

Research compiled 2026-04-05 for the ZorkBurr project. Covers adjacent projects where LLMs play video games and text adventures, with analysis of techniques applicable to Zork I.

---

## Table of Contents

1. [Claude Plays Pokemon](#claude-plays-pokemon)
2. [Gemini Plays Pokemon](#gemini-plays-pokemon)
3. [LLMs Playing Text Adventures](#llms-playing-text-adventures)
4. [LLM Game-Playing in Other Domains](#llm-game-playing-in-other-domains)
5. [Academic Papers — Memory and Planning Architectures](#academic-papers--memory-and-planning-architectures)
6. [Why Zork Is Harder Than Pokemon](#why-zork-is-harder-than-pokemon)
7. [Key Takeaways for ZorkBurr](#key-takeaways-for-zorkburr)
8. [Sources](#sources)

---

## Claude Plays Pokemon

### Background

Created by **David Hershey**, an engineer on Anthropic's Applied AI team, as a side project starting June 2024. Publicly launched February 2025 alongside Claude 3.7 Sonnet's extended thinking capability. Livestreamed on Twitch at twitch.tv/claudeplayspokemon. Framed not as a product but as an unconventional benchmark — one that tests sustained, coherent agentic behavior over thousands of actions, something traditional math/reasoning benchmarks cannot capture.

### Architecture — The Game Loop

The architecture is **deliberately simple**. Hershey has said he stripped complexity out over time rather than adding it.

1. **Capture game state**: Take a screenshot from the PyBoy emulator (Game Boy emulator in Python), and read structured game data from Pokemon Red's RAM via a `PokemonRedReader` class.
2. **Send to Claude**: The screenshot (PNG, base64-encoded, 2x upscaled) plus the RAM-extracted game state text (location, coordinates, party Pokemon with HP/level/moves/PP, inventory, badges, money, on-screen dialog) are sent as a user message in the conversation.
3. **Claude reasons and calls tools**: Claude receives the visual + structured input and decides what to do. It outputs reasoning text followed by one or more tool calls.
4. **Execute tool calls**: The system executes button presses or navigation on the emulator, captures a new screenshot + state, and returns them as tool results.
5. **Repeat**: The assistant response and tool results are appended to the message history. Loop back to step 3 (Claude may chain multiple tool calls in one turn).
6. **Summarize when context grows**: When message history hits a threshold (~60 messages in the starter code, ~30 actions in the production system), trigger summarization to compress the history.

**Config** (from the starter repo): Model is `claude-3-7-sonnet-20250219`, temperature `1.0`, max tokens `4000`. System prompt is minimal: tells Claude it is playing Pokemon Red, can see the game screen and use emulator commands, and its goal is to defeat the Elite Four. Instructs Claude to explain its reasoning briefly, then use tools.

### Tools Available to Claude

Claude has access to **three tools** (only two in the open-source starter, with navigator disabled by default):

**Tool 1: `press_buttons`** (called `use_emulator` in some descriptions)
- Accepts an array of button strings: `["a", "b", "start", "select", "up", "down", "left", "right"]`
- Optional `wait` boolean — controls whether to pause between presses (120 frames with wait, 10 without)
- Returns: screenshot + RAM-parsed game state overlay after execution

**Tool 2: `update_knowledge_base`**
- A self-managed persistent memory system embedded in the prompt
- Claude can **add**, **edit**, and **delete** entries
- The knowledge base is a dictionary with sections like `current_status`, `game_progress`, `current_objectives`, `inventory`
- Claude has **full control** over what to store and how to organize it
- This is the key mechanism for persisting information across summarization boundaries

**Tool 3: `navigate_to`** (conditional, controlled by `USE_NAVIGATOR` flag)
- Takes target `row` (0-8) and `col` (0-9) coordinates on a 9x10 grid
- Uses **A\* pathfinding** on a collision map extracted from the emulator
- The collision map is an ASCII grid showing walls, walkable paths, sprites, and player position with directional arrows
- Only available in overworld contexts (not in menus or battles)
- Compensates for Claude's poor spatial reasoning

### Memory and Learning Systems

Two layers:

**Short-term: Conversation History**
- The raw message history of Claude interactions and tool results
- This is the "working memory" — Claude can see recent actions, screenshots, and results
- Limited by context window (200K tokens for Claude 3.7 Sonnet)

**Long-term: Knowledge Base Tool**
- A structured dictionary that persists in the system prompt across summarization cycles
- Claude decides what to write — game facts it discovers (e.g., "Electric is super effective against Water"), current objectives, progress notes, inventory status
- This is the critical mechanism for maintaining coherence over 35,000+ actions
- A secondary LLM validates knowledge base accuracy after summarization

**Accordion-style Summarization**
- When conversation history exceeds the threshold (~30 actions):
  1. The full conversation is sent to Claude with a `SUMMARY_PROMPT`
  2. Claude generates a condensed summary covering: game events and milestones, key decisions, current objectives, location and team status, strategies
  3. The entire message history is **replaced** with a single user message containing the summary text + current screenshot + "continue playing"
  4. The knowledge base persists separately (it's in the system prompt, not the history)
- This creates a hierarchical compression: older information gets increasingly compressed while recent context stays detailed
- This cycle repeats indefinitely, enabling play across tens of thousands of interactions

### Decision-Making and Planning

**Extended thinking** is the key capability. Claude 3.7 Sonnet's ability to reason through multi-step plans before acting is what enabled it to progress beyond Pallet Town (where Claude 3.5 Sonnet got permanently stuck). The thinking process is visible on the Twitch stream's left panel.

**Strengths:**
- Good at short-term tactical reasoning (Pokemon battles, type matchups)
- Can try multiple strategies and question previous assumptions
- Can recover from errors — e.g., Opus 4.5 backtracked from Pokemon Mansion to Safari Zone after realizing it missed the Gold Teeth needed for STRENGTH

**Weaknesses:**
- **Poor executive function**: Abandons objectives after minor setbacks rather than adapting
- **Bad spatial reasoning**: Confuses walkable paths with walls, mistakes player character for NPCs, gets trapped in environmental puzzles
- **Memory decay**: Prematurely declares goals completed, forgets recorded information, attempts to interact with already-defeated trainers
- **Visual processing**: Confuses sprites, misidentifies buildings, fails to recognize when inputs produce no effect
- **No long-range planning**: Struggles with multi-step dependencies (e.g., the STRENGTH HM chain)

### Progress Over Time (Model Evolution)

| Model | Achievement | Notes |
|-------|------------|-------|
| Claude 3.0 Sonnet | Cannot leave starting house | Total failure |
| Claude 3.5 Sonnet | Cannot leave Pallet Town | Stuck immediately |
| Claude 3.7 Sonnet | 3 gym badges (~35,000 actions, ~140 compute hours) | First meaningful progress; stuck in Mt. Moon for 78+ hours across runs |
| Claude Opus 4.5 | All 8 badges, reached Victory Road (~230,000 steps) | Major breakthrough — beat Silph Co, Safari Zone, Pokemon Mansion; stuck on boulder puzzles |
| Claude Opus 4.6 | Still playing (as of April 2026) | Has not yet beaten the game |

### Key Design Insights

1. **The knowledge base as a self-managed tool is the most important design decision.** Rather than the system deciding what to remember, Claude itself chooses what to store, edit, and delete. This creates an emergent memory system where the model learns to maintain its own institutional knowledge.
2. **Simplicity wins.** Hershey explicitly says he removed complexity over time. The system prompt is short, the tools are minimal, and the agent framework is straightforward. The model's intelligence is the main driver, not elaborate scaffolding.
3. **Accordion summarization enables infinite-horizon play.** The compress-and-replace pattern lets Claude play indefinitely despite finite context windows. The knowledge base survives summarization because it lives in the system prompt, not in the conversation history.
4. **RAM reading as ground truth.** Rather than asking Claude to parse the screen for game state, the system reads Pokemon Red's RAM directly for badges, HP, inventory, location, coordinates, etc. Claude gets both the screenshot (for visual reasoning) and the structured data (for reliable facts). Analogous to ZorkBurr using Jericho as ground truth.
5. **Spatial reasoning remains the bottleneck.** The navigator tool with A\* pathfinding was added specifically because Claude cannot reliably navigate by pixel-level spatial reasoning. A scaffolding workaround for a fundamental model limitation.
6. **"Exhaust prompting before fine-tuning."** Hershey advocates pushing prompting as far as possible. The rapid iteration cycle (minutes vs weeks for training) makes it far more efficient for most agent use cases.
7. **Pokemon as an agent benchmark.** The project revealed model capabilities invisible to traditional benchmarks. Progress milestones (gym victories) require sustained coherent behavior over hours, exposing improvements between model versions that standard evaluations miss.

---

## Gemini Plays Pokemon

### Background

A parallel effort using Google's Gemini 2.5 Pro to play Pokemon Blue. Gemini beat Pokemon Blue before Claude beat Pokemon Red, though the developers of both projects caution against treating it as a model comparison due to significant differences in scaffolding and tools.

### Architecture

- Gemini 2.5 Pro received game state extracted from **RAM as text** (not raw pixels — Gemini struggled with pixel input)
- Used an **XML-based map model** updated during exploration for spatial memory
- A **"scratchpad of goals"** managed context and focus
- Two specialized tools: `pathfinder` (navigation using the XML map) and `boulder_puzzle_strategist` (specific puzzle solver)
- 1M token context window (vs Claude's 200K)

### Critical Findings

1. **Context poisoning**: If a hallucination entered the goals list, the model fixated on impossible objectives. This was their biggest challenge. Once bad information gets into persistent state, the model cannot reason its way out.

2. **Long-context degradation**: Beyond 100K tokens, the agent favored repeating actions from its history rather than synthesizing novel plans. Benchmark performance on long-context retrieval did NOT translate to effective planning. This is a major finding.

3. **Information control > raw perception**: Curated text extraction from RAM outperformed multimodal pixel input. Strategic context management mattered more than raw sensory data.

### Timeline

First run took 813 hours with constant tweaks. Second run took 406.5 hours.

### Relevance to ZorkBurr

The "context poisoning" problem and long-context degradation findings are directly applicable. ZorkBurr's approach of synthesizing memories rather than accumulating raw history is validated by their experience. Their finding that curated text beats raw data supports ZorkBurr's design of using Jericho's structured output.

---

## LLMs Playing Text Adventures

### Gerrits 2026 — "Playing With AI" (Zork I)

Already in the ZorkBurr repo (`docs/Playing With AI.pdf`). Key findings for context: all models scored under 75/350 points. Claude Opus 4.5 was the best performer. Detailed game instructions did not help. Extended thinking did not help.

**Core failure modes:**
- Repetitive actions
- Inability to learn from chat history
- "Lost in the middle" problem where earlier failures become invisible at long context lengths
- Dropping items needed later

**Relevance to ZorkBurr:** This paper is the strongest validation of ZorkBurr's architecture thesis. The zero-shot approach fails precisely because LLMs lack persistent memory across turns and metacognition. ZorkBurr's `MEMORIES_BY_LOCATION` and `KNOWLEDGE_BASE` systems directly address these gaps.

### Tseng et al. 2023 — "Can Large Language Models Play Text Games Well?"

- **arXiv:** 2304.02868
- **Architecture:** Tested ChatGPT on Zork I with three evaluation methods: world model assessment (reading walkthroughs to learn spatial relationships), goal inference, and direct gameplay with structured prompts showing game state and valid actions.
- **Results:** ChatGPT scored only 10 points base, 15 with action history reminders, 35-40 with human guidance. Spatial reasoning accuracy was 42.5% on seen locations, only 18.5% on unseen. Goal inference succeeded only 24% of the time.
- **Key failure modes:** World model collapse, goal confusion (conflating immediate actions with strategic objectives), passive/repetitive behavior, hallucinated walkthrough details.
- **What helped:** Action history reminders (anchoring the model to prior decisions) and structured prompts with clear action lists. Human guidance was the most effective intervention.
- **Relevance to ZorkBurr:** The memory system addresses the world model collapse problem. The 18.5% spatial accuracy on unseen locations validates why ZorkBurr builds `MAP_DATA` incrementally rather than relying on the LLM's internal knowledge.

### LPLH Framework (2025) — "Learning to Play Like Humans"

- **Paper:** ACL 2025 Findings (arXiv 2505.12439)
- **Authors:** Jinming Zhang (University of Essex), Yunfei Long (Queen Mary University of London)
- **Length:** 18 pages including appendices
- **Code:** No public repository released

#### Component 1: Dynamic Knowledge Graph (KG-Map)

A fine-tuned **Qwen2.5-1.5B-Instruct** (`fm_re`), trained via LoRA on LLaMA-Factory, extracts `<subject, relation, object>` triples from game text. Training data from 3 non-test games (Dragon, Karn, Night), annotated by GPT-4 then manually refined.

**Triple schema** (from Table 5 of the paper):
- **Location:** `<You, in, LocationName>` — always uses "in" for spatial presence
- **Objects:** `<[Location], have, object>` — interactive objects only, max 3-word names, ignore decorative details
- **Spatial connections:** `<current location, direction, [new location]>` — north/south/east/west/up/down
- **Dependencies:** `<location/object, need/require, something to action>` — e.g., `<Forest, need, machete to go west>`
- **Object-on-object:** `<sock, on, table>` for spatial relations between objects

**Update formula:**
```
I_k^o = fm_re(a_{k-1}, o_k)                         # extract triples from previous action + current observation
G_k = kg(G_{k-1}, a_{k-1}) ⊕ kg(G_{k-1}, I_k^o)    # merge action effects + new triples into graph
```

If the observation is insufficient (e.g., "Opened", "Taken"), outputs `|start| none |end|` and skips extraction. Represented as JSON, fed directly into the main LLM's prompt.

**Extraction accuracy:** 15% error rate on Zork1 validation. The authors acknowledge this as a limitation: "the consistency and clarity of this representation can influence the model's reasoning."

#### Component 2: Action Space Learning

The most architecturally distinctive and impactful component. Operates in two phases:

**Phase 1: Verb & Object Extraction** (`fm_vo`, also fine-tuned Qwen2.5-1.5B-Instruct)

After each action, checks whether it was valid based on the game's response. If valid, decomposes the action into a verb-object pair:
```
"put key in box" → <act> <put & in &; [key, box]> </act>
"north"          → <act> <west; []> </act>           # empty object list for directions
"take all"       → <act> <take all; []> </act>
```

Prepositions (on, at, with) are absorbed into the verb with `&` placeholders. **98% extraction accuracy** — this decomposition is easy for a small fine-tuned model.

**Phase 2: Object & Verb Pairing**

The action space `AS` is an **n×m matrix** (n verbs × m objects). It grows incrementally:
```
vobj_k = fm_vo(a_{k-1})    iff a_{k-1} is valid
AS = AS ∪ vobj_k
```

At decision time, the `pairing()` function cross-references objects visible in the current location (`obj^{loc}`) with the accumulated verb space → produces plausible verb-object combinations for the current context.

**This is NOT embedding-based retrieval.** It is purely combinatorial — take all known-valid verbs, combine with objects actually present. Simple set intersection filtering. Storage is in-memory during the episode.

#### Component 3: Experience Library

- **Trigger:** ONLY on scoring events — point gains or losses/deaths. The authors explicitly acknowledge this limitation: "human players naturally integrate relevant information into their memory at any point during gameplay."
- **Summarization model:** **GPT-o3-mini** (`LLM_es`) — a different, more expensive model than the extraction models
- **Input:** Fixed-length interaction history + reward change + current game state

**Output structure** (from Table 8):
1. `location` — one location name with description
2. `puzzle_status` — only puzzle-related steps, formatted as `<step>open door<step>` at `<loc>Room1 to enter <loc>Room2<loc>`
3. `scoring` — how points were earned/lost, with `<step>` and point counts
4. `important_experience` — reflective insights for future reference

Distinguishes "Earn Points" (record what led to scoring) from "Lose Points" (died or stalled — give suggestions for next time). Tagged with `<tag>`, `<room>`, `<dif>` (difficulty) for retrieval indexing.

**Storage:** Vector database (specific DB and embedding model NOT specified). RAG retrieval given current game context as query.

#### Full Results Table

All scores as raw/max. "base" = LLM with action history only. LPLH = last 3 epochs of 10-epoch runs.

| Game | Max | DRRN | KG-A2C | Qwen-7B base | Qwen-7B LPLH | Qwen-14B base | Qwen-14B LPLH | GPT-4o-mini base | GPT-4o-mini LPLH | GPT-o3-mini base | GPT-o3-mini LPLH |
|------|-----|------|--------|-------------|-------------|--------------|--------------|-----------------|-----------------|-----------------|-----------------|
| omniquest | 50 | 5 | 3 | 1/5 | **5/5** | 1.5/5 | **5/5** | 2/5 | **5/5** | 4/5 | **5/5** |
| detective | 360 | 197.8 | 207.9 | 10/10 | **68/100** | 36/70 | 72/90 | 22/30 | 30/60 | 20/20 | 50/60 |
| zork1 | 350 | 32.6 | 34 | 0/0 | 9/15 | 9/35 | **39.7/45** | 6/10 | 10/15 | 30/35 | 33.8/45 |
| zork3 | 7 | 0.7 | 0.1 | 0/0 | 0.6/1 | 2.0/3 | 2.6/3 | 1.8/3 | 2.8/3 | 3/3 | 3/3 |
| ludicorp | 150 | 13.8 | 17.8 | 1/1 | 1/1 | 10.5/12 | 11.7/13 | 1/1 | 2.6/3 | 4.4/7 | 8/11 |
| balances | 51 | 10 | 10 | 0/0 | 5/5 | 8.75/10 | **10/10** | 5/5 | 5/5 | 8.3/10 | **10/10** |
| spellbrkr | 600 | 37.8 | 21.3 | 0/0 | 25/25 | 25/40 | **41.7/60** | 18/40 | 38.3/50 | 31.3/50 | 47.5/60 |
| dragon | 25 | -3.5 | 0 | -3.5/-1 | -1.3/0 | -0.8/0 | -0.67/0 | -0.8/-0.2 | 0/0 | -4/-2 | -0.5/1 |
| gold | 100 | 0 | — | 0/0 | 0/0 | 2.4/3 | 2.5/3 | 3/3 | 3/3 | 1/3 | 3/3 |

Best LPLH Zork1 result: 39.7 raw / 45 max (Qwen-14B) — close to but not exceeding RL baselines. Human reference: 350 points in 412 steps with 48 verbs, 57 objects, 63 rooms.

#### Ablation Study (Zork1, Qwen-14B)

| Configuration | Raw | Max | Std Dev |
|---|---|---|---|
| Full LPLH | **39.7** | **45.0** | 4.2 |
| LPLH + CoT distillation | **41.6** | 45.0 | **2.4** |
| Action space only | 26.6 | 35.0 | 6.6 |
| Experience only | 25.6 | 34.0 | 9.0 |
| KG-map only | 11.0 | 15.0 | 2.0 |
| KG-map + action space | 27.8 | 35.0 | 6.8 |
| KG-map + experience (no action space) | 11.0 | 35.0 | 13.1 |
| Experience + action space | 32.0 | 40.0 | 4.0 |
| Baseline (no LPLH) | 9.0 | 25.0 | 9.2 |

**Action space learning is the single most impactful component** (9.0 → 26.6 alone). KG-map alone barely helps (9.0 → 11.0). Without action space, variance explodes (13.1 std dev). CoT distillation (DeepSeek-R1-Distill-Qwen-14B) adds 2 points and significantly reduces variance.

#### Implementation Details

- **Steps:** 10 epochs per game, 250 steps per epoch (2,500 total)
- **Hardware:** 2× RTX 4090 GPUs, bf16 precision
- **Temperatures:** 0.6 for non-fine-tuned LLMs, 0.1 for fine-tuned models
- **Fine-tuning:** LoRA rank 16, alpha 32, dropout 0.1, lr 2e-5, 3 epochs, targets all layers
- **Training data:** 3 non-test games, random + LLM-generated actions, GPT-4 annotation, manual curation
- **CoT distillation model:** DeepSeek-R1-Distill-Qwen-14B
- **Cost/tokens per turn:** NOT reported
- **Vector DB / embedding model:** NOT specified

#### Zork-Specific Failure Modes

The paper (Section 7) calls out two concrete Zork1 puzzles:
- **"echo" in the Loud Room:** Must type the literal word "echo" to score 5 points. Not inferable from context. Neither RL nor LLM agents reliably discover it.
- **"move rug" in the Living Room:** Reveals a hidden passage. The agent "frequently fails here — substituting implausible variants like `hit rug` or ignoring the rug entirely — though it occasionally succeeds with `move rug` or `pull rug`."

#### Head-to-Head: LPLH vs ZorkBurr

| Dimension | LPLH | ZorkBurr |
|---|---|---|
| Map data | LLM-parsed KG triples (15% error) | Jericho ground truth via `MAP_DATA` (0% error) |
| Memory trigger | Score changes only | Score change, location change, or death |
| Memory storage | Vector DB with RAG retrieval | Dict keyed by `location_id`, direct lookup |
| Strategic knowledge | Part of experience library | Separate `KNOWLEDGE_BASE`: periodic distillation into free-form markdown |
| Action validation | Post-hoc (did it work?) + action space accumulation | **Pre-execution critic** rejects before sending to game engine |
| Action vocabulary | Explicit verb-object matrix with combinatorial pairing | Free-text generation, no explicit vocabulary |
| Cross-episode learning | None | Knowledge base persists across episodes via disk files |
| Fine-tuned models | 2× LoRA-tuned 1.5B models for extraction | No fine-tuned components (single LLM, structured output) |
| Game interface | Jericho 'verbose' mode, observation text only | Jericho with ground-truth state extraction (`LOCATION_ID`, `SCORE`, `INVENTORY`) |

**What ZorkBurr should adopt from LPLH:**
1. **Action space accumulation** — track confirmed-valid verb-object pairs by location. Surface "commands known to work here" in context. Directly reduces wasted turns.
2. **Earn/lose distinction in memory prompts** — different summarization framing for deaths vs. score gains produces more actionable failure memories.
3. **Tagged experience retrieval** — `<tag>`, `<room>`, `<dif>` markup enables cross-location retrieval without vector DB overhead.

**What LPLH lacks that ZorkBurr has:**
1. **Pre-execution criticism** — ZorkBurr's critic prevents bad actions from reaching the game, saving turns
2. **Ground-truth game state** — ZorkBurr's Jericho integration eliminates the 15% KG extraction error
3. **Cross-episode persistence** — ZorkBurr's knowledge base improves over multiple runs

### CALM (2020) — "Keep CALM and Explore"

- **Paper:** EMNLP 2020
- **Architecture:** A Contextual Action Language Model (GPT-2 fine-tuned on human gameplay transcripts from ClubFloyd — 223K context-action pairs across 590 games) generates candidate actions. A DRRN (Deep Reinforcement Relevance Network) then re-ranks candidates by Q-value. Hybrid LM + RL approach.
- **Results:** 69% relative improvement over prior SOTA on Jericho benchmark. Competitive with models that had access to ground-truth admissible actions.
- **What worked:** Training on human gameplay transcripts gave the LM a prior over reasonable actions. The RL layer then selected among plausible candidates.
- **Relevance to ZorkBurr:** Pre-LLM-era but foundational. Demonstrates that the action generation problem (knowing what commands are even valid in a text adventure) is a major bottleneck. ZorkBurr's critic serves a similar filtering function to CALM's DRRN re-ranker.

### AdventureGPT (2023)

- **Blog post:** Better Programming
- **Architecture:** Forked a Python port of Colossal Cave Adventure. Game output is fed to ChatGPT, which returns a command. Uses LangChain agent patterns.
- **Results:** Demonstrated basic feasibility but limited progress without memory systems.
- **Relevance:** A simple baseline showing that pure prompt-and-respond loops plateau quickly.

---

## LLM Game-Playing in Other Domains

### DoomVLM (2024-2025)

- **GitHub:** Felliks/DoomVLM
- **Architecture:** Takes screenshots, overlays a numbered grid, sends to a vision LLM. The model calls `shoot(column)` or `move(direction)` — just two tool functions. Supports 1-4 agents in deathmatch. Works with any OpenAI-compatible API.
- **Results:** Functional but limited. Models can navigate and shoot but lack strategic depth.

### "Will GPT-4 Run DOOM?" (2024)

- **Paper:** arXiv 2403.05468
- **Architecture:** Two-component system: GPT-4V (vision) takes screenshots and returns structured game state descriptions; GPT-4 (agent) makes decisions based on vision output and action history. Limited to ~16 frames of history due to 32K token limit.
- **Key finding:** GPT-4 can execute short-term tactical decisions (manipulating doors, basic combat, pathing) but has **shallow reasoning depth and low memory recall** — if an enemy goes out of view, the model forgets about it entirely.
- **Relevance:** Confirms that LLMs without external memory systems cannot maintain awareness of off-screen/non-immediate state.

### Cradle (2024) — General Computer Control

- **Paper:** arXiv 2403.03186
- **Architecture:** Six modules: Information Gathering, Self-Reflection, Task Inference, Skill Curation, Action Planning, and Memory. Takes screenshots as input, outputs keyboard/mouse actions. Tested on Red Dead Redemption 2, Cities: Skylines, Stardew Valley, and desktop applications.
- **Results:** First agent to follow RDR2's main storyline and complete 40-minute real missions. Also created cities in Cities: Skylines and operated Chrome/Outlook.
- **What worked:** The modular architecture with specialized components for different cognitive functions. Self-reflection module for error correction.
- **Relevance:** The modular architecture pattern (separate components for perception, reflection, planning, execution) mirrors ZorkBurr's Burr graph design. Their "Skill Curation" module (building reusable action sequences) is similar to Voyager's skill library.

---

## Academic Papers — Memory and Planning Architectures

### BALROG Benchmark (ICLR 2025)

- **Paper:** arXiv 2411.13543
- **Games:** BabyAI, Crafter, TextWorld, Baba Is AI, MiniHack, NetHack
- **Results:** Claude 3.5 Sonnet and GPT-4o led at ~32% average progression. All models flatlined on NetHack (best: o1-preview at 1.5%). All games are procedurally generated, preventing memorization.
- **Critical failure modes identified:**
  - **The "Knowing-Doing Gap":** Models correctly identify that eating rotten food causes death when asked directly, yet repeatedly die from this exact mistake during gameplay. They know the rules but cannot apply them in context.
  - **Exploration collapse:** Models wander aimlessly, revisiting explored rooms while missing important areas.
  - **Vision hurts:** GPT-4o and Llama 3.2 performed WORSE when given image observations vs. text-only.
- **Relevance to ZorkBurr:** The "knowing-doing gap" is exactly what ZorkBurr's critic is designed to catch. The exploration collapse problem is what ZorkBurr's memory system (recording what has been explored) should address. The vision finding reinforces using Jericho's text interface.

### Voyager (NeurIPS 2023) — Minecraft

- **Paper:** arXiv 2305.16291
- **Architecture:** Three components:
  1. **Automatic Curriculum:** GPT-4 generates a sequence of tasks matching the agent's current capabilities, considering state, inventory, completed/failed tasks. Uses chain-of-thought prompting.
  2. **Skill Library:** Stores executable JavaScript code for completed tasks. Skills are indexed by embedding and retrieved by similarity to new tasks. Enables compositionality (combine simple skills into complex ones).
  3. **Iterative Prompting:** Generates code, executes it, feeds errors/feedback back for refinement. Self-verification checks task completion before adding to library.
- **Results:** 3.3x more unique items, 2.3x longer distances, 15.3x faster tech tree milestones vs. prior SOTA.
- **What worked:** The skill library as persistent memory. Code as a representation for skills (interpretable, composable, no catastrophic forgetting). The automatic curriculum preventing the agent from attempting tasks beyond its current capability.
- **Relevance to ZorkBurr:** The automatic curriculum concept maps well to ZorkBurr's objective system. The skill library concept (storing reusable solutions) could inspire storing successful puzzle-solving sequences in the knowledge base. The self-verification step is analogous to ZorkBurr's critic.

### GITM (NeurIPS 2023) — "Ghost in the Minecraft"

- **Paper:** arXiv 2305.17144
- **Architecture:** Hierarchical decomposition with three LLM layers:
  1. **LLM Decomposer:** Breaks goals into sub-goals using internet-sourced text knowledge
  2. **LLM Planner:** Plans structured action sequences for each sub-goal; records and summarizes successful plans into text-based memory for future use
  3. **LLM Interface:** Translates structured actions to keyboard/mouse operations
- **Results:** +47.5% success rate on ObtainDiamond. First agent to obtain ALL items in Minecraft's Overworld tech tree. Runs on CPU only (no GPU training).
- **What worked:** The hierarchical decomposition. Text-based memory of successful plans. Using internet knowledge (game wikis) for initial goal decomposition.
- **Relevance to ZorkBurr:** The hierarchical decomposition pattern (goal → sub-goals → actions) could inform ZorkBurr's objective system. Currently objectives are discovered but not decomposed into sub-steps. GITM's approach of recording successful action sequences as reusable plans could enhance ZorkBurr's knowledge base.

### SPRING (NeurIPS 2023) — "Studying the Paper and Reasoning to Play Games"

- **Paper:** arXiv 2305.15486
- **Architecture:** Feeds the game's academic paper (LaTeX source) as context to an LLM. Uses a DAG of game-related questions as nodes with dependency edges. Traverses the DAG in topological order, computing LLM responses at each node. Final node produces the action.
- **Game tested:** Crafter (Minecraft-like survival)
- **Results:** GPT-4 + SPRING outperformed all RL baselines trained for 1M steps, with zero training.
- **What worked:** Structured chain-of-thought via the DAG decomposition. Providing game documentation as context.
- **Relevance to ZorkBurr:** The DAG-based reasoning decomposition is interesting. ZorkBurr's `assemble_context` could potentially structure its context more hierarchically rather than as flat markdown. However, SPRING assumes access to a game manual — ZorkBurr deliberately avoids this to test genuine learning.

### ReAct (ICLR 2023) — "Synergizing Reasoning and Acting"

- **Paper:** arXiv 2210.03629
- **Architecture:** Interleaves reasoning traces ("I think I should...") with actions ("go north") in a single prompt. The model generates both thoughts and actions alternately.
- **Results on ALFWorld:** 71% success rate with 2-shot prompting, vs. 45% for act-only and 37% for imitation learning trained on 100K+ instances.
- **What worked:** The interleaving of thought and action allows dynamic plan adjustment. The model can reason about why an action failed and adjust.
- **Relevance to ZorkBurr:** ZorkBurr's agent prompt already uses a ReAct-like pattern (the agent produces reasoning + action). The critic adds a second layer of reflection that pure ReAct lacks.

### Reflexion (NeurIPS 2023) — "Verbal Reinforcement Learning"

- **Paper:** arXiv 2303.11366
- **Architecture:** After task failure, the agent generates a verbal self-reflection explaining what went wrong. These reflections are stored in an episodic memory buffer and included in subsequent attempts. No weight updates — learning happens entirely through natural language.
- **Results:** 91% pass@1 on HumanEval (vs. GPT-4's 80%). Strong improvements across HotPotQA and ALFWorld.
- **What worked:** Verbal self-reflection as a learning mechanism. The episodic memory buffer that persists across attempts.
- **Relevance to ZorkBurr:** Conceptually very close to ZorkBurr's `record_memory` action, which synthesizes what happened after each significant event. The key difference is that Reflexion reflects on *failures* specifically, while ZorkBurr records all significant outcomes. Consider adding explicit "what went wrong and why" framing to death/failure memories.

### DEPS (NeurIPS 2023) — "Describe, Explain, Plan and Select"

- **Paper:** arXiv 2302.01560
- **Architecture:** Four-phase loop:
  1. Describe the current execution state
  2. Explain why the current plan failed
  3. Re-plan with the explanation
  4. Select among parallel sub-goals using a trained ranker that estimates completion difficulty
- **Results:** First zero-shot multi-task agent completing 70+ Minecraft tasks. Nearly doubled overall performance.
- **What worked:** The Explain phase — explicitly asking the LLM to diagnose failures before re-planning. The goal selector that ranks sub-goals by estimated difficulty.
- **Relevance to ZorkBurr:** The Explain phase could improve ZorkBurr's death/failure handling. Currently `record_memory` records what happened, but explicit "explain why this failed" reasoning could produce more actionable memories. The difficulty-based goal ordering could help ZorkBurr prioritize objectives.

### Generative Agents (UIST 2023) — "Smallville"

- **Paper:** arXiv 2304.03442
- **Memory architecture:** Three layers:
  1. **Observation stream:** Complete record of experiences in natural language
  2. **Reflection:** Periodic synthesis of observations into higher-level insights ("I notice that I keep failing at X, maybe I should try Y")
  3. **Planning:** Daily/hourly plans generated from reflections and current state, with dynamic retrieval of relevant memories
- **What worked:** The reflection mechanism that synthesizes raw observations into abstract insights. Retrieval based on recency, importance, and relevance.
- **Relevance to ZorkBurr:** The three-tier memory hierarchy (raw observations → reflections → plans) is directly applicable. ZorkBurr has two tiers (memories + knowledge base). Adding a planning layer that synthesizes from the knowledge base into explicit strategic plans could help. The importance-weighted retrieval (not just recency) is also relevant — some memories matter more than others.

### SwiftSage (NeurIPS 2023 Spotlight)

- **Paper:** arXiv 2305.17390
- **Architecture:** Dual-process inspired by Kahneman's System 1/System 2:
  - **Swift module (System 1):** Small encoder-decoder LM fine-tuned on expert trajectories via imitation learning. Handles routine actions quickly and cheaply.
  - **Sage module (System 2):** GPT-4 for complex subgoal planning and grounding. Activated only when Swift fails or encounters novel situations.
- **Results:** Significantly outperformed ReAct, Reflexion, and SayCan on ScienceWorld. Only 757 tokens per action (very efficient).
- **What worked:** The dual-process design — using a cheap fast model for routine actions and an expensive model only for hard decisions.
- **Relevance to ZorkBurr:** Maps directly to ZorkBurr's hybrid model routing concept (local model for routine roles, remote model for agent decisions). Could extend the concept further: use the local model for "routine" navigation actions and the remote model only when the agent encounters something genuinely novel or puzzling.

### MindCraft — Minecraft Multi-Agent

- **GitHub:** mindcraft-bots/mindcraft
- **Paper:** arXiv 2504.17950
- **Architecture:** Multiple LLM-driven Minecraft agents that communicate and collaborate. Each agent has its own conversation context and can use tools to interact with the game world.
- **Relevance:** Demonstrates multi-agent coordination in game environments, though less directly applicable to single-player Zork.

---

## Why Zork Is Harder Than Pokemon

| Dimension | Pokemon | Zork |
|-----------|---------|------|
| **Action space** | ~8 buttons, structured menus | Free-text commands — infinite combinatorics |
| **Feedback** | HP bars, level-ups, type effectiveness | Often no feedback at all ("Nothing happens here") |
| **Game state** | Fully readable from RAM (badges, HP, position) | Partially observable, requires inference |
| **Knowledge needed** | Self-contained game rules | Real-world knowledge (what's a "sceptre"? what do you do with a "prayer"?) |
| **Exploration** | Linear route system with landmarks | Maze-like, unmarked, with one-way traps |
| **Failure cost** | Faint → restart at Pokecenter | Die → restart entire game |
| **Progress legibility** | Badges, levels, Pokedex — clear metrics | Score increases are sparse and unpredictable |
| **Grind as fallback** | Can level up to brute-force battles | No equivalent — puzzles require specific solutions |

The Gerrits paper confirms this empirically: best zero-shot LLM score on Zork was ~75/350. BALROG found the "knowing-doing gap" — models know game rules but fail to apply them in context. Text adventures compound this with the free-text command problem (you must *generate* the right command string, not select from options).

---

## Key Takeaways for ZorkBurr

### What ZorkBurr Already Does Right (Validated by Research)

1. **Ground truth from game engine (Jericho)** — both Pokemon projects do this. Gemini's team found curated text extraction from RAM outperformed multimodal pixel input.
2. **Critic/evaluator step** — unique to ZorkBurr among these projects. Directly addresses the "knowing-doing gap" that BALROG identified as the central unsolved problem.
3. **Synthesized memories over raw history accumulation** — Gemini's team learned the hard way that raw context accumulation degrades beyond 100K tokens. ZorkBurr's approach is validated.
4. **Learning from experience, not hard-coded knowledge** — the thesis holds up. Zero-shot approaches plateau quickly (Gerrits, Tseng, AdventureGPT).
5. **Modular graph architecture (Burr)** — mirrors Cradle's finding that specialized components for different cognitive functions outperform monolithic designs.

### Gaps and Opportunities

1. **Action vocabulary learning** (from LPLH): Track what commands work in which contexts. Store successful verb-object pairs by location for retrieval. ZorkBurr doesn't currently do this — it's a technique that directly addresses the free-text command problem.

2. **Explicit failure reasoning** (from Reflexion, DEPS): "Why did this fail?" not just "what happened." Adding causal reasoning to death/failure memories could produce more actionable learning. DEPS's Explain phase nearly doubled performance.

3. **Goal decomposition with prerequisites** (from GITM, Voyager): Break objectives into sub-steps with dependency tracking. Currently ZorkBurr discovers objectives but doesn't decompose them. GITM's hierarchical decomposition was key to being the first agent to obtain all Minecraft items.

4. **Context poisoning defense** (from Gemini Plays Pokemon): Validate knowledge base entries don't contain hallucinations. Once bad information enters persistent state, models fixate on it. This was Gemini's biggest problem.

5. **Self-managed knowledge base** (from Claude Plays Pokemon): Rather than the system deciding what to remember, give the agent more control over its own knowledge base entries. This created an emergent memory system in the Pokemon project.

6. **Importance-weighted memory retrieval** (from Generative Agents): Not all memories are equally relevant. Adding importance scoring to memory retrieval (beyond just location-keyed lookup) could help surface critical information at the right time.

7. **Dual-process model routing** (from SwiftSage): Use cheap/fast model for routine navigation, expensive model only for novel/puzzle situations. Extends ZorkBurr's existing hybrid routing concept.

---

## Sources

### Claude Plays Pokemon
- [Anthropic — Extended Thinking Blog Post (official launch)](https://www.anthropic.com/news/visible-extended-thinking)
- [Latent.Space — How Claude 3.7 Plays Pokemon](https://www.latent.space/p/how-claude-plays-pokemon-was-made)
- [Michael Liu's ML Blog — Claude Plays Pokemon Analysis](https://michaelyliu6.github.io/posts/claude-plays-pokemon/)
- [ZenML — Building and Deploying a Pokemon-Playing LLM Agent at Anthropic](https://www.zenml.io/llmops-database/building-and-deploying-a-pokemon-playing-llm-agent-at-anthropic)
- [MLOps Community — A Conversation with the Creator (David Hershey)](https://home.mlops.community/public/videos/claude-plays-pokemon-a-conversation-with-the-creator)
- [GitHub — ClaudePlaysPokemonStarter (open-source code)](https://github.com/davidhershey/ClaudePlaysPokemonStarter)
- [LessWrong — Claude Plays Pokemon: Opus 4.5 Follow-up](https://www.lesswrong.com/posts/gogZyeistdaDFuhbG/claude-plays-pokemon-opus-4-5-follow-up)
- [LessWrong — Insights into Claude Opus 4.5 from Pokemon](https://www.lesswrong.com/posts/u6Lacc7wx4yYkBQ3r/insights-into-claude-opus-4-5-from-pokemon)
- [LessWrong — So How Well is Claude Playing Pokemon?](https://www.lesswrong.com/posts/HyD3khBjnBhvsp8Gb/so-how-well-is-claude-playing-pokemon)
- [TechCrunch — Anthropic's Claude AI is playing Pokemon on Twitch](https://techcrunch.com/2025/02/25/anthropics-claude-ai-is-playing-pokemon-on-twitch-slowly/)

### Gemini Plays Pokemon
- [The Making of Gemini Plays Pokemon](https://blog.jcz.dev/the-making-of-gemini-plays-pokemon)
- [Agentic Case Study — Playing Pokemon with Gemini](https://www.dbreunig.com/2025/06/17/an-agentic-case-study-playing-pok%C3%A9mon-with-gemini.html)

### Text Adventure Papers
- [Gerrits 2026 — Playing With AI](https://arxiv.org/html/2602.15867)
- [Can LLMs Play Text Games Well? (Tseng et al. 2023)](https://arxiv.org/abs/2304.02868)
- [LPLH — Learning to Play Like Humans (ACL 2025)](https://arxiv.org/abs/2505.12439)
- [CALM — Keep CALM and Explore (EMNLP 2020)](https://aclanthology.org/2020.emnlp-main.704/)
- [AdventureGPT](https://betterprogramming.pub/adventuregpt-using-llm-backed-agents-to-play-text-based-adventure-games-be52f243866a)

### Game-Playing AI (Other Domains)
- [DoomVLM (GitHub)](https://github.com/Felliks/DoomVLM)
- [Will GPT-4 Run DOOM?](https://arxiv.org/abs/2403.05468)
- [Cradle — General Computer Control](https://arxiv.org/abs/2403.03186)

### Memory and Planning Architectures
- [BALROG Benchmark (ICLR 2025)](https://arxiv.org/abs/2411.13543)
- [Voyager (NeurIPS 2023)](https://arxiv.org/abs/2305.16291) | [Project site](https://voyager.minedojo.org/)
- [GITM — Ghost in the Minecraft (NeurIPS 2023)](https://arxiv.org/abs/2305.17144)
- [SPRING (NeurIPS 2023)](https://arxiv.org/abs/2305.15486)
- [ReAct (ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366)
- [DEPS (NeurIPS 2023)](https://arxiv.org/abs/2302.01560)
- [Generative Agents / Smallville (UIST 2023)](https://arxiv.org/abs/2304.03442)
- [SwiftSage (NeurIPS 2023)](https://arxiv.org/abs/2305.17390)
- [MindCraft (2025)](https://arxiv.org/abs/2504.17950) | [GitHub](https://github.com/mindcraft-bots/mindcraft)

### Surveys and Meta-Resources
- [Lilian Weng — LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
- [Large Language Models and Games: Survey](https://arxiv.org/abs/2402.18659)
- [Awesome LLM Game Agent Papers (GitHub)](https://github.com/git-disl/awesome-LLM-game-agent-papers)
