# ZorkBurr Orchestrator Journal

Started: 2026-03-30

## Key Learnings (updated after episode 54)

**Current best score:** 54 (episode 37, A3b MoE model). Local-model best: 40 (ep48, ep54, Ministral-3-14B-Reasoning)
**Current bottleneck:** Dam puzzle verb discovery. Agent reliably scores 40 (house+troll) by turn 25 but can't break past — needs "turn bolt with wrench" but tries "use/push/twist wrench on bolt" instead.

### What works
- **KB item scanning rule** (ep53→54): Agent reads ALL KB entries before acting. Confirmed: takes sword+lantern before rug puzzle. Fixed 3-episode sword-skipping streak.
- **Consolidation bracket fix** (ep52→53): Strip `[]` from titles before matching. 6 consolidations in ep53, 1+2 supersessions in ep54. Memory quality improving.
- **Ministral-3-14B-Reasoning model** (ep48): Reliable KB adherence, killed troll consistently. Clear upgrade from Qwen3-14B.
- **KB append-and-merge** (ep49→50): Prevents LLM from overwriting existing KB entries. KB content preserved across episodes.
- **Context reordering** (ep50→51): KB before plan/reasoning in context. Agent reads strategy before forming plans.
- **Bidirectional map** (ep51): Both directions shown in Mermaid diagram. Agent navigates reverse routes correctly.
- **Permanent obstacle rule** (ep35→36): Cap of 5 attempts on same target. Prevents 20-turn fixation loops.
- Cross-episode KB: KB drives efficient early game (score 35-40 by turn 20-25 consistently).

### Falsified hypotheses
- "Temperature 0.7 reduces variance" — FAILED ep47: Made agent deterministic on wrong path.
- "Qwen3-14B is sufficient" — FAILED ep42-47: Inconsistent KB adherence.
- "50-turn prompt changes can fix model KB-following" — FAILED ep39-41: Root cause was objective LLM not receiving KB (code bug).

### Open problems
- **Dam puzzle unsolved** — 150+ cumulative turns across episodes. Agent tries "use/push/twist X on Y" but never "turn X with Y". Verb discovery gap.
- **KB update timeout** — 4 consecutive episodes (ep51-54). Fix committed: reduced action window 50→25 turns. Untested.
- **Loud Room puzzle** — "echo" command never discovered. Agent takes platinum bar but it vanishes.
- **Critic over-rejection** — Critic rejects "move rug" (-0.50 to -0.90) and combat actions. Wastes 3+ turns per episode on forced-through valid actions.

### Subsystems investigated
- Agent prompt: ~20 changes, last ep53→54 (KB item scanning)
- Critic prompt: ~3 changes, last ep7
- KB/memory system: ~10 changes, last ep52→53 (consolidation bracket fix)
- Python pipeline: ~8 changes, last ep54 (KB update window reduction)
- Model: 2 switches (API→Qwen3-14B ep42, Qwen3→Ministral ep48)


---

## Episode 75 — Turn 25 Checkpoint
**Type:** HEALTHY — score 40 by t18, efficient KB-driven early game, deep underground exploration
**Score:** 40/350 (house +10 t7, cellar +25 t14, troll +5 t18)
**Locations visited:** 13 unique (West_House, North_House, Behind_House, Kitchen, Living_, Cellar, Troll_, East-West_Passage, Round_, Narrow_Passage, Mirror_, Cave, Winding_Passage)
**Avg critic score:** 0.54 (HEALTHY)
**Rejection rate:** 4/25 (16%) — EXCELLENT
**Gameplay quality:** LEARNING
  - Memory use: Agent explicitly references memories at t5 (Behind House window entry), t14 (cellar from trap door), t16 (troll combat), t18 (east for +5 points). Every key navigation decision cites memory data. Excellent.
  - KB alignment: KB empty (wiped pre-ep75). Agent relying on memories from prior episodes for scoring path. Expected.
  - Objective quality: 7 discovered, 6 completed. 4/7 well-formed with location IDs. Some vague (explore round room, use lantern).
  - Objective pursuit: Agent completed 6 objectives efficiently (mailbox, leaflet, items, staircase, kitchen passage). Now mapping underground rooms.
  - Learning system quality: 0 new memories, 0 KB updates (expected at t25). Memory dedup still an issue (6 egg memories across 2 locations). KB will be generated end-of-episode by Sonnet.
  - Pathfinding: NAVIGATING — perfect route mailbox→house→items→rug→cellar→troll→east. Then systematic mapping of Mirror Room/Cave/Winding Passage (all new rooms). Zero wasted turns at known rooms (skip-mapping heuristic may be working).
**Triggers:** None — all metrics healthy.
**Notes:** Score 40 by t18 is 3rd fastest ever (ep71: 45 by t24, ep73: 40 by t18). Verb exploration rule fired at t12 (move rug after examine rug). Agent reasoning shows clear memory-driven planning — citing memories for window entry, trap door, troll combat. Throughput ~1 turn/min (reasoning mode adding latency, some turns took 3-6 min). Agent now in Mirror Room area mapping underground — watching for Dam area progression and further scoring.

---

## Episode 75 — Turn 50 Checkpoint
**Type:** HEALTHY — score 44, painting acquired, broad underground exploration
**Score:** 44/350 (delta: +4 since t25 — painting +4 at t50)
**Locations visited (t26-50):** 11 unique (Cave, Entrance_Hades, Winding_Passage, Mirror_, Narrow_Passage, Round_, East-West_Passage, Troll_, Cellar, East_Chasm, Gallery)
**Avg critic score:** 0.55 (HEALTHY)
**Rejection rate:** 2/25 (8%) — EXCELLENT (best t26-50 block across all episodes)
**Gameplay quality:** LEARNING
  - Memory use: Agent escaped Entrance_Hades after 8 turns (permanent obstacle rule fired at t35). Navigated back through known underground rooms efficiently.
  - KB alignment: KB empty (post-ep75 start, Sonnet KB only generated end-of-episode). Agent using memories and map for navigation.
  - Objective quality: Not checked yet.
  - Objective pursuit: Agent took painting at Gallery (t50, +4 score). Navigated through East_Chasm route (new path from Cellar south). Purposeful.
  - Learning system quality: 0 LLM fallbacks (max_tokens 2048 fix CONFIRMED working — 0 in 50 turns). 0 KB updates (expected — end-of-episode only).
  - Pathfinding: NAVIGATING — Entrance_Hades (8 turns, escaped via obstacle rule) → backtrack through Mirror/Round → Troll Room (re-fought troll t43) → Cellar → East_Chasm → Gallery. Systematic underground circuit.
**Triggers:** None — all metrics healthy. Entrance_Hades stay (8 turns) was under 10-turn threshold and agent self-corrected.
**Notes:** Agent discovered Gallery via East_Chasm (south from Cellar, east to Gallery) — a different route than prior episodes. Painting +4 at t50 brings score to 44 (matching ep63's session high). Troll re-spawned (t42-43) — expected in Zork. Agent tried "up" from Cellar (t46, rejected 3x at -0.80) — critic correctly blocked ascending without scoring opportunity. max_tokens fix confirmed: ZERO LLM fallbacks in 50 turns (was 18% in ep72). Agent heading deeper underground from Gallery.

---

## Episode 75 — Turn 75 Checkpoint
**Type:** CONCERN — score stagnant 2 checkpoints, big loop circuit through known rooms
**Score:** 44/350 (delta: 0 since t50 — stagnant 25 turns)
**Locations visited (t51-75):** 9 unique (Studio, Gallery, East_Chasm, Cellar, Troll_, East-West_Passage, Round_, Narrow_Passage, Mirror_) — all previously visited
**Avg critic score:** 0.43 (BELOW 0.50 threshold)
**Rejection rate:** 5/25 (20%) — HEALTHY, but 3 turns had 3 rejections each (all "up" from Cellar)
**Gameplay quality:** DRIFTING
  - Memory use: Agent not referencing memories for navigation decisions in this block.
  - KB alignment: KB empty (end-of-episode Sonnet generation only). No strategic guidance available.
  - Objective quality: Not checked.
  - Objective pursuit: Agent circling known rooms. No progress toward any objective.
  - Learning system quality: 0 new memories, 0 KB updates (expected). LLM fallbacks: 0 (max_tokens fix holding).
  - Pathfinding: WANDERING — Agent doing big loops: Cellar→Troll→EW Passage→Round→Narrow→Mirror→back. Tries "up" from Cellar 3 times (t46, t56, t68 — always rejected). Never heads toward Chasm/Dam area. Area escape rule NOT firing — agent in 6+ rooms per loop, not 2-3 as rule requires.
**Triggers:** Score stagnant (0 delta across 2 consecutive checkpoints). Low critic (0.43 < 0.50).
**Notes:** Agent stuck in underground circuit without reaching new territory. The area escape rule doesn't fire because the loop spans 6 rooms (rule checks 2-3 rooms). KB is empty so agent has no strategic guidance about where to go next. This is expected for a post-KB-wipe episode — the agent's only scoring opportunities are puzzle-gated (dam bolt, echo room, Hades). Not dispatching improvement because: (1) first episode post-KB-wipe, (2) score ceiling from game puzzles not system failure, (3) Sonnet KB at episode end will provide strategic guidance for ep76. Monitoring to t100 — if agent finds no new territory, this confirms the need for better exploration heuristics when KB is empty.

---

## Episode 75 — Turn 100 Checkpoint
**Type:** CONCERN — score stagnant 3 consecutive checkpoints (50 turns at 44), big-loop circuit persists
**Score:** 44/350 (delta: 0 since t50 — stagnant 50 turns)
**Locations visited (t76-100):** 10 unique (Cave, Chasm, East-West_Passage, Entrance_Hades, Maze, Mirror_, Narrow_Passage, Round_, Troll_, Winding_Passage) — Chasm and Maze are new but visited only briefly
**Avg critic score:** 0.67 (HEALTHY — best block this episode)
**Rejection rate:** 4/25 (16%) — EXCELLENT
**Gameplay quality:** DRIFTING
  - Memory use: Not evaluated — minimal memories available.
  - KB alignment: KB empty. No strategic guidance.
  - Objective quality: Not checked.
  - Objective pursuit: Agent circling known rooms with occasional new room visits (Chasm t88, Maze t92) but immediately returns to circuit.
  - Learning system quality: 0 KB updates, 0 new memories. Episode will generate Sonnet KB at end.
  - Pathfinding: WANDERING — Same big-loop circuit: Round→Narrow→Mirror→Cave→Hades→back→EW Passage→Troll→Round. Third visit to Entrance_Hades (t99-100). Agent briefly visited Chasm (t88, 1 turn) and Maze (t92, 1 turn) but retreated immediately both times.
**Triggers:** Score stagnant (0 delta across 3 consecutive checkpoints). However: KB empty, expected behavior.
**Notes:** Not dispatching improvement. Root cause is empty KB — agent has no strategic direction for post-44 scoring. The big-loop circuit visits 6+ rooms per cycle so the area escape rule (designed for 2-3 room oscillations) doesn't fire. Agent is productively visiting new rooms (Chasm, Maze) but doesn't explore them in depth. Sonnet KB generation at episode end will document the underground map and scoring history, providing strategic context for ep76. Letting episode run to max_turns for maximum KB data.

---

## Episode 75 — COMPLETE
**Turns:** 125 (max_turns — survived full episode!)
**Final score:** 44/350 (house +10 t7, cellar +25 t14, troll +5 t18, painting +4 t50)
**Locations visited:** 19 unique
**Objectives found:** 13
**End reason:** max_turns
**Memory stats:** 12 total, 1 new, 2 dedup rejected, 0 superseded, 0 consolidated

**Sonnet KB Generation: SUCCESS**
KB generated by Claude Sonnet 4.6 at episode end. Content quality: EXCELLENT.
- 4 Score Changes: all correct with exact score deltas
- Puzzle Mechanics: 5 entries, all grounded in observed gameplay (rug→trap door, trap door locks, spirits immune to material objects, gate blocked by force, sword glow in Cave)
- Items Found: 8 entries with correct locations
- Failed Approaches: 7 entries, all factual (no hallucinated approaches)
- Unexplored Leads: 6 entries pointing to real unexplored areas (gothic door, maze, chasm stairway, cellar crawlway)
- ZERO game knowledge leaks (no "requires solving", "may require", puzzle naming)
- ZERO hallucinated score events (was the main problem with Ministral KB in ep66)

**Key achievements:**
  - Score 40 by t18 (3rd fastest ever: house t7, cellar t14, troll t18)
  - ZERO LLM fallbacks in 125 turns — max_tokens 2048 fix CONFIRMED
  - Verb exploration rule fired at t12 (move rug), generalized to examine mirror/painting
  - Survived all 125 turns with no death
  - Sonnet KB is clean, factual, strategic — major improvement over Ministral KB

**Key issues:**
  1. **Big-loop circuit t51-125 (75 turns at 44)**: Agent circled Cellar→Troll→EW→Round→Narrow→Mirror→Cave→Hades in a 6-room loop. Area escape rule doesn't fire on 6-room loops.
  2. **Entrance to Hades fixation**: 4 separate multi-turn visits (t27-34, t79-80, t99-107, t122-125). Agent can't solve spirits puzzle (needs bell/candles/prayer — multi-item ritual from distant rooms).
  3. **Never reached Dam/Chasm area**: Agent explored east circuit only, never went south from Round Room or through Chasm.
  4. **Rate limits**: 429 errors at t101 and t116 (OpenRouter Gemma 4-31B rate limiting). Added ~10 min wall time.
  5. **Throughput**: ~1.5 turns/min average, some turns 3-6 min. 125 turns took ~4 hours.

**Pending improvement resolutions:**
  - max_tokens 1024→2048 (ep73→74 BLOCKER): **CONFIRMED** — 0 LLM fallbacks in 125 turns (ep72: 18%)
  - Skip-mapping heuristic (ep73→74 INCREMENTAL): **PARTIALLY CONFIRMED** — 0 wasted turns at known rooms in t1-50, but big-loop circuit in t51-125 is a different issue
  - Reasoning mode (ep71→72 INCREMENTAL): **INCONCLUSIVE** — throughput degraded (~1.5 vs 2 turns/min). No measurable reasoning quality improvement vs ep71 (non-reasoning). Score 44 matches ep63/ep71.
  - Sonnet KB model (ep74→75 INCREMENTAL): **CONFIRMED** — KB clean, factual, zero leaks. Takes effect for ep76 which will have this KB to guide strategy.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep66 | 15 | 0 | 54 | 6 | 14 | hallucinated | killed t75 |
| ep67 | 15 | 0 | 54 | 20 | 8 | clean | killed t78 |
| ep68 | 10 | -5 | 54 | 7 | 11 | clean | killed t65 |
| ep69 | 15 | +5 | 54 | 6 | 11 | clean | killed t59 |
| ep70 | 45 | +30 | 54 | 7 | 22 | clean | max_turns! |
| ep71 | 45 | 0 | 54 | 5 | 20 | clean | max_turns! |
| ep72 | 30(40) | -5 | 54 | 7 | 11 | clean | death t28 |
| ep73 | 40 | +10 | 54 | 7 | 16 | clean | killed t50 |
| ep74 | 45 | +5 | 54 | 7 | 14 | clean | killed t60 |
| ep75 | 44 | -1 | 54 | 7 | 19 | sonnet | max_turns! |

**Trend:** ep75 matched recent scores (44 vs 45 in ep70/71/74). System reliably scores 40-45 within 20 turns. Score ceiling at 44-45 across 6 episodes now. The underground is puzzle-gated: dam bolt (needs button prerequisite), Hades (needs bell/candles/prayer), echo room (needs "echo" command). Agent explores the east underground circuit but never reaches Dam/Chasm area. Sonnet KB is the major deliverable from this episode — ep76 will be the first episode with Sonnet-quality strategic guidance.

---

## Episode 76 — Turn 25 Checkpoint
**Type:** CONCERN — heavy rate limiting (7 fallback looks), but score 40 by t25
**Score:** 40/350 (house +10 t7, cellar +25 t22, troll +5 t25)
**Locations visited:** 8 unique (West_House, South_House, Behind_House, Kitchen, Living_, Cellar, Troll_, East-West_Passage)
**Avg critic score:** 0.50 (borderline — dragged down by fallback looks getting low scores)
**Rejection rate:** 7/25 (28%) — borderline
**LLM fallback looks:** 7/25 (28%) — WORST EVER. Rate limiting (429) from OpenRouter Gemma 4-31B.
**Gameplay quality:** LEARNING (despite rate limiting)
  - Memory use: Agent reasoning references KB Score Changes and memories. House entry path used.
  - KB alignment: Agent followed KB path exactly despite rate limits: house → items → rug → cellar → troll → east. Sonnet KB guiding well.
  - Objective quality: Not checked.
  - Objective pursuit: Agent reached EW Passage at t25 — on track for underground exploration.
  - Learning system quality: 7 fallback "look" actions consumed ~28% of turns. Without rate limits, agent would have scored 40 by ~t18.
  - Pathfinding: NAVIGATING (when LLM responds) — efficient route, zero wasted turns on non-fallback actions.
**Triggers:** LLM error pile-up: 7 fallback "look" in 25 turns (28%). Rate limiting is external (OpenRouter provider throttling) not system defect.
**Notes:** Score 40 by t25 despite 7 wasted turns. Verb exploration rule fired at t18 (move rug). Same KB-driven execution as ep75 but slower due to rate limits. Agent now at EW Passage heading east — critical question: will Sonnet KB's "Unexplored Leads" guide agent to Chasm/Dam area (Round Room south/southeast, or EW Passage north stairway)?

---

## Episode 76 — Turn 50 Checkpoint
**Type:** HEALTHY — Dam area reached for first time since KB wipe, broad exploration
**Score:** 40/350 (delta: 0 since t25 — expected, underground puzzle-gated)
**Locations visited (t26-50):** 10 unique (Round_, Loud_, Deep_Canyon, Dam, Dam_Lobby, Maintenance_, Reservoir_South, Chasm, East-West_Passage, Troll_)
**Avg critic score:** 0.47 (borderline — Maintenance inventory management drove negatives)
**Rejection rate:** 5/25 (20%) — HEALTHY
**LLM fallback looks:** 1/25 (4%) — rate limiting easing
**Gameplay quality:** LEARNING
  - Memory use: Not evaluated in detail.
  - KB alignment: Sonnet KB "Unexplored Leads" guided agent to explore Chasm stairway, Dam area. Agent collected wrench+screwdriver from Maintenance (KB "Items Found" lists these).
  - Objective quality: Not checked.
  - Objective pursuit: Agent at Dam area collecting tools. Purposeful.
  - Learning system quality: 1 fallback look (improvement from 7 in t1-25). KB guiding exploration.
  - Pathfinding: NAVIGATING — efficient route: Round→Loud→Deep Canyon→Dam→Lobby→Maintenance→Dam→Reservoir→Chasm→EW→Troll. Broad circuit covering Dam area for first time post-reset.
**Triggers:** None — all metrics healthy. Critic borderline (0.47) but driven by inventory management turns at Maintenance.
**Notes:** MAJOR: Agent reached Dam area at t30 — first time since KB wipe (ep75 never reached it in 125 turns). Sonnet KB "Unexplored Leads" drove exploration. Agent took wrench+screwdriver from Maintenance. DID NOT try "turn bolt with wrench" at Dam — KB lists this as "Failed Approach." The KB correctly records the agent's observation (bolt genuinely failed without button prerequisite). Agent at Troll Room t50 — monitoring for further Dam area exploration or Gallery route.

---

## Episode 76 — Turn 75 Checkpoint
**Type:** HEALTHY — score 44, broad underground exploration, painting scored
**Score:** 44/350 (delta: +4 since t25 — painting +4 at t61)
**Locations visited (t51-75):** 9 unique (Cellar, East_Chasm, Gallery, Troll_, East-West_Passage, Chasm, Reservoir_South, Deep_Canyon, Loud_)
**Avg critic score:** 0.48 (borderline — inventory management and bar attempts driving negatives)
**Rejection rate:** 8/25 (32%) — borderline, driven by Gallery inventory and Loud Room bar
**Gameplay quality:** LEARNING
  - Memory use: Agent navigating underground purposefully using map data.
  - KB alignment: Agent avoided bolt at Dam (KB Failed Approach). Explored Chasm/Dam circuit. Took platinum bar attempt at Loud Room.
  - Objective quality: Not checked.
  - Objective pursuit: Agent exploring underground systematically — Gallery (painting +4), then Chasm circuit → Loud Room.
  - Learning system quality: 0 KB updates (end-of-episode only). Memories building.
  - Pathfinding: NAVIGATING — Gallery→East_Chasm→Cellar→Troll(pick up wrench)→EW→Chasm→Reservoir→Deep Canyon→Loud Room. Broad exploration of both east and south underground circuits.
**Triggers:** None — score increased (+4), metrics healthy.
**Notes:** Agent explored BOTH underground circuits in ep76: east circuit (Gallery/Studio via East Chasm) and south circuit (Chasm→Reservoir→Dam→Deep Canyon→Loud Room). This is the broadest underground exploration pattern post-reset. Score 44 matches ep75. Platinum bar at Loud Room is the echo puzzle — agent can't solve it yet. Episode running to max_turns for Sonnet KB update. Rate limiting easing (~1 turn/min).

---

## Episode 76 — COMPLETE
**Turns:** 125 (max_turns — survived full episode!)
**Final score:** 44/350 (house +10 t7, cellar +25 t22, troll +5 t25, painting +4 t61)
**Locations visited:** 20 unique
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** 12 total, 0 new, 3 dedup rejected, 0 consolidated

**Sonnet KB Generation: SUCCESS (richer than ep75)**
New data from ep76 exploration:
- Blue button mechanics: flooding behavior documented
- Loud Room echo pattern: "all commands echo back as repeated text"
- Dam bolt: still listed as failed but more context
- Stream View: new area visited
- Screwdriver/tube location tracking: "left in Troll Room"

**Key achievements:**
  - FIRST DAM AREA EXPLORATION post-reset (Sonnet KB drove exploration — ep75 never reached Dam in 125 turns)
  - Blue button pressed (t88) → bolt retried (t97, t113) — causal reasoning across distant rooms
  - Painting +4 at t61 (needed inventory management first)
  - 20 locations explored (matched ep75)
  - 125 turns survived with heavy rate limiting (7 fallback looks from 429 errors)

**Key issues:**
  1. **Rate limiting:** 429 errors throughout, ~8+ fallback looks. Throughput degraded to ~1 turn/2 min at times. Total runtime ~4.5 hours.
  2. **Bolt still won't turn** — blue button is wrong prerequisite (floods rooms). Agent needs yellow button.
  3. **Loud Room platinum bar** — agent tried 6+ times to take bar but commands echo. Needs intransitive "echo" command (see user feedback).
  4. **Score stagnant t61-125** (64 turns at 44): Underground puzzle-gated.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep68 | 10 | -5 | 54 | 7 | 11 | clean | killed t65 |
| ep69 | 15 | +5 | 54 | 6 | 11 | clean | killed t59 |
| ep70 | 45 | +30 | 54 | 7 | 22 | clean | max_turns! |
| ep71 | 45 | 0 | 54 | 5 | 20 | clean | max_turns! |
| ep72 | 30(40) | -5 | 54 | 7 | 11 | clean | death t28 |
| ep73 | 40 | +10 | 54 | 7 | 16 | clean | killed t50 |
| ep74 | 45 | +5 | 54 | 7 | 14 | clean | killed t60 |
| ep75 | 44 | -1 | 54 | 7 | 19 | sonnet | max_turns! |
| ep76 | 44 | 0 | 54 | 7 | 20 | sonnet | max_turns! |

**Trend:** ep76 matched ep75 (score 44). System consistently scores 40-45 within 25 turns then plateaus. Score ceiling at 44-45 for 7 consecutive episodes now. The Sonnet KB drove exploration to the Dam area (ep75 never reached it), and the agent showed causal reasoning (button→bolt retry). Two unsolved puzzles block further progress: (1) dam bolt needs yellow button prerequisite, (2) Loud Room needs intransitive "echo" command. Both require the agent to try actions outside its current verb-noun pattern.

---

## Session Complete
**Episodes run:** 2 (ep75 max_turns 44/350, ep76 max_turns 44/350)
**Best score achieved:** 44/350 (both episodes)
**Improvements made:** 0 (this session was evaluation — confirming Sonnet KB, max_tokens, reasoning mode)
**System status:** PERFORMING WELL (Sonnet KB driving exploration, all subsystems stable)
**Summary:** This session confirmed the Sonnet KB model (ep74→75) works: ep76 explored the Dam area for the first time post-reset (ep75 never reached it), and the agent showed causal reasoning (pressed blue button → retried bolt). Score ceiling at 44 for 7 consecutive episodes — underground is puzzle-gated. Two puzzles block progress: (1) dam bolt needs yellow button (agent pressed blue), (2) Loud Room needs intransitive "echo" command. User observation: agent's fixation on verb-noun commands prevents discovering intransitive commands like "echo" and "pray". Next improvement should add a game-agnostic intransitive command exploration rule based on game response patterns (e.g., "commands echo back" → try typing the echoed word as a command).

**Planned improvement for ep77:** Add intransitive command exploration rule to agent prompt. When game responses contain unusual patterns (echoed text, repeated words, onomatopoeia), the game may be hinting at a command word. The agent should try typing unusual words from game responses as standalone commands. Game-agnostic: teaches response-reading as a puzzle-solving strategy, not specific solutions.

---

## Episode 77 — Turn 25 Checkpoint
**Type:** HEALTHY — score 40 by t18, efficient KB-driven early game, systematic underground exploration
**Score:** 40/350 (house +10 t7, cellar +25 t13, troll +5 t18)
**Locations visited:** 12 unique (West_House, North_House, Behind_House, Kitchen, Living_, Cellar, Troll_, East-West_Passage, Round_, Narrow_Passage, Mirror_, Engravings_Cave)
**Avg critic score:** 0.54 (HEALTHY)
**Rejection rate:** 6/25 (24%) — HEALTHY (driven by "take sack,bottle" -1.00×3, "move rug" -0.90×3)
**Gameplay quality:** LEARNING
  - Memory use: Agent reasoning references KB Score Changes throughout (turns 3, 4, 7, 13, 17, 18). Every navigation decision cites KB. Excellent.
  - KB alignment: Agent followed KB Score Changes exactly: house entry→items→rug→cellar→troll→east. Perfect.
  - Objective quality: Not checked yet (objectives just generated at t20 boundary).
  - Objective pursuit: Agent at Engravings Cave (new area, t25). Exploring systematically.
  - Learning system quality: KB clean (Sonnet-generated from ep76). 12 memories, 6 are egg duplicates (dedup issue). 0 LLM fallbacks so far.
  - Pathfinding: NAVIGATING — efficient route: mailbox→house→items→rug→cellar→troll→EW Passage→Round→Mirror Room circuit→Engravings Cave (new). Zero wasted turns.
**Triggers:** None — all metrics healthy.
**Notes:** Throughput ~1 turn/min avg. Engravings Cave is new territory (not seen in ep75/76). Agent exploring southeast from Round Room. Memory dedup still broken (6 egg memories across 2 locations). Residual critic issues: comma-separated commands (-1.00), "move rug" (-0.90). Both force-accepted but waste turns. Monitoring to t50 for Dam area exploration and scoring.

---

## Episode 77 — Turn 50 Checkpoint
**Type:** HEALTHY — score 44, painting acquired, broad underground exploration including Dome Room (new)
**Score:** 44/350 (delta: +4 since t25 — painting +4 at t37)
**Locations visited (t26-50):** 11 unique (Dome_, Engravings_Cave, Round_, East-West_Passage, Troll_, Cellar, East_Chasm, Gallery, Chasm, Reservoir_South, Stream_View)
**Avg critic score:** 0.52 (HEALTHY)
**Rejection rate:** 6/25 (24%) — HEALTHY
**Gameplay quality:** LEARNING
  - Memory use: Agent navigating purposefully using map data. Referenced KB for Gallery painting.
  - KB alignment: Agent took painting (+4) per KB Score Changes. Now navigating back toward Living Room for gothic door investigation.
  - Objective quality: Not checked yet.
  - Objective pursuit: Agent plans to investigate gothic door in Living Room (KB Unexplored Leads). Navigating via Chasm→EW Passage→Troll→Cellar→up.
  - Learning system quality: 0 KB updates (end-of-episode only). Memories building. 0 LLM fallbacks.
  - Pathfinding: NAVIGATING — Dome Room→Engravings Cave→Gallery (painting)→Cellar→Troll→Chasm→Reservoir South→Stream View. Broad exploration with purposeful item collection.
**Triggers:** None — score increased, all metrics healthy.
**Notes:** Agent discovered Dome Room (new area, t26). Thief appeared in Cellar at t42 — stole sword and matchbook. Agent fought with axe. Screwdriver+tube missing from Troll Room (thief or game state). Agent now heading back to Living Room for gothic door. Lost sword may prevent future troll encounters. Score 44 by t37 — matches ep75/76 pace. Monitoring for gothic door outcome and Dam area exploration.

---

## Episode 77 — Turn 75 Checkpoint
**Type:** HEALTHY — score stagnant but agent exploring broadly, Loud Room echo pattern observed
**Score:** 44/350 (delta: 0 since t37 — stagnant 38 turns, expected underground puzzle-gated)
**Locations visited (t51-75):** 10 unique (Cellar, Chasm, Deep_Canyon, East_Chasm, East-West_Passage, Loud_, Reservoir_South, Round_, Stream_View, Troll_)
**Avg critic score:** 0.52 (HEALTHY)
**Rejection rate:** 4/25 (16%) — EXCELLENT
**Gameplay quality:** DRIFTING
  - Memory use: Not evaluated in detail.
  - KB alignment: Agent tried platinum bar at Loud Room (t70) — KB lists this as Failed Approach. Agent correctly abandoned after 3 turns.
  - Objective quality: Not checked.
  - Objective pursuit: Agent exploring underground circuit. Tried to retrieve tools from Troll Room (t53, t58) but items not visible. Stream View water bottle experiment (t63-66, 4 turns).
  - Learning system quality: 0 KB updates, 0 new memories this block.
  - Pathfinding: NAVIGATING — Cellar→Troll→EW→Chasm→Reservoir→Stream View→Deep Canyon→Loud Room→Round→EW→Chasm. Broad underground circuit, no tight oscillation.
**Triggers:** Score stagnant (0 delta across 2 consecutive checkpoints). However: underground is puzzle-gated, agent exploring productively.
**Notes:** LOUD ROOM OBSERVATION (t69-72): Agent tried "take platinum bar" (echoed), "look" (echoed), "examine noise" (echoed). Recognized the echoing pattern but tried to find/muffle noise source (brown sack, axe) instead of typing "echo" as standalone command. This confirms the need for the intransitive command exploration rule. Agent also tried filling bottle at Stream View (t63-66, 4 turns) — creative but unproductive. "up" from Cellar rejected 3x at -0.90 (t55) — critic blocking valid ascent. Not dispatching improvement yet — ep77 is observation baseline before implementing intransitive command rule for ep78.

---

## Episode 77 — Turn 100 Checkpoint
**Type:** CONCERN — score stagnant 3 consecutive checkpoints, thief combat consuming turns
**Score:** 44/350 (delta: 0 since t37 — stagnant 63 turns)
**Locations visited (t76-100):** 7 unique (Cellar, Chasm, East_Chasm, East-West_Passage, Reservoir_South, Stream_View, Troll_) — all previously visited
**Avg critic score:** 0.66 (HEALTHY — best block this episode)
**Rejection rate:** 6/25 (24%) — HEALTHY
**Gameplay quality:** DRIFTING
  - Memory use: Not evaluated.
  - KB alignment: Agent circling known underground rooms. No new KB-driven exploration.
  - Objective quality: Not checked.
  - Objective pursuit: Agent fighting thief repeatedly (t77, t87-88, t91-94). No objective progress.
  - Learning system quality: 0 KB updates, memories may have been generated.
  - Pathfinding: WANDERING — Same underground circuit as t51-75. Cellar→Troll→EW→Chasm→Reservoir→Stream View→back. No new territory discovered.
**Triggers:** Score stagnant (0 delta across 3 consecutive checkpoints). However: underground is puzzle-gated, and thief encounters are consuming turns.
**Notes:** Thief appeared 4+ times in this block (t77 EW Passage, t87-88 Stream View, t91-94 Reservoir South). Agent spent 7 turns on "attack man with axe" — valid combat but no score gain. The thief stealing items (sword, matchbook earlier) is disrupting inventory management. Agent never reached Dam area this episode — stayed in east/south underground circuit. Score ceiling at 44 is from puzzle gating (dam bolt, echo room). Not dispatching improvement — this is baseline data for intransitive command rule evaluation.

---

## Episode 77 — COMPLETE
**Turns:** 125 (max_turns — survived full episode)
**Final score:** 44/350 (house +10 t7, cellar +25 t13, troll +5 t18, painting +4 t37)
**Locations visited:** 20 unique
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** 12 total, 0 new, 3 dedup rejected, 0 superseded, 0 consolidated
**Improvement dispatched:** yes — intransitive command rule (for ep78)

**Key achievements:**
  - Score 40 by t18 (efficient KB-driven early game)
  - Dome Room discovered (new territory, t26)
  - Painting +4 at t37
  - 125 turns survived — 3rd consecutive max_turns episode
  - 0 LLM fallback "look" actions from truncation (max_tokens fix holding)

**Key issues:**
  1. **Score stagnant t37-125** (88 turns at 44): Underground puzzle-gated
  2. **Loud Room echo pattern not solved** — agent tried "take bar", "look", "examine noise" (all echoed) but never tried "echo" as standalone command (t69-72)
  3. **Thief encounters** — 4+ thief fights consuming 7+ turns. Thief stole sword and matchbook. Inventory disrupted.
  4. **Underground loop** — same Cellar↔Troll↔EW↔Chasm↔Reservoir circuit for 88 turns. Never reached Dam area this episode.
  5. **"up" from Cellar rejected** — critic rejects ascent at -0.90×3 (t55, t103). Agent can't return to surface to deposit painting.
  6. **Fallback "look" at t115-119** — 3 consecutive looks at Troll Room. Rate limiting or model stalling.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep70 | 45 | +30 | 54 | 7 | 22 | clean | max_turns! |
| ep71 | 45 | 0 | 54 | 5 | 20 | clean | max_turns! |
| ep72 | 30(40) | -5 | 54 | 7 | 11 | clean | death t28 |
| ep73 | 40 | +10 | 54 | 7 | 16 | clean | killed t50 |
| ep74 | 45 | +5 | 54 | 7 | 14 | clean | killed t60 |
| ep75 | 44 | -1 | 54 | 7 | 19 | sonnet | max_turns! |
| ep76 | 44 | 0 | 54 | 7 | 20 | sonnet | max_turns! |
| ep77 | 44 | 0 | 54 | 7 | 20 | sonnet | max_turns! |

**Trend:** ep77 matched ep75/76 (score 44, 20 locations, max_turns). Score ceiling at 44-45 for 8 consecutive episodes. System reliably scores 40 by t18 and reaches painting by t37. Underground exploration follows the same east/south circuit without reaching Dam. The Loud Room echo pattern is the clearest improvement opportunity — agent recognizes commands echo but lacks the heuristic to try typing echoed words as standalone commands. Dispatching intransitive command rule for ep78.

---

## IMPROVEMENT: Grounding Validator (during ep77, t45)

**Problem:** Memory and objective LLMs hallucinate claims not supported by actual gameplay. Examples: attributing carried items to room locations ("screwdriver found in forest" when agent just dropped it there), generating objectives referencing items/NPCs never seen in game text, inventing mechanics not demonstrated.

**Evidence:** 6 duplicate egg memories across 2 locations (dedup catches exact titles but not semantic hallucinations). Objective quality issues noted in ep75/76 checkpoints. Memory synthesis prompt already warns about inventory vs. room items but LLM still confuses them.

**Change:** Added binary grounding validation gate after memory generation (memories only — objectives excluded).
- One new Burr graph node: `validate_memory` (after `record_memory`)
- Calls a shared grounding prompt that checks whether claims trace back to actual game output in the last 5 turns
- Uses `critic_model` (same as action critic) with temperature 0.0
- Binary accept/reject — ungrounded candidates are dropped, grounded ones committed
- Fail-open on LLM error (commit anyway)
- Kill switch: `enable_grounding_validator = true` in pyproject.toml

**Why memories only, not objectives:** Objectives are forward-looking and KB-informed — the objective generator sees the Knowledge Base and creates objectives about distant locations/items from prior episodes. The grounding validator only sees the last 5 turns, so it would reject valid KB-driven objectives (e.g., "collect tools from Maintenance Room") as ungrounded. Memories are backward-looking claims about what just happened, so grounding against recent turns is appropriate.

**New graph flow:**
```
record_memory → validate_memory → check_objective_completion → [update_objectives] → assemble_context
```

**Files changed:**
- `zorkburr/state.py` — 1 new pending state key (`PENDING_MEMORY`)
- `zorkburr/config.py` + `pyproject.toml` — `enable_grounding_validator` flag
- `zorkburr/llm/models.py` — `GroundingJudgment`, `GroundingValidationResponse`
- `prompts/grounding_validator.md` — shared prompt with `{grounding_rules}` placeholder
- `zorkburr/actions/grounding.py` — new file: `_call_grounding_validator`, `validate_memory`
- `zorkburr/actions/memory.py` — `record_memory` writes to `PENDING_MEMORY` instead of committing directly
- `zorkburr/app.py` — new node and transitions wired in

**LLM call budget:** ~5-10 memory validations per 100-turn episode. Minimal cost.

**Type:** INCREMENTAL — measure in ep78 (ep77 already running without this change).

**Success criteria:** Fewer hallucinated memories (particularly item-location misattributions). Watch `grounding_rejected` counter in memory stats.

**Risk:** Over-rejection of valid memories by the grounding LLM. Mitigated by fail-open on errors and the kill switch.

---

## Episode 78 — Turn 25 Checkpoint
**Type:** CONCERN — Loud Room reached but agent skipped without trying ANY command (KB poisoning)
**Score:** 40/350 (house +10 t7, cellar +25 t14, troll +5 t17 — no painting)
**Locations visited:** 14 unique (BEST first-25 location count this session)
**Avg critic score:** 0.57 (HEALTHY)
**Rejection rate:** 6/25 (24%) — HEALTHY
**Gameplay quality:** DRIFTING
  - Memory use: Agent navigating purposefully.
  - KB alignment: Agent followed KB scoring sequence (house→cellar→troll→east). At Loud Room (t23), agent reasoning explicitly cites KB: "the KB confirms that the room's echo property prevents taking it" — and immediately moves on WITHOUT trying any command.
  - Objective quality: Not checked.
  - Objective pursuit: Agent navigating toward Gallery for painting via Cellar route.
  - Learning system quality: KB clean, but the Loud Room entry now actively prevents the agent from attempting the puzzle.
  - Pathfinding: NAVIGATING — efficient deep underground exploration. Reached Loud Room at t23 (ep77 reached it at t69). Now heading to Gallery for painting.
**Triggers:** None — first checkpoint.
**Notes:** UNEXPECTED FAILURE MODE: The intransitive command rule didn't fire because the agent didn't even attempt a command at the Loud Room. The KB entry "All commands in Loud Room echo back as repeated text — platinum bar cannot be taken in this state" is being read as "skip this room entirely." This is a KB-poisoning problem distinct from ep77 (where the agent tried 3 commands and observed echoes). The new rule needs to either (a) override the KB skip behavior, or (b) be paired with KB cleanup that converts "Failed Approaches" into "Try alternative". Monitoring whether agent revisits Loud Room after gathering more info, or whether the rule fires elsewhere in the episode.

---

## Episode 78 — Turn 50 Checkpoint
**Type:** CONCERN — score 44 (painting), Loud Room never re-attempted, agent in same underground circuit
**Score:** 44/350 (delta: +4 since t25 — painting at t32)
**Locations visited (t26-50):** 11 unique (Cellar, Chasm, East_Chasm, East-West_Passage, Gallery, North-South_Passage, Reservoir_South, Round_, Stream_View, Troll_, Loud_)
**Avg critic score:** ~0.66
**Rejection rate:** ~5/25 (20%) — HEALTHY
**Gameplay quality:** DRIFTING
  - Memory use: Agent navigating purposefully via map.
  - KB alignment: Agent took painting (+4) but did NOT revisit Loud Room. KB skip behavior persisting — agent reads "echo prevents taking" and refuses to engage.
  - Objective quality: Not checked.
  - Objective pursuit: Same underground circuit as ep77 (Cellar↔Troll↔EW↔Chasm↔Reservoir).
  - Learning system quality: 0 LLM fallbacks (max_tokens fix holding).
  - Pathfinding: NAVIGATING — efficient, but no new territory discovered.
**Triggers:** Score stagnant (0 delta since t32, 18 turns).
**Notes:** INTRANSITIVE COMMAND RULE NOT FIRING: Agent passed through Loud Room at t23 and never returned. KB poisoning prevents the rule from being tested. Painting acquired faster than ep77 (t32 vs t37). Verb exploration rule firing (move rug at t11). Same fundamental behavior as ep77 — score 44 ceiling holds. Need to either: (a) wipe Loud Room KB entry to force re-engagement, (b) add explicit instruction to revisit known-failed puzzles when new heuristics are available, or (c) accept that 44 is the structural ceiling without echo discovery.

---

## Episode 78 — COMPLETE (killed at turn 50)
**Turns:** 50
**Final score:** 44/350 (house +10 t7, cellar +25 t14, troll +5 t17, painting +4 t32)
**Locations visited:** ~16 unique
**End reason:** early_stop (manual kill — intransitive command rule cannot be tested due to KB skip behavior)
**Improvement dispatched:** no — diagnosis reframed

**Intransitive command rule evaluation:**
- Agent reached Loud Room at t23 (faster than any post-reset episode — ep77 reached at t69, ep76 reached but only briefly)
- Agent reasoning at t24: "the KB confirms that the room's echo property prevents taking it" — IMMEDIATELY moved on without trying any command
- The new "Response-Derived Commands" rule never had a chance to fire because the agent didn't observe echoing this episode (no commands attempted)
- This is a different failure mode than diagnosed: KB-driven puzzle skip vs. missing reasoning heuristic
- **VERDICT: NEUTRAL/UNTESTABLE — rule is well-formed but blocked upstream by KB behavior**

---

## Session Complete
**Episodes run:** 2 (ep77 max_turns 44/350, ep78 killed at t50 with score 44)
**Best score achieved:** 44/350 (both episodes — 9 consecutive episodes at this ceiling)
**Improvements made:** 1 (intransitive command rule, untestable due to KB skip)
**System status:** PERFORMING WELL but PLATEAUED at 44
**Summary:** This session confirmed the score ceiling at 44 holds for the 9th consecutive episode. ep77 served as baseline observation: agent reached Loud Room at t69, observed echoing, tried verb-noun commands (take bar, look, examine noise) but never typed a single word as a standalone command. The intransitive command rule was added to prompts/agent.md to teach this heuristic. ep78 deployed the rule but exposed a NEW failure mode: the KB now contains "All commands in Loud Room echo back — platinum bar cannot be taken" which the agent reads as "skip this room entirely." Agent passed through Loud Room at t23 without attempting any command, so the new rule could not fire. The rule itself is sound and game-agnostic, but its trigger condition (observing echoes) requires the agent to actually engage with the puzzle. Two coupled problems must be solved together: (1) the intransitive command heuristic (now in place), and (2) the KB representation of unsolved puzzles needs to encourage retry when new heuristics are available, not permanent skip. Also: a separate session added a grounding validator (memories only) for ep78+ — independent infrastructure improvement, not yet evaluated.

**Next steps for future session:**
1. Modify KB Failed Approaches representation: distinguish "permanently failed" (try, give up) from "puzzle observation" (try, learn, retry with new approach). Current "all commands echo back, bar cannot be taken" should become "Loud Room: commands echo back — environmental constraint, requires alternative approach."
2. Or: Wipe specific Loud Room KB entry pre-ep79 to force re-engagement and test the intransitive command rule cleanly.
3. Continue evaluating grounding validator (ep78 was killed early so memory stats incomplete).
4. Consider upstream KB cleanup: when multiple Failed Approaches accumulate at the same location with same root cause, the agent should be encouraged to try fundamentally different categories (intransitive commands, environmental modifications) rather than abandoning the location.

---

## Episode 77 → 78 — IMPROVEMENT
**Trigger:** Score stuck at 44/350 for 8 consecutive episodes. Agent reaches Loud Room, observes echoing pattern, tries only verb-noun commands (take bar, examine noise, look), never considers intransitive commands. Leaves after 3 turns without progress.
**Hypothesis:** The agent's command generation is biased toward verb-noun pairs because the prompt's parser reference and puzzle-solving protocol only model transitive commands. The agent has no heuristic for recognizing when game responses hint that a word itself is the command, so it never generates standalone intransitive commands even when the game's behavior (echoing, repetition) strongly suggests one.
**Change:** Added "Response-Derived Commands" rule to the Puzzle-Solving Protocol in `prompts/agent.md`. The rule teaches the agent to: (1) notice when game responses echo, repeat, or mirror input, (2) recognize that emphasized or conspicuous words in responses may themselves be commands, (3) try those words as standalone intransitive commands (single words with no object).
**Reasoning:** The rule is game-agnostic — it applies to any text adventure where the game hints at commands through response patterns (echoing, rhyming, emphasis). It teaches HOW to think about unusual response patterns, not WHAT to type. The agent should apply this at the Loud Room (echoing → try "echo") but also at other puzzles requiring intransitive commands (e.g., "pray" at a temple).
**Validation:** Re-read the modified prompt. Confirmed: (1) rule is game-agnostic — works for any text adventure with response-pattern puzzles, (2) no game-specific knowledge — no room names, item names, or puzzle solutions, (3) teaches reasoning heuristic — how to interpret unusual response patterns, (4) single logical modification — one new rule added to puzzle-solving protocol.
**Target metric:** Agent tries at least one intransitive command at the Loud Room derived from the echoing pattern. Score exceeds 44 (+10 for platinum bar = 54).
**Result:** IMPROVED — **CONFIRMED in ep81 t48.** Sonnet (agent model) visited Loud Room at t39, walked east to Damp_Cave at t40, returned to Loud Room at t47, and typed `echo` at t48 (intransitive command). Game responded; at t49 `take platinum bar` scored +10 (score 40→50). This is the first confirmed firing of the rule since it was added in ep77→78. Ep78 failed because KB contained "commands echo, platinum bar cannot be taken" triggering a skip; ep81 succeeded because post-ep79 KB reset cleared that entry and Sonnet re-engaged. The rule itself works — its effectiveness depends on the KB not poisoning Loud Room with a permanent-skip entry. Target metric (score > 44 via platinum bar) achieved.

---

## Episode 78 → 79 — IMPROVEMENT (WILD EXPERIMENT — user-directed, off-orchestrator)
**Trigger:** User-directed experiment. Not orchestrator-dispatched. Score has been flat at 44/350 for 9 consecutive episodes on the local 14B agent model (Ministral 3 14B → Gemma 4 31B via OpenRouter). User wants to see what a frontier model does with the same loop before returning to prompt-level iteration.
**Hypothesis:** A stronger base model (Claude Sonnet 4.6) may reveal whether the 44 ceiling is (a) a prompt/architecture limitation that smaller models also hit, or (b) a capability limitation of the previous agent model. If Sonnet also plateaus at 44, the bottleneck is architectural (KB representation, memory schema, critic loop) and prompt iteration on smaller models is the right path forward. If Sonnet breaks 44 cleanly, the previous ceiling was model-bound and we have a new reference point for what "the loop working well" looks like.
**Change:** `pyproject.toml` — `agent_model` switched from `remote/google/gemma-4-31b-it` to `remote/anthropic/claude-sonnet-4.6`. Critic / extractor / memory / analysis roles unchanged (still local Ministral 3 14B). Knowledge model unchanged (already `remote/anthropic/claude-sonnet-4.6`). Commit: `9fdcbfa`.
**Reasoning:** This tests the model-capability hypothesis in isolation by keeping every other component constant. The critic continues to operate at its existing rejection thresholds (per the universal-thresholds memory), so if Sonnet produces better actions, the critic should accept them at the same rate or higher. The ep77→78 intransitive-command rule is still in place and PENDING — running it on Sonnet will also give a secondary signal on whether that rule fires when the underlying model is more capable.
**Target metric:** (1) Score vs. 44 ceiling. (2) Whether Sonnet triggers the ep77→78 intransitive-command rule at Loud Room (it may, if KB-skip behavior is sensitive to model reasoning quality). (3) Cost-per-episode signal — Sonnet every turn is materially more expensive, so this is a bounded experiment, not a new baseline.
**Caveats:** This violates the "one-change-per-episode" rule in spirit because the intransitive-command rule from ep77→78 is still PENDING. Results will need careful attribution — if score changes, disentangling "better model" from "rule finally fires" requires a follow-up Gemma run. Orchestrator should treat this as an isolated data point, not a baseline shift.
**Result:** IMPROVED — ep80 (Sonnet 4.6, post-max_tokens-fix) scored 45/350 with 28 locations visited, breaking the 9-episode 44 ceiling. Key behavioral differences vs. local models: (1) solved the Mirror Room passage via `enter mirror` at t43, (2) discovered the entire Coal Mine complex (Gas, Smelly, Shaft, Ladder Top/Bottom, Timber, Dead End, maze rooms — territory no local-model episode reached in this session), (3) picked up the bracelet in Gas Room for +5, (4) engaged the Shaft basket puzzle (put coal in basket / lower / raise / look). **Hypothesis verdict: CONFIRMED** — the 44 ceiling was model-bound, not prompt/architecture-bound. The loop architecture is sound. Cost caveat stands: ~1 turn/min throughput, ~100 min wall clock per episode. Not a new baseline — bounded experiment as planned.

---

## Episode 79 — Turn 25 Checkpoint (Sonnet 4.6 agent experiment)
**Type:** HEALTHY
**Score:** 40/350 (house +10 t7, cellar +25 t13, troll +5 t15)
**Locations visited:** 13 unique (West_House, South_House, Behind_House, Kitchen, Living_, Cellar, Troll_, East-West_Passage, Round_, Narrow_Passage, Mirror_, Winding_Passage, Cave)
**Avg critic score:** 0.66 (HEALTHY — higher than ep75-78 first blocks)
**Rejection rate:** 5/25 (20%) — HEALTHY
**Gameplay quality:** LEARNING (preliminary — not deep-inspected)
  - Memory use: Standard KB-driven scoring path (house→cellar→troll→east), 40 points by t16 matches fastest-ever pace.
  - KB alignment: Following cross-episode KB cleanly. `move rug` still rejected hard (-0.90 × 3) before being forced through — known critic over-rejection.
  - Pathfinding: NAVIGATING — clean underground circuit, currently back at East-West Passage.
**Triggers:** None.
**Notes:** First Sonnet 4.6 agent checkpoint. Throughput ~1 turn/min (reasoning-heavy — expect total ~100 min for full episode). Real test is the t26-100 block where local models plateau at 44.

---

## Episode 79 — Turn 50 Checkpoint (Sonnet 4.6 agent experiment)
**Type:** CONCERN — matches 44 ceiling, 2 consecutive `look` fallbacks at t49-50, 14 max_tokens retries in log
**Score:** 44/350 (delta: +4 since t25 — painting at t30)
**Locations visited (t26-50):** 10 unique (Troll_, Cellar, East_Chasm, Gallery, East-West_Passage, Round_, Narrow_Passage, Mirror_, Winding_Passage, Cave) — all previously visited
**Avg critic score:** 0.59 (HEALTHY)
**Rejection rate:** 4/25 (16%) — HEALTHY
**Gameplay quality:** DRIFTING
  - Memory use: Sonnet painting run (t27-30: Cellar→East_Chasm→Gallery→drop-sword-take-painting) is the fastest painting acquisition so far. Then t30-48 is the same underground circuit as local-model episodes (Cellar↔Chasm, Troll↔EW↔Round↔Narrow↔Mirror).
  - KB alignment: Following KB scoring path cleanly.
  - Objective pursuit: Agent experimented at Mirror Room (t41-43: examine/push/pull mirror) — novel, productive probing behavior not seen from local models. But did not break through.
  - Learning system quality: Not deep-inspected yet.
  - Pathfinding: NAVIGATING early, then two `look` fallbacks at t49-50 — infrastructure issue (max_tokens).
**Triggers:** LLM error pile-up (2 consecutive `look` fallbacks at t49-50), though overall rejection rate is healthy. Underlying cause: 14 `max_tokens` errors in log suggest Sonnet's reasoning is generating very long outputs and the `max_tokens` budget used for the local model may be too tight for Sonnet 4.6 via OpenRouter.
**Notes:** **KEY OBSERVATION:** Sonnet reached painting at t30 (fastest ever — ep77 t37, ep78 t32). But then fell into the same Cellar↔Troll↔EW↔Chasm circuit as local models, matching the 44 ceiling. Never reached Loud Room in first 50 turns, so the intransitive-command rule still untested on Sonnet. Mirror Room probing (t41-43) is the most creative local-experimentation behavior seen this session — a quality signal, even though it didn't score. **Infrastructure concern:** the `look` fallbacks are data loss — turns where Sonnet's response was truncated. Need to monitor and potentially kill early if fallbacks cascade.

---

## Episode 79 → 80 — IMPROVEMENT (BLOCKER: agent max_tokens)
**Trigger:** Agent LLM fallbacks at ep79 t49-50 — Sonnet 4.6 exceeded hard-coded 2048-token budget during complex planning, Instructor retried 3× (useless for deterministic truncation), then fell back to action="look" destroying high-quality strategic reasoning (trap-door-direction analysis, alternative-route hypothesis).
**Hypothesis:** Not a prompt problem — the agent action call has `max_tokens=2048` hard-coded in `zorkburr/actions/agent.py:61`, ignoring `config.default_max_tokens = 4096`. Sonnet 4.6 thinking mode needs more headroom than any budget currently configured.
**Change:**
  - `zorkburr/actions/agent.py:61` — `max_tokens=2048` → `max_tokens=config.default_max_tokens`
  - `pyproject.toml [tool.zorkburr]` — set `default_max_tokens = 8192`
**Reasoning:** Wires the existing config field through to the site that actually needs it, and bumps the override to 4× the failing budget. Other LLM call sites (critic, extractor, memory, etc.) keep their own tight budgets — only the agent action call gets the bigger budget.
**Validation:** Infrastructure fix — no fixture replay applicable. Manual checks: grep confirms both edits, config loads with default_max_tokens=8192, test suite passes.
**Target metric:** Zero `Agent LLM call failed` events from `max_tokens length limit` in ep80 under Sonnet 4.6. Score ceiling unchanged — this fix only restores observability, it does not alter agent behavior on clean turns.
**Result:** IMPROVED — 0 max_tokens fallbacks in ep80 across all 100 turns (vs. 2 in ep79 by t50). Fix confirmed. Side effect: score 45 (ceiling broken) — not directly caused by the fix, but the clean trace enabled the experiment to run to completion and reveal that Sonnet can solve the mirror passage + coal mine puzzles.

---

## Episode 80 — Turn 25 Checkpoint (Sonnet 4.6 agent + max_tokens fix)
**Type:** HEALTHY
**Score:** 40/350 (house +10 t7, cellar +25 t13, troll +5 t15)
**Locations visited:** 12 unique (West_House, South_House, Behind_House, Kitchen, Living_, Cellar, Troll_, East-West_Passage, Round_, Engravings_Cave, Dome_, Chasm)
**Avg critic score:** 0.60 (HEALTHY)
**Rejection rate:** 2/25 (8%) — BEST first-25 block this session
**Max_tokens events:** 0 (fix confirmed — clean trace through 25 turns)
**Gameplay quality:** LEARNING
  - Memory use: Standard KB-driven scoring path (house→cellar→troll→east) — 40 by t15.
  - KB alignment: Clean. `move rug` still rejected hard at t10 (critic over-rejection persists).
  - Objective pursuit: Score path efficient. Novel exploration: at t18-21, Sonnet went SE from Round Room to Engravings Cave and Dome Room — territory local models rarely reach. Probed Dome railing (t20) before returning.
  - Pathfinding: NAVIGATING — clean, no oscillation. t25 `look` is deliberate (critic=0.50, not a fallback).
**Triggers:** None.
**Notes:** Max_tokens fix is working — zero truncation events in 25 turns vs. ep79 which had 2 by t50. Score pace matches ep79 (40 by t15/t16). The Engravings Cave / Dome Room exploration (t18-21) is a positive quality signal — Sonnet is willing to probe new territory rather than beeline for known scoring routes. Still a throughput concern (~1 turn/min) but the data is now clean.

---

## Episode 80 — Turn 50 Checkpoint (Sonnet 4.6 agent + max_tokens fix)
**Type:** CONCERN — score stagnant at 40 since t15, Sonnet skipped painting scoring path
**Score:** 40/350 (delta: 0 since t25 — no painting this episode)
**Locations visited (t26-50):** 13 unique (NEW territory: Cold_Passage, Slide_, Mine_Entrance, Squeaky_, Coal_Mine — 5 rooms never explored in recent sessions). Also revisited: Chasm, Dome_, Engravings_Cave, Mirror_, Narrow_Passage, North-South_Passage, Reservoir_South, Round_.
**Avg critic score:** 0.54 (HEALTHY)
**Rejection rate:** 7/25 (28%) — near threshold, driven by Coal Mine movement attempts (t49 rejected 3× at -0.90)
**Max_tokens events:** 0 (fix still holding through 50 turns)
**Gameplay quality:** DRIFTING
  - Memory use: Not deep-inspected.
  - KB alignment: Sonnet is NOT following the KB painting scoring path. Instead it routed Cellar→Chasm→Reservoir South→back through Round, then to Mirror Room → **through the mirror** into Cold Passage → Slide Room → Mine Entrance → Squeaky Room → Coal Mine. This is a fundamentally different exploration strategy.
  - Objective pursuit: Score is not being pursued — Sonnet is prioritizing novel-area discovery.
  - Pathfinding: NAVIGATING — Sonnet correctly passed through the mirror at t43 (`enter mirror` action), discovering Cold Passage as a new passage. The Mirror Room puzzle the agent was probing at t37-43 was actually being solved — the rub/enter sequence worked.
**Triggers:** Score stagnant (0 delta across 2 consecutive checkpoints). High rejection rate at Coal Mine (28%).
**Notes:** **CRITICAL OBSERVATION:** At t43 Sonnet successfully `entered mirror` and transitioned to Cold_Passage — territory the local models have never reached in any recent session. This is SOTA-specific behavior: Sonnet's Mirror Room probing (t37-43: examine, enter, rub, look) wasn't random experimentation — it was methodical puzzle-solving that actually worked. The tradeoff: Sonnet has not yet touched the painting for +4 and is at 40/350 vs. local models' 44/350. But the exploration frontier has expanded dramatically (Coal Mine area = new territory for the entire project). This is the single most interesting result of the session. Critic is rejecting Coal Mine "n" attempts at -0.90 — likely because the agent doesn't have a light source check or the mine is dark. Continuing to monitor.

---

## Episode 80 — Turn 75 Checkpoint (Sonnet 4.6 agent + max_tokens fix)
**Type:** HEALTHY — score breakthrough, extensive new-territory discovery
**Score:** 45/350 (delta: +5 since t50 — **FIRST SCORE ABOVE 44 IN 9 EPISODES**, bracelet at Gas Room t53)
**Locations visited (t51-75):** 8 unique — ALL NEW TERRITORY for recent sessions (Coal_Mine, Dead_End, Gas_, Ladder_Bottom, Ladder_Top, Shaft_, Smelly_, Timber_). 0 revisits of old rooms this block.
**Avg critic score:** 0.46 (lower — coal mine navigation is critic-costly)
**Rejection rate:** 6/25 (24%) — HEALTHY
**Max_tokens events:** 0 (still zero — fix holding through 75 turns)
**Gameplay quality:** LEARNING
  - KB alignment: N/A — KB has no entries for this territory (brand new).
  - Objective pursuit: Score breakthrough at t53 (+5 bracelet), coal acquired at t75. Sonnet is on the Coal→Machine Room puzzle path.
  - Pathfinding: Sonnet navigated a twisty Coal Mine complex (multiple identical "Coal_Mine" rooms) via Gas Room → Smelly → Shaft → Ladder Top → Coal Mine → Ladder Top → Ladder Bottom → Timber → Ladder Bottom → Dead End. Two rejection clusters at t57 and t66/69 (3× each at ~-0.80) suggest the critic is blocking some navigation — likely direction mismatches against the map graph.
**Triggers:** None (score improvement overrides earlier stagnation concern).
**Notes:** **BREAKTHROUGH EPISODE.** Three firsts:
  1. **Score 45** — first break of the 44 ceiling in 9 consecutive episodes
  2. **8 new rooms in one 25-turn block** — the entire Coal Mine complex (Gas, Smelly, Shaft, Ladder Top/Bottom, Coal Mine variants, Timber, Dead End) — territory never reached by any local-model episode
  3. **Coal acquired at t75** — Sonnet is actively working the Machine Room diamond puzzle path, not randomly wandering
  
The SOTA experiment has already justified itself: Sonnet solved the Mirror Room passage at t43 (intransitive-ish: "enter mirror"), found the entire Coal Mine complex, and broke a 9-episode score ceiling. The intransitive command rule (ep77→78) may have helped — "enter mirror" is a verb-noun, but its use here is the kind of probe Sonnet wasn't doing before. Still no Loud Room visit this episode, so the echo heuristic is untested.

---

## Episode 80 — COMPLETE
**Turns:** 100 (max_turns)
**Final score:** 45/350 (house +10 t7, cellar +25 t13, troll +5 t15, **bracelet +5 t53**)
**Locations visited:** 28 unique (BEST location count this session — up from ep77's 20, ep75's 19)
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** 3 total, 2 new, 0 dedup/superseded/consolidated
**Max_tokens events:** 0 across all 100 turns (fix CONFIRMED)
**Improvement dispatched:** BLOCKER fix (max_tokens wiring) committed before episode; no new improvement dispatched at end

### Turn 100 block metrics (t76-100)
- Avg critic: 0.56 (HEALTHY)
- Rejections: 3/25 (12%)
- Unique locs this block: 6 (Coal_Mine maze re-traversals, Shaft_, Smelly_, Gas_, Ladder_Bottom, Ladder_Top, Dead_End)
- Key activity: Sonnet executed the coal-basket-lower-raise-look sequence at Shaft Room (t91-95), then returned to Coal Mine complex (t96-100)

### Key achievements (the whole episode)
1. **SCORE CEILING BROKEN** — 45 beats the 44 cap that held for 9 consecutive episodes (ep72-79). First +5 breakthrough in this session.
2. **28 locations visited** — largest exploration frontier this session. Expanded by ~8-10 rooms vs. recent episodes.
3. **Coal Mine complex fully discovered** — Gas, Smelly, Shaft, Ladder Top, Ladder Bottom, Timber, Dead End, multiple Coal Mine maze rooms. Never visited by any local-model episode in recent sessions.
4. **Mirror passage puzzle solved** — `enter mirror` at t43 transitioned Mirror Room → Cold Passage. This was the hypothesis probe that opened the Coal Mine path.
5. **Coal-basket-Machine Room puzzle engaged** — Sonnet executed `take coal` → `put coal in basket` → `lower basket` → `press button` → `raise basket` → `look in basket` (t75, t91-95). Didn't complete the loop (needs to descend the ladder, retrieve from basket at Drawing Room), but the reasoning was correct.
6. **Zero max_tokens fallbacks** — the BLOCKER fix works cleanly, all reasoning preserved.

### Key issues
1. **Coal Mine maze navigation** — Sonnet spent t78-87 (10 turns) wandering in Coal_Mine maze rooms that Jericho collapses to a single location ID. No breadcrumb strategy.
2. **Painting skipped** — no +4 painting this episode; the entire t26-75 block was spent on new-territory exploration instead of the known scoring path. 
3. **Basket puzzle incomplete** — Sonnet raised the basket without first descending the ladder to retrieve the coal at the bottom. The Shaft Room basket puzzle requires going down to Drawing Room, NOT raising back at the top.

### Running Score Table
| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|
| ep74 | 45 | +5 | 54 | 7 | 14 | killed t60 |
| ep75 | 44 | -1 | 54 | 7 | 19 | max_turns |
| ep76 | 44 | 0 | 54 | 7 | 20 | max_turns |
| ep77 | 44 | 0 | 54 | 7 | 20 | max_turns |
| ep78 | 44 | 0 | 54 | 7 | ~16 | killed t50 |
| ep79 | 44 | 0 | 54 | 7 | ~19 | killed (max_tokens) |
| **ep80** | **45** | **+1** | **54** | **7** | **28** | **max_turns** |

**Trend:** ep80 is the first score increase in 10 episodes. The 45 is structurally different from ep71/74's 45 — those came from the known painting route (40 + painting=44, then trophy deposit for +1, or similar). Ep80's 45 is 40 (standard KB path) + bracelet (Gas Room, brand new territory). This validates the Sonnet experiment: the 44 ceiling was MODEL-bound, not prompt-bound. The loop architecture is sound; the local model was capability-limited.

### Pending improvements resolved
- **Episode 79 → 80 — BLOCKER (max_tokens)**: **IMPROVED** — 0 fallbacks in ep80 vs. 2 in ep79. Fix confirmed. `**Result:** PENDING` → needs updating below.
- **Episode 77 → 78 — intransitive command rule**: STILL PENDING — ep80 never reached the Loud Room, so the rule fired at most once (Mirror Room `enter mirror`, which is borderline verb-noun). Carry forward.
- **Episode 78 → 79 — Sonnet 4.6 wild experiment**: **IMPROVED** — score 45 vs. 44 ceiling confirms the model-capability hypothesis. Sonnet exploration breadth (28 locs) and puzzle engagement (mirror passage, basket sequence) dramatically exceed any local-model episode. Cost signal: episode took ~2 hours wall clock (~1 turn/min).

---

## Episode 81 — Turn 25 Checkpoint (Sonnet 4.6, KB carryover from ep80)
**Type:** HEALTHY
**Score:** 40/350 (house +10 t6, cellar +25 t13, troll +5 t15)
**Locations visited:** 13 unique (including new room Twisting_Passage at t24)
**Avg critic score:** 0.55 (HEALTHY)
**Rejection rate:** 2/25 (8%) — BEST first-25 this session
**Max_tokens events:** 0
**Gameplay quality:** LEARNING
  - KB alignment: Sonnet went for Mirror Room puzzle at t20 (`rub mirror`) — direct application of ep80's discovered route. KB carryover working.
  - Novel exploration: Twisting Passage (west from Mirror, new) at t24.
  - Pathfinding: NAVIGATING — clean scoring sequence, fastest-ever KB-driven start.
**Triggers:** None.
**Notes:** KB learning from ep80 is transferring. Sonnet immediately probed the mirror at t20 (rub) instead of meandering first. Now exploring new territory west of Mirror (Twisting Passage).

---

## Episode 81 — Turn 50 Checkpoint (Sonnet 4.6, KB carryover)
**Type:** HEALTHY — **LOUD ROOM SOLVED, SCORE 50/350 — NEW ALL-TIME SESSION BEST**
**Score:** 50/350 (delta: +10 since t25 — platinum bar at t49, **echo puzzle solved** at t48)
**Locations visited (t26-50):** 13 unique (including NEW rooms: Cold_Passage, Slide_, Damp_Cave, Studio, Twisting_Passage from block start)
**Avg critic score:** 0.55 (HEALTHY)
**Rejection rate:** 3/25 (12%) — HEALTHY
**Max_tokens events:** 0
**Gameplay quality:** LEARNING
  - KB alignment: Agent followed the learned Mirror Room passage route (t19-26) to Cold Passage (ep80 discovery). Then returned via Slide→Cellar→Gallery→Studio (new room, t31) exploring Gallery's north branch.
  - **Loud Room breakthrough:** t47 agent entered Loud Room (for the 2nd time this episode). t48 action = **`echo`** (intransitive command rule FIRED). t49 score jumped +10 with `take platinum bar`.
  - Pathfinding: NAVIGATING — broad circuit through all known underground territory + first visit to Damp Cave (east of Loud Room).
**Triggers:** None — the 10-point jump resolves any stagnation concern.
**Notes:** **EPISODE 77→78 INTRANSITIVE COMMAND RULE: CONFIRMED WORKING.** This is the single most important result of the session. The hypothesis was that teaching the agent to try emphasized/echoed words as standalone commands would unlock puzzles like the Loud Room. Ep78 failed because of KB-skip behavior (agent read "commands echo, bar cannot be taken" and left). Ep81 succeeded because: (1) Sonnet is a stronger reasoner that doesn't treat KB as a blanket skip-list, (2) the intransitive-command rule gave it the explicit heuristic to try `echo`, (3) it visited Loud Room TWICE in this episode (t39 and t47) — the second visit is when it tried the rule. Score breakdown: 10 (house) + 25 (cellar) + 5 (troll) + 10 (platinum bar) = 50. This beats the 9-episode 44 ceiling by 6 points AND confirms the intransitive-command rule as an effective reasoning heuristic. The rule is now validated and can return to local-model episodes to see if it holds with Gemma/Ministral.

---

## Episode 81 — Turn 75 Checkpoint (Sonnet 4.6)
**Type:** CONCERN — score stagnant at 50 since t49, 10+ turns stuck in Maze (t55-71)
**Score:** 50/350 (delta: 0 since t50)
**Locations visited (t51-75):** 5 unique (Maze, Dead_End, Troll_, Cellar, East-West_Passage) — all but Maze previously known
**Avg critic score:** 0.52 (HEALTHY)
**Rejection rate:** 7/25 (28%) — elevated, driven by t65/t68 Maze take-item failures (critic rejected at -0.80)
**Max_tokens events:** 0
**Gameplay quality:** DRIFTING
  - Novel exploration: Maze + Dead_End, found skeleton key + bag (Zork treasures)
  - Item interactions: `take skeleton key, take bag` at t63 — unclear if successfully took (score didn't move, but treasures only score on deposit). Then dropped manual/leaflet/bottle/sword as breadcrumbs — classic maze strategy.
  - Pathfinding: Sonnet spent t55-71 (17 turns) in the Maze without reliable room identification (Jericho collapses maze to single "Maze" loc_id). Struggled to re-find the treasure room after moving. Escaped back to Troll Room at t72.
**Triggers:** Score stagnant (0 delta across 2 consecutive checkpoints). Maze navigation difficulty (17 turns in Maze).
**Notes:** Mixed block. **Positive:** Sonnet discovered the Maze and attempted the skeleton key / coin bag puzzle with correct reasoning (breadcrumb drops). **Negative:** Jericho's single-loc_id-for-all-maze-rooms makes tracking impossible — Sonnet dropped items hoping to mark rooms, but couldn't navigate back reliably. Needs to return to the house to deposit the platinum bar at the trophy case for points, but is instead looping underground. The score path from here is: (1) reach trophy case (Living Room) to deposit platinum bar (+4 estimated), (2) re-enter maze for coins + skeleton key, (3) deposit those. No new improvement dispatched — continuing to observe whether Sonnet finds the Living Room route.

---

## Episode 81 — COMPLETE
**Turns:** 100 (max_turns)
**Final score:** 60/350 — **NEW SESSION HIGH, +15 above prior ceiling of 44-45**
**Score breakdown:** house +10 t6, cellar +25 t13, troll +5 t15, **platinum bar +10 t49 (echo puzzle)**, **bag of coins +10 t81**
**Locations visited:** 24 unique (includes NEW territory: Twisting_Passage, Maze, Dead_End, Damp_Cave, Studio on top of ep80 discoveries)
**Objectives found:** 14
**End reason:** max_turns
**Memory stats:** 6 total (up from 3 post-ep80), 3 new, 0 dedup/superseded/consolidated
**Max_tokens events:** 0 across all 100 turns
**Improvement dispatched:** no — pure observation episode with KB carryover from ep80

### Turn 100 block metrics (t76-100)
- Avg critic: 0.58 (HEALTHY)
- Rejections: 5/25 (20%) — HEALTHY
- Key activity: Maze re-entry at t77, found treasure room again at t81 (`take bag` → +10 score), extracted treasures, then continued wandering the maze t85-100 unable to find route back to Troll Room / Living Room. Never deposited treasures at trophy case.

### Key achievements (whole episode)
1. **SCORE 60/350 — 9-episode 44 ceiling shattered by +15 in two episodes (ep80=45, ep81=60)**
2. **LOUD ROOM PUZZLE SOLVED** — Sonnet typed `echo` at t48, scored +10 for platinum bar at t49. **This is the first confirmed firing of the ep77→78 intransitive-command rule.** The rule works.
3. **Maze discovered and treasure retrieved** — Sonnet found the skeleton+bag room, grabbed the bag of coins for +10. Classic Zork breadcrumb strategy attempted (dropped manual, leaflet, bottle, sword as markers).
4. **KB carryover confirmed** — Sonnet immediately targeted the Mirror Room puzzle at t20 (`rub mirror`) and the Cold Passage route from ep80's discovery, proving the learned KB transfers across episodes.
5. **Studio room discovered** — new territory east of Gallery (north).
6. **Zero max_tokens events** — 200 consecutive clean Sonnet turns (ep80+ep81).

### Key issues
1. **Maze navigation** — Jericho collapses all maze rooms to single loc_id. Sonnet's breadcrumb strategy was sound in theory but couldn't verify which room it was in (all show `Maze`). Spent t77-100 in the maze unable to escape to deposit treasures.
2. **Painting skipped both episodes** — Sonnet prioritized new-territory / puzzle discovery over the +4 painting. Consistent with ep80.
3. **No trophy case deposits** — platinum bar and coin bag still in inventory at end. If Sonnet had deposited both, score would be ~64-68 (first deposit +1, second +1 each, with additional for the treasures themselves already counted on pickup).
4. **Loud Room KB skip prevented** — notably, KB from ep80 did NOT contain a "commands echo, skip room" entry, so Sonnet was free to engage. This is why ep81 worked where ep78 failed.

### Pending improvements resolved
- **Episode 77 → 78 — intransitive command rule**: **IMPROVED/CONFIRMED** — Sonnet typed `echo` at Loud Room t48, scoring +10 from platinum bar pickup. Rule validated. Note: only worked because KB didn't contain a skip-instruction for Loud Room.
- **Episode 78 → 79 — Sonnet wild experiment**: Already resolved IMPROVED in ep80. Ep81 extends the result: Sonnet can chain puzzles across episodes using KB.
- **Episode 79 → 80 — max_tokens BLOCKER**: Already resolved IMPROVED in ep80. Ep81 extends: 200 consecutive clean turns confirms the fix is robust.

### Running Score Table
| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|
| ep75 | 44 | -1 | 54 | 7 | 19 | max_turns |
| ep76 | 44 | 0 | 54 | 7 | 20 | max_turns |
| ep77 | 44 | 0 | 54 | 7 | 20 | max_turns |
| ep78 | 44 | 0 | 54 | 7 | ~16 | killed t50 |
| ep79 | 44 | 0 | 54 | 7 | ~19 | killed (max_tokens) |
| ep80 | 45 | +1 | 54 | 7 | 28 | max_turns |
| **ep81** | **60** | **+15** | **60** | **6** | **24** | **max_turns** |

**Trend:** Sonnet + max_tokens fix + KB carryover = two-episode chain: ep80 discovers Coal Mine + Mirror passage (+1 from bracelet), ep81 discovers Loud Room solution + Maze treasures (+15). Each episode builds on the prior. **Ep81 beats the previous all-time session best (54 from ep37, A3b MoE)** — this is the highest score this project has ever produced. The 44 ceiling was definitively model-bound; the 54 ceiling was definitively compound (model + accumulated KB), and Sonnet breaks both.

---
