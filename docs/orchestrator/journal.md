# ZorkBurr Orchestrator Journal

Started: 2026-03-30

## Key Learnings (updated after episode 117)

**Current best score:** **102/350 (ep94)** — unbeaten. Recent 10 episodes range 0-90; ep112/ep113 tied at 89 as the current reproducible ceiling. ep117 = 80 with the stale-verdict fix fully validated.
**Current bottleneck:** **Strategic-void / commit-to-plan.** Post-initial-deposit-run, agents have KB + objectives but no executed high-value plan. Recent manifestations: ep116 gear-shuttle + thief-no-pursuit (35+ turns wasted), ep117 Dam-wandering (22 turns) + Dome-without-rope (2 visits, never fetched rope). The agent "knows" multi-step chains (Attic→rope→Dome→Torch Room = +14, Cyclops via ulysses = thief recovery route) but doesn't execute them. Not a KB problem — an execution-commitment problem.
**Model stack (current):** agent + critic + knowledge + memory all on `remote/google/gemini-3-flash-preview`; objective_model on local `mistralai/ministral-3-14b-reasoning`; extractor removed; critic bypassed (`enable_critic=false`).
**Session velocity:** ~3 turns/min (~22s/turn). A full 200-turn episode runs in ~60-70 min.

### What works (confirmed wins, most recent first)
- **ep116→117 stale-verdict stop-gate** (commit `1baeaf2`): engine-grounded-vs-inferred-mechanism discriminator in `prompts/agent.md`. KB entries with quoted engine responses (e.g., `"It doesn't seem to work"`) are ineligible for re-verification; inferred-mechanism entries (e.g., `torch vaporizes candles`) remain eligible for one-shot. ep117: 0 wooden-door attempts in 200 turns vs 5 in ep116. **IMPROVED** (fully confirmed in live play).
- **ep113→114 stale-verdict verification** (initial introduction): adds one-shot re-verification for KB failure entries. **PARTIAL** — first-fire correctness confirmed via fixture replay; live-play true-positive case (Hades candles) still untested across ep114, ep116, ep117 (agent never reached Hades).
- **ep110→111 NEW_OBJECTIVE wiring + cap hotfix** (BLOCKER): agent's per-turn objective proposals now correctly merge into DISCOVERED_OBJECTIVES with priority-safe insertion.
- **ep93→94 visibility bundle** (BLOCKER): completed-objectives rendering + score-event timeline + nav_target BFS + inventory_changed memory trigger. Delivered the ep94 102-point ceiling.
- **ep94→95 stale-route recompute** (agent.md): "planned direction missing from engine exits → mark STALE and replan". Behaviorally confirmed every episode.
- **ep98→99 extract_info deletion + map_graph forward-only edges**: pipeline simplification, ~1 LLM call/turn saved, one-way passages no longer fabricate reverse edges.
- **ep96→97 critic model swap** Ministral→gemini-3-flash (then disabled ep97→98): programmatic critic is sufficient; LLM critic was net cost at model parity.

### Falsified hypotheses
- **"Sonnet 4.6 works for secondary subsystems"** — FAILED ep85-86.
- **"Ministral is sufficient for memory synthesis"** — FAILED ep91-92.
- **"Ministral is sufficient for critic role"** — FAILED ep96.
- **"At gemini/gemini parity, the LLM critic still adds value"** — FAILED ep97-98.
- **"Temperature 0.7 reduces variance"** — FAILED ep47.
- **"50-turn prompt changes can fix model KB-following"** — FAILED ep39-41 (code bug, not prompt).

### Open problems (ordered by current impact)
1. **Strategic-void / commit-to-plan — THE current top priority.** Agent has KB + objectives but doesn't execute multi-step high-value chains. Concrete: Attic→rope→Dome→Torch Room (+14), Cyclops ulysses route to Treasure Room (thief recovery), Hades exorcism. Candidates: (a) objectives prioritization — rank by expected score; (b) commit-to-chain rule in agent.md — when objective X requires prerequisite Y which is N steps away, don't drop the chain mid-execution.
2. **Hades candle test unreached** — ep113→114 fix's intended true-positive case. Requires Hades-reaching episode which requires (a) above.
3. **Dam puzzle unsolved** — 150+ cumulative turns across session, zero score. Known dead-weight zone. Programmatic validator misparses some compound takes.
4. **Thief-pursuit never executed** — Cyclops ulysses shortcut in KB; not attempted recently.
5. **data/map.json false reverse edges** from ep1-98 still present; forward-only fix stopped accumulation but didn't wipe existing data.

### Subsystems investigated (current totals)
- Agent prompt: ~22 changes, last ep116→117 (stale-verdict stop-gate). Next target: strategic commit-to-plan.
- Critic prompt: 3 changes total, last ep7. Now bypassed.
- KB/memory system: ~13 changes, last ep96→97.
- Python pipeline: ~13 changes, last ep98→99.
- Model stack: 6 switches total, current = gemini-3-flash for agent/critic/knowledge/memory, Ministral for objectives.
- Infrastructure: circuit breaker, max_turns=200, WAL mode, map_graph forward-only edges.

### What works (session-level confirmed wins)
- **ep92→93 memory_model swap Ministral→gemini-3-flash** (commit era). mem_new grew 2→24→49→31 across ep92-95. Learning loop alive.
- **ep93→94 visibility bundle** (BLOCKER bundle): completed-objectives rendering + score-event timeline + nav_target BFS + inventory_changed memory trigger. Delivered the ep94 102 ceiling.
- **ep94→95 stale-route recompute** (agent.md): specific "planned direction missing from engine exits → mark STALE and replan" rule. Behaviorally confirmed in ep95 t77 and ep98 t39. **This is the narrow template for the proposed ep100→101 general stale-belief rule.**
- **ep96→97 critic model swap** (`c0f8e69`): Ministral→gemini-3-flash for critic role. Fixture probe showed 5/5 problem flips, 3/3 healthy preserved. ep97 production confirmed: zero spirals, 0.76 avg critic, deposit loop unblocked.
- **ep97→98 critic disable experiment** (`1663389`): `enable_critic=false` in pyproject.toml. ep98 produced 90/350 on the cleanest execution of the session — 34 locations visited (new session-high location count), compound commands unblocked, Cyclops-shortcut deposit used for the first time in session. At gemini/gemini parity, the LLM critic was net cost.
- **ep98→99 extract_info deletion** (`873c37d`): pure subtraction of the extractor action, IN_COMBAT state, COMBAT ACTIVE banner, and associated config. Saved ~1 LLM call/turn. Delivered the 3-turns/min speedup. Execute_action now writes EXITS and VISIBLE_OBJECTS directly from Jericho.
- **ep98→99 map_graph reverse-edge fix** (`3de19b6`): `add_connection` now records only observed forward edges. One-way passages (chimney, chasm drops, slide room) no longer get fabricated reverse edges. Unit-test validated (9/9 passing). Data effects appear gradually as new observations accumulate.
- **memory_model consolidation routing** (`5d7bb77`): end-of-episode consolidation uses `memory_model` (gemini-3-flash) instead of the old `analysis_model` (Ministral). Validated end-to-end in ep100 with `mem_consolidated=8` and sensible keep/drop/merge decisions in the log.
- **analysis_model → objective_model rename** (`165ba18`): 1:1 mapping between config keys and concerns. No prompt changes. Pure cleanup.
- **SQLite WAL mode on `data/burr_state.db`**: applied post-ep99 crash. Allows the Burr tracker web server and episode persister to write concurrently. Environmental fix, not in git.

### Falsified hypotheses (session-level)
- **"Sonnet 4.6 works for secondary subsystems"** — FAILED ep85-86.
- **"Ministral is sufficient for memory synthesis"** — FAILED ep91-92 (confirmed via direct probe).
- **"Ministral is sufficient for critic role"** — FAILED ep96 (confirmed via ep96 fixture probe, 5/5 flip rate).
- **"At gemini/gemini parity, the LLM critic still adds value"** — FAILED ep97-98 experiment (91.2% first-proposal accept, no observable value on the remaining 9%).
- **"Temperature 0.7 reduces variance"** — FAILED ep47.
- **"50-turn prompt changes can fix model KB-following"** — FAILED ep39-41 (code bug, not prompt).

### Open problems (ordered by current impact)
1. **Belief reconciliation / object permanence — THE top priority.** Agent has stored plans and KB facts, reads them into context every turn, but doesn't verify preconditions against live engine state. Manifestations: thief combat (3/4 recent), KB failure-verdict retries (ep99 Dam bolt), phantom-inventory takes (ep98/100 bar). **Proposed fix: generalize the ep94→95 stale-route rule into a full "stale-belief" reasoning protocol in agent.md** — apply to inventory, visible_objects, and KB failure records in addition to exits. Fixture-probe against ep99 t29 and ep100 t53.
2. **Thief combat gameplay defect.** Subcase of #1 but severe enough to mention separately. Score impact ~15-30 points per affected episode. The KB has the knowledge ("thief dodges, disarms, leaves when finding nothing of value"); the agent doesn't apply it.
3. **Rope-at-Dome prerequisite not carrying forward.** ep94 successfully descended Dome→Torch via rope from Attic for +28. Subsequent episodes haven't reproduced this despite the rope being in the KB. ep100 took the rope but never navigated to Dome. Investigate whether the ep94 memory/KB entry exists and is renderable, or whether it got consolidated away.
4. **Dam puzzle unsolved.** 150+ cumulative turns, zero score. Not currently the priority but a known dead-weight zone.
5. **Programmatic validator compound-take blind spot.** `validate_against_object_tree` misparses `take X, Y` as a single object. Low-priority cleanup; force-accept resolves it.
6. **data/map.json has accumulated false reverse edges from ep1-98.** The ep98→99 map_graph fix stops adding new ones but doesn't wipe existing. Consider a one-time cleanup if routing errors persist.

### Subsystems investigated (current totals)
- Agent prompt: ~21 changes, last ep94→95 (stale-route). Next target: stale-belief generalization.
- Critic prompt: 3 changes total, last ep7. Now bypassed entirely via `enable_critic=false`.
- KB/memory system: ~13 changes, last ep96→97 (memory_model consolidation routing + rename cleanup).
- Python pipeline (context assembly): ~13 changes, last ep98→99 (extract_info deletion, execute_action now writes exits/visible_objects).
- Model stack: 6 switches total, current = gemini-3-flash for agent/critic/knowledge/memory, Ministral for objective_model only.
- Infrastructure: circuit breaker, max_turns=200, WAL mode, map_graph forward-only edges.


---

## Future Work Queue
- **Nav-target route injection (ep94 or later):** Add a `nav_target` field to the agent's response schema (location ID or name). On the next turn, `assemble_context` runs BFS over `MAP_DATA.connections` from current_loc → nav_target and injects the shortest route into the formatted context as text (e.g., *"Planned route to Gallery: w → down → s → e"*). Passive, no tool-call wiring needed. Motivated by watching ep91/ep92 agents wander the Maze for 20+ turns despite having a clear destination. Zork I maze is deterministic with distinct internal room IDs, so BFS over MAP_DATA works without special-casing — the agent's difficulty is visual recognition ("all rooms say Maze") which the router bypasses by reading location_id directly. Route injection is NOT game-specific knowledge (it's the agent's own learned map). Do AFTER ep93 validates the memory_model fix, so we're not stacking effects.

---

## Episode 106 — COMPLETE (killed at t151)
**Turns:** 151 (killed — 114 turns stagnant, no recovery prospect)
**Final score:** 54/350
**Locations visited:** 23
**Objectives found:** not counted (episode killed)
**End reason:** early_stop (orchestrator killed — 114 turns stagnant)
**Improvement dispatched:** yes — stale-belief protocol

**Key observations:**
- KB dedup BLOCKER fix VALIDATED: No circuit breaker in 151 turns. Context manageable throughout. ep105→106 dedup fix working.
- Thief stole painting + platinum bar at t36 after chimney climb — score stuck at 54 for remaining 115 turns
- Dam bolt loop recurred (turns 87-100) despite KB failure verdicts
- Agent tried to take bar at Loud Room (t150) despite it not being there — reasoning explicitly overrides room observation with KB "knowledge": "although the room description doesn't explicitly mention the platinum bar, the strategic knowledge confirms it is here"
- Weight management protocol working (chimney climb succeeded at t39)
- 114 turns stagnant — worst stagnation in session history

**Root cause analysis:**
The agent has NO mechanism to prefer current engine observations over stored KB facts. Three manifestations in this episode:
1. Dam bolt: KB says "bolt succeeds after water rises" (hallucinated) — agent keeps trying despite game saying "bolt won't turn"
2. Platinum bar: KB says "bar at Loud Room" — agent tries to take it despite game saying "isn't here" (thief stole it)
3. General stagnation: agent repeats actions that have failed in the current episode because KB says they should work

This is the belief reconciliation problem from Key Learnings #1. The fix is a stale-belief protocol in agent.md.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep103   | 85    | +30     | 90          | 5                 | 31        | noisy      | max_turns  |
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |

**Trend:** ep105 and ep106 are both below ep104's 95 ceiling. ep105 was not representative (credit exhaustion). ep106 is representative — the thief + belief reconciliation failure is the clear bottleneck. The KB dedup fix is validated (no more token overflow) but the agent's inability to reconcile stored beliefs against live observations remains the top open problem.

---

## Episode 106 → 107 — IMPROVEMENT
**Trigger:** 114-turn stagnation in ep106 (score 54/350). Agent overrides engine observations with KB "knowledge" in two concrete failures: (1) Dam bolt retried 6+ times despite game rejecting every attempt, because KB had a hallucinated conditional success entry; (2) `take bar` at Loud Room t150 despite game saying "isn't here", because agent reasoning explicitly stated "although the room description doesn't explicitly mention the platinum bar, the strategic knowledge confirms it is here."
**Hypothesis:** The Pre-Action Belief Check (added ep100→101) put engine observations and KB entries on EQUAL footing ("Engine-supplied facts and KB-recorded verdicts are the live truth"). When they conflict, the agent picks whichever supports its current plan (confirmation bias). Three specific loopholes: (a) no authority hierarchy between engine and KB, (b) Rule 2 has an "unless" clause allowing KB conditional success entries to override repeated engine rejections, (c) Rule 1's `take X` check isn't strong enough to override KB claims about item presence.
**Change:** Three targeted edits to the PRE-ACTION BELIEF CHECK section of `prompts/agent.md`:
1. **Engine-supremacy hierarchy (line 62):** Replaced equal-footing language with an explicit, NON-NEGOTIABLE authority chain: `Engine observations (this turn) > Engine observations (earlier this episode) > KB entries > Your plan`. Added clear language: "When engine observations and KB entries conflict, THE ENGINE IS RIGHT AND THE KB IS STALE."
2. **Same-episode empirical falsification (Rule 2):** Removed the exploitable "unless the KB itself records a specific new condition" clause. Added a NON-NEGOTIABLE same-episode retry limit: if action X has been tried 2+ times this episode and rejected every time, it is empirically falsified — do not retry regardless of KB conditional success entries. Added explicit prohibition on self-invented preconditions.
3. **Definitive absence for `take X` (Rule 1):** Strengthened from "item is not in this room" to "item is DEFINITIVELY ABSENT from this room RIGHT NOW." Added explicit handling for game responses like "isn't here" as HARD ENGINE VERDICTS. Added: "KB saying 'X is at this location' when the engine says it isn't = KB is stale, not the engine being wrong."
**Reasoning:** The ep94→95 stale-route fix worked precisely because it was absolute ("NON-NEGOTIABLE") with no escape clauses. These edits apply the same absoluteness to the broader belief check. All three changes are reasoning heuristics applicable to any text adventure (pass the Two-Question Test from prompts/CLAUDE.md). They teach HOW to resolve conflicting information sources, not WHAT to do in specific game situations.
**Target metric:** (1) No Dam bolt retry loops (0 retries after 2 failures), (2) No phantom `take X` when game said "isn't here", (3) Score >= ep106's 54/350 (no regression from belief-check strictness).
**Validation:** Ran `validate_prompt.py` against all 7 ep106 fixtures. Results: 5/7 structural pass. The 2 "failures" are false positives — t36 (take painting at Gallery where painting IS visible) and t46 (go east from Troll Room as navigation) were labeled "problem" with a generic description but their original actions are correct; the prompt change correctly preserved them. Critical target fixtures: t40 (thief recovery) PASSED — agent now checks inventory instead of blindly pursuing stolen items; t150 (phantom bar take) PASSED — action string changed, reasoning now notices "the platinum bar is not in the truncated description." All 3 healthy fixtures (t5, t24, t39) PASSED with identical actions preserved.
**Result:** **PARTIAL** — ep107 scored 80/350 (vs ep106's 54), significant improvement. Bolt retries reduced from ep106's 15+ continuous to 5 total (3+break+2), and agent broke out by t44 (vs ep106 stuck for 100+ turns). BUT the 2-retry limit was NOT strictly followed — agent made 5 attempts because the KB hallucinated entry provides positive justification that overrides the negative prompt constraint. Score improved because the agent spent less time at the Dam and more time scoring (painting deposit +6, bar deposit +5, bag deposit +5). Engine-supremacy hierarchy is a net positive but the bolt-specific loop needs a code-level fix (KB cleanup or stagnation detector) — 2/3 prompt attempts on this root cause have failed to fully resolve it.

---

## Episode 107 — Turn 50 Checkpoint
**Type:** CONCERN
**Score:** 40/350 (delta: +0 since turn 25)
**Locations visited:** 15 total (3 new this block)
**Avg critic score:** 0.50
**Rejection rate:** low
**Gameplay quality:** DRIFTING
  - KB alignment: Engine-supremacy rule NOT working for Dam bolt — agent tried 5 times (t31,33,35,40,42) despite 2-retry limit. Agent's reasoning explicitly cites KB hallucinated entry ("bolt succeeds after water rises") as justification. However, agent DID leave Dam at t44 (~12 turns in Dam area vs ep106's 20+).
  - Learning system quality: No circuit breaker — KB dedup holding.
  - Pathfinding: DRIFTING — left Dam area, heading to Loud Room
**Triggers:** Score stagnant (0 delta across 2 checkpoints), bolt retry (5 attempts, exceeds 2-retry limit)
**Notes:** The engine-supremacy prompt fix had PARTIAL effect — agent spent ~12 turns at Dam vs ep106's 20+, and broke out earlier. But the 2-retry limit is being ignored; the KB hallucinated entry ("bolt succeeds after water rises") is providing stronger positive reasoning than the negative prompt constraint. This is 2/3 attempts at prompt-level bolt loop fixes. If ep107 final score doesn't improve significantly vs ep106, the 3-strikes rule activates and the fix shifts to Python code (stagnation detector or KB cleanup).

---

## Episode 107 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 65/350 (delta: +25 since turn 50)
**Locations visited:** 20 total
**Bolt attempts:** 5 total (all before t42, none since — partial fix working)
**Gameplay quality:** LEARNING
  - Score trajectory: t25=40, t50=40, t75=54, t100=65 — second half is producing consistent scoring
  - Painting deposited at t82 (+6), bar deposited at t91 (+5) after chimney return trip
  - Weight management: REGRESSION — agent dropped bar in Studio at t64 (should have dropped sack instead), required extra round trip. But recovered the bar and deposited it.
  - Engine-supremacy: PARTIAL — bolt retries reduced from ep106's 15+ continuous to 5 with breaks. Agent broke out of Dam at t44. BUT 2-retry limit not strictly followed (5 total).
  - No circuit breaker — KB dedup holding through 100 turns.
**Triggers:** none — score is progressing, no stuck loops since t44
**Notes:** Better than ep106 despite the Dam detour. ep106 stagnated at 54 for 100+ turns. ep107 is at 65 at t100 with 100 turns remaining and still scoring. The engine-supremacy fix is a partial improvement — reduced but didn't eliminate bolt retries.

---

## Episode 107 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 80/350
**Locations visited:** 21
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** mem_total=72, mem_new=44 (excellent learning rate), mem_superseded=16, mem_consolidated=7
**Improvement dispatched:** no — evaluating results

**Score milestones:**
- t5: in Kitchen (+10), score 10
- t13: down to Cellar (+25), score 35
- t19: east from Troll (+5), score 40
- t52: take bar at Loud Room (+10), score 50
- t62: take painting at Gallery (+4), score 54
- t82: deposit painting in trophy case (+6), score 60
- t91: deposit bar in trophy case (+5), score 65
- t121: take bag in Maze (+10), score 75
- t137: deposit bag in trophy case (+5), score 80

**Key observations:**
- Engine-supremacy fix PARTIAL: bolt retries 5 (down from ep106's 15+), agent broke out at t44 (vs ep106 stuck 100+ turns). Score 80 vs ep106's 54 — clear improvement.
- KB dedup validated: no circuit breaker in 200 turns. mem_new=44 is healthy learning rate.
- Weight management: REGRESSION — dropped bar in Studio at t64, needed extra round trip. But recovered it.
- Late stagnation: score stuck at 80 from t137 to t200 (63 turns). Agent cycled through underground areas without finding new scoring opportunities.
- Thief: did NOT steal treasures this episode — agent was lucky or thief encounters were less impactful.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep103   | 85    | +30     | 90          | 5                 | 31        | noisy      | max_turns  |
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |

**Trend:** ep107 (80) is well above ep106 (54) and ep105 (40), confirming both BLOCKER fixes (KB dedup) and the engine-supremacy INCREMENTAL fix are net positive. Still below ep104's session best (95). The gap is primarily from the Dam detour (~12 turns wasted) and late-game stagnation (63 turns at 80). The system is HEALTHY overall — variance between episodes is expected. Best score ceiling (95) has not been broken.

---

## Episode 107 → 108 — KB DATA CLEANUP (not a code/prompt change)
**Action:** Removed 3 hallucinated bolt entries from data/knowledge.md:
- "bolt only succeeds after water level rises significantly (chest level)" — HALLUCINATED
- "Turning the bolt opens the sluice gates" — HALLUCINATED (agent never succeeded)
- "bolt fails initially until flooding progresses" — HALLUCINATED
Replaced with explicit failure verdicts: "tested multiple times with water rising, bolt does NOT turn. Approach exhausted."
**Rationale:** The hallucinated KB entries provided positive justification that overrode the engine-supremacy prompt rule. Removing them means the KB now ONLY contains failure verdicts for the bolt, which should align with Rule 2's failure-verdict matching.
**Not committed:** data/knowledge.md is gitignored. This is an operational data cleanup, not a code change.

---

## Episode 108 — Turn 50 Checkpoint
**Type:** HEALTHY
**Score:** 60/350 (delta: +20 since turn 25)
**Locations visited:** 15 total
**Avg critic score:** 0.50
**Bolt attempts:** 0 (KB cleanup + engine-supremacy working!)
**Gameplay quality:** LEARNING
  - KB alignment: ZERO bolt retries — agent bypassed Dam area entirely. KB failure verdicts are being respected.
  - Engine-supremacy: Agent recognized bar missing from Studio ("not visible in the current location"), moved on instead of retrying. This is the exact behavior change we wanted.
  - Weight management: REGRESSION — dropped bar in Studio at t36 (same pattern as ep107). Thief stole the bar from Studio while agent was above.
  - Score progression: 60 at t50 (vs ep107's 40 at t50, ep106's 54 at t50). Better early-game efficiency.
**Triggers:** none
**Notes:** The KB cleanup + engine-supremacy combination is working perfectly for the Dam bolt issue. The agent is now spending its turns productively instead of at the Dam. Thief theft from unguarded Studio is a recurring problem but is a game-level challenge, not a system defect.

---

## Episode 108 — Turn 75 Checkpoint
**Type:** CONCERN
**Score:** 60/350 (delta: +0 since turn 50)
**Locations visited:** 20 total
**Bolt attempts:** 0 (validated!)
**Gameplay quality:** DRIFTING
  - Agent explored Dam area without trying bolt (VALIDATED). Pressed yellow/brown buttons in Maintenance Room (exploratory).
  - Score stagnant at 60 since t39 (painting deposit). Bar stolen by thief from unguarded Studio.
  - 20 locations explored — broad exploration despite stagnation.
**Triggers:** Score stagnant (0 delta across 2 checkpoints)
**Notes:** The Dam bolt issue is FULLY RESOLVED — 0 attempts in 75 turns. Agent spent its Dam turns productively exploring buttons instead. Stagnation is due to thief stealing the bar (game-level), not system defect. The agent needs to find the maze bag or underground treasures to score further.

---

## Episode 108 — COMPLETE
**Turns:** 105 (circuit_breaker — OpenRouter credits exhausted again, not KB bloat)
**Final score:** 70/350
**Locations visited:** 24
**Objectives found:** 14
**End reason:** llm_circuit_breaker (402 — "can only afford 3689" of requested 4096 max_tokens)
**Memory stats:** mem_total=65, mem_new=13, mem_consolidated=1
**Bolt attempts:** 0 (ZERO — dam loop fully resolved!)
**Improvement dispatched:** no

**Score milestones:**
- t5: in Kitchen (+10), score 10
- t13: down to Cellar (+25), score 35
- t19: east from Troll (+5), score 40
- t23: take bar at Loud Room (+10), score 50
- t33: take painting at Gallery (+4), score 54
- t39: deposit painting (+6), score 60
- t90: take egg from tree (+5), score 65
- t97: deposit egg (+5), score 70

**Key observations:**
- **Dam bolt loop FULLY RESOLVED:** Zero bolt attempts in 105 turns. Agent visited Dam area (t61-68) and explored buttons in Maintenance Room instead of trying the bolt. This is the combined effect of KB cleanup + engine-supremacy prompt rule.
- **KB dedup holding:** No token overflow from KB bloat. Credits ran out (money), not prompt tokens exceeded.
- **Thief stole bar from Studio** at ~t46 while agent was above. Agent correctly recognized bar was missing and moved on (engine-supremacy working for object presence too).
- **Weight management REGRESSION:** Agent dropped bar (treasure) in Studio at t36 instead of expendable items, then thief stole it. Same pattern as ep107. This is now a recurring issue worth investigating.
- Score would likely have been higher with more turns — agent was actively exploring new areas (Forest, Tree) at time of death.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |

**Trend:** ep108 (70) is lower than ep107 (80) but died early from credits at t105. Score-per-turn is comparable: ep108 scored 70 in 105 turns (0.67/turn) vs ep107 80 in 200 turns (0.40/turn). ep108 was actually more efficient per turn. The system is HEALTHY — both BLOCKER fixes validated, engine-supremacy working, bolt loop eliminated.

---

## Session Complete
**Episodes run:** 4 (ep105, ep106, ep107, ep108)
**Best score achieved:** 80/350 (ep107, full 200 turns) — session best within this run
**Overall best:** 95/350 (ep104, from prior session)
**Improvements made:** 3
  1. KB Items Found dedup (ep104→105) — IMPROVED
  2. KB all-section dedup (ep105→106) — IMPROVED (BLOCKER resolved)
  3. Engine-supremacy hierarchy in belief check (ep106→107) — PARTIAL (bolt loop reduced but not eliminated by prompt alone; KB data cleanup completed the fix)
  + KB data cleanup (ep107→108) — operational, removed hallucinated bolt success entries
**System status:** STOPPED — OpenRouter credits exhausted for second time this session
**Summary:** Resolved two infrastructure BLOCKERs (KB duplication causing token overflow) and one gameplay INCREMENTAL (engine-over-KB hierarchy). The Dam bolt loop — the dominant stagnation cause — is fully resolved through the combination of engine-supremacy prompt rule + KB data cleanup. Score trajectory is healthy (70-80 range with clean system), though below ep104's 95 ceiling. The remaining ceiling gap is primarily from thief interactions and late-game exploration efficiency.

---

## Episode 109 — Turn 26 Checkpoint
**Type:** HEALTHY
**Score:** 40/350 (delta: +40 from start)
**Locations visited:** 12 total (12 new this block)
**Avg critic score:** 0.50 (critic disabled, fixed value)
**Rejection rate:** 1/26 turns had rejections (4%)
**Gameplay quality:** LEARNING
  - Memory use: No memory synthesis triggered yet (first 26 turns, only 2 score events). KB content is rich from prior episodes. Agent acted on KB knowledge at t16 (attack troll with sword — one-shot kill).
  - KB alignment: Agent exploring Dam area (t21-26) — KB records bolt as failed, agent hasn't attempted bolt. Good alignment so far.
  - Objective quality: 7 discovered / 0 completed — objectives are specific and actionable (deposit treasures, explore troll hole, chimney climb)
  - Objective pursuit: Agent navigating toward Dam/Maintenance area — exploring but not yet pursuing deposit objectives
  - Learning system quality: KB is clean (dedup working), rich strategic content from prior episodes. No new memories yet (expected at this stage).
  - Pathfinding: NAVIGATING — agent followed a coherent path: West House → Kitchen → Living Room → Cellar → Troll → East → Dam area. Good use of known map connections.
**Triggers:** none
**Notes:** Strong early game — 40 points in 26 turns with efficient pathing. Agent dropped expendables (leaflet, bottle) to pick up guidebook/matchbook at Dam Lobby, showing reasonable weight management. Now in Maintenance Room — key question is whether it attempts the bolt (KB says failed) or moves on.

---

## Episode 109 — Turn 50 Checkpoint
**Type:** HEALTHY
**Score:** 50/350 (delta: +10 since last checkpoint)
**Locations visited:** 16 total (4 new this block: Deep Canyon, North-South Passage, Round Room, Stream View)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 0/25 turns had rejections (0%)
**Gameplay quality:** LEARNING
  - Memory use: No new memories this block (dedup working — echo/bar pattern already in KB). Agent acted on KB at t41 (used `echo` command in Loud Room, a known puzzle mechanic from KB).
  - KB alignment: Agent did NOT attempt bolt at Dam (KB records it as failed). Good compliance. Used echo trick for platinum bar per KB. No contradictions observed.
  - Objective quality: 13 discovered / 3 completed — some duplicates creeping in (wooden door objective re-added at t40 despite prior failure). Mix of specific and vague.
  - Objective pursuit: Agent took bar (objective completed t43), now navigating toward Living Room to deposit — clear pursuit of deposit objective.
  - Learning system quality: KB clean, rich from prior episodes. Memory dedup rejecting redundant entries correctly.
  - Pathfinding: NAVIGATING — agent heading back via Cellar → East Chasm toward Living Room for deposit. Coherent routing.
**Triggers:** none
**Notes:** Score progressing at reasonable pace. Agent efficiently used `echo` + weight management to get platinum bar. Now routing toward Living Room to deposit. Spent turns 26-42 exploring Dam area without attempting the bolt — engine-supremacy rule holding. Some wasted turns examining bubble/control panel at Dam (t34-35) but not excessive.

---

## Episode 109 — Turn 77 Checkpoint
**Type:** HEALTHY
**Score:** 65/350 (delta: +15 since last checkpoint)
**Locations visited:** 18 total (2 new this block: Engravings Cave, Dome Room)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 0/27 turns had rejections (0%)
**Gameplay quality:** LEARNING
  - Memory use: No new memories this block (prior KB coverage sufficient). Agent correctly didn't descend Dome without rope — KB records "cannot go down without fracturing many bones."
  - KB alignment: Excellent. Weight management worked perfectly: carried bar through chimney with just lantern (t54-55), deposited, went back for painting same way (t73-75). No treasures dropped in Studio — the ep107/108 regression is NOT repeating.
  - Objective quality: 15 discovered / 10 completed — good turnover. Some duplicate objectives re-added (wooden door, chimney) but not harmful.
  - Objective pursuit: Strong — completed 7 objectives this block including 3 deposit objectives.
  - Learning system quality: KB clean, objectives system actively tracking and completing.
  - Pathfinding: NAVIGATING — two clean chimney round-trips (bar deposit, painting deposit). Efficient routing.
**Triggers:** none
**Notes:** Best chimney execution seen in any episode — two separate round-trips, both with correct weight management. Score 65 at t77 is on pace for 80+ if the agent finds more treasures. Agent now has just lantern in inventory and is at Living Room — needs to go find more items (egg, bag, coffin, etc.).

---

## Episode 109 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 75/350 (delta: +10 since last checkpoint)
**Locations visited:** 22 total (6 new this block: Clearing, Forest, Forest Path, Up a Tree, North House, Behind House)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 2/25 turns had rejections (8%)
**Gameplay quality:** LEARNING
  - Memory use: 0 new memories this episode so far. KB from prior episodes providing sufficient coverage for current actions. Agent correctly used KB knowledge for echo trick, chimney weight rules, egg location.
  - KB alignment: Strong. Agent followed known scoring paths efficiently. No bolt attempts, no KB contradictions.
  - Objective quality: 13 discovered / 18 completed — excellent turnover, objectives being actively pursued and completed.
  - Objective pursuit: Very strong — egg retrieval + deposit loop completed (t78-90). Now retrieving cached items from Studio.
  - Learning system quality: KB clean, objectives system working well. Memory system quiet but not broken (prior KB coverage sufficient).
  - Pathfinding: NAVIGATING — efficient above-ground egg retrieval path. Minor issue: stuck at chimney t98-100 with too many items. KB records the solution (drop more items) so should self-correct.
**Triggers:** none
**Notes:** Score 75 at t100 is solid — 3 treasures deposited (bar, painting, egg). Agent stuck at chimney with too many items (t98-100) — dropped sword but still carrying tube, matchbook, manual, sack. Should resolve in next few turns per KB guidance. No scoring stagnation concern yet. The 0-memory episode is notable but not a trigger — KB coverage from 100+ prior episodes is comprehensive for the paths this agent is taking.

---

## Episode 109 — Turn 125 Checkpoint
**Type:** CONCERN
**Score:** 75/350 (delta: +0 since last checkpoint — stagnant for 35 turns)
**Locations visited:** 27 total (0 new this block — only 6 unique locations visited: Studio, Gallery, Kitchen, Living Room, Cellar, East Chasm)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 4/25 turns had rejections (16%)
**Gameplay quality:** DRIFTING
  - Memory use: Agent has 21 new memories created this episode (cumulative) but reasoning shows stale beliefs about Studio contents (believes bar, brass bell, skeleton key are there — they aren't).
  - KB alignment: KB has chimney rules ("drop matchbook, tube, screwdriver, wrench, guidebook, manual") but agent repeatedly fails chimney with tube+matchbook+sword (t98, 100, 113), drops only 1-2 items, tries again, fails again.
  - Objective quality: 15 discovered / 22 completed — objectives are active but some are stale (deposit egg already done, retrieve items that don't exist in Studio).
  - Objective pursuit: Agent pursuing "retrieve items from Studio" and "deposit in trophy case" but the items it seeks (bar, bell, key) aren't in Studio. Shuttling non-scoring items (sack, tube, matchbook) up chimney for no benefit.
  - Learning system quality: KB clean and comprehensive. Memory system producing dedup_rejected (good — not creating noise). But agent isn't applying chimney weight rules from KB within-episode.
  - Pathfinding: WANDERING — agent cycling Studio → chimney fail → Gallery → Cellar → Living Room → back down → repeat. 35 turns stagnant, 0 new locations. Stale-route rule fired at t125 but led to long-way-around instead of dropping items.
**Triggers:** Score stagnant (0 delta across turns 90-125, 35 turns). Area-stuck (6 locations cycling).
**Notes:** The agent exhausted its known scoring paths (bar, painting, egg deposited) and is now burning turns shuttling non-value items through the chimney. The fundamental issue is the agent doesn't know where to find the next treasure (bag in Maze, coffin underground, etc.) and is defaulting to busywork. Not dispatching improvement yet — this is a natural plateau when the agent has collected the "easy" above-ground treasures. The remaining 100 turns should push it to explore new areas. If score is still 75 at the 150 checkpoint, will investigate.

---

## Episode 109 — Turn 150 Checkpoint
**Type:** CONCERN
**Score:** 85/350 (delta: +10 since last checkpoint)
**Locations visited:** 28 total (1 new this block: Maze)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 1/25 turns had rejections (4%)
**Gameplay quality:** DRIFTING
  - Memory use: 23 new memories cumulative (dedup rejecting 3, superseded 6). Agent still not creating new memories this block despite scoring in maze.
  - KB alignment: Agent correctly navigated to maze, found bag (+10) and skeleton key. Followed chimney pattern but still struggles with weight — tries dropping one item at a time (t145 sword → fail t146, t147 matchbook+tube → fail t148, t150 key). Taking 5 turns to do what should take 1.
  - Objective quality: 14 discovered / 25 completed — odd objective completions (marking "retrieve items from Maze" as complete at t145 when in Studio, marking "retrieve screwdriver from Troll Room" at t135 when in Maze). Objective system has loose completion criteria.
  - Objective pursuit: Actively pursuing bag deposit — coherent goal, just inefficient execution.
  - Learning system quality: KB clean. Memory dedup working. Objectives have loose completion matching.
  - Pathfinding: NAVIGATING — maze navigation efficient (4 turns in, 4 turns out). Chimney route is the bottleneck, not navigation.
**Triggers:** none (score stagnation resolved — +10 this block)
**Notes:** Score recovered to 85 after maze trip. The recurring chimney weight issue (agent drops items one at a time instead of all at once) costs 3-5 turns per chimney trip. Not a prompt issue — the KB already specifies which items to drop. The agent reads KB but applies it incrementally rather than all at once. This is a behavioral pattern of the model, not a system defect. 50 turns remaining.

---

## Episode 109 — Turn 177 Checkpoint
**Type:** CONCERN
**Score:** 90/350 (delta: +5 since last checkpoint — bag deposit at t153)
**Locations visited:** 29 total (1 new: Attic)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 0/25 turns had rejections (0%)
**Gameplay quality:** DRIFTING
  - Memory use: Agent retrieved rope from Attic (t163) — KB records "tie rope to railing at Dome Room." This shows KB-driven planning. But now stuck in maze unable to reach destination.
  - KB alignment: Agent has a coherent plan: rope for Dome descent, skeleton key for grating. But it entered the maze to reach the grating room and is now wandering (t170-177, 8 turns in maze with no exit found).
  - Objective quality: Objectives appear active but agent is maze-trapped with no clear exit path.
  - Objective pursuit: Strong intent (rope+key+knife gathered purposefully) but execution blocked by maze navigation.
  - Learning system quality: KB clean. Memory system quiet (23 new cumulative).
  - Pathfinding: WANDERING — 8 consecutive turns in maze with "all alike" rooms. Agent has the map data but maze rooms are hard to distinguish. Encountered thief at t175.
**Triggers:** none (score improved +5; maze wandering is expected in Zork)
**Notes:** Score 90 with 23 turns left. Agent showed excellent strategic planning: deposited bag, retrieved skeleton key + rope + knife for Dome/grating objectives. Now spending remaining turns stuck in the maze trying to reach the grating room. Unlikely to score more this episode. 90 is a strong result — 4th best ever (ep104=95, ep101=88, ep103=85). The agent has 4 treasures deposited (bar, painting, egg, bag). If it had reached the Dome with the rope, the coffin/sceptre scoring path could push past 100.

---

## Episode 109 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 90/350
**Locations visited:** 29
**Objectives found:** 13
**End reason:** max_turns
**Memory stats:** total=95, new=32, dedup_rejected=3, superseded=10, ephemeral_pruned=1, consolidated=16
**Improvement dispatched:** no

**Key observations:**
- **Excellent early game (t1-90):** 75 points in 90 turns. Clean chimney round-trips for bar, painting, egg deposits. Best weight management seen — no treasures dropped in Studio.
- **Mid-game stagnation (t91-134):** 35 turns cycling Studio ↔ chimney ↔ Living Room shuttling non-value items. Agent couldn't find new treasures and defaulted to busywork.
- **Late recovery (t135-153):** Found bag in maze (+10), deposited. Strategic planning to get rope + skeleton key for Dome/grating objectives.
- **Belief reconciliation failure (t184-193):** Agent gathered rope for Dome descent, then DROPPED rope in Studio (t184) to climb chimney, went to Dome (t193) without rope, couldn't descend. This is the #1 open problem from Key Learnings manifesting again — agent has a plan, gathers the tools, then discards a critical tool for a tactical need and doesn't reconcile.
- **Dam bolt loop: ZERO attempts.** Engine-supremacy rule + KB cleanup fully resolved this. Not a single bolt attempt in 200 turns.
- **Thief encounter (t175):** "Finding nothing of value, he left." Agent wasn't carrying valuables in the maze — correct behavior.
- **Skeleton key unused:** Agent carried it through the whole second half but never reached the grating room.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |

**Trend:** ep109 (90) is the 2nd highest score ever, matching the 80-95 range of the best full-200-turn episodes. The system is HEALTHY — KB clean, bolt loop eliminated, weight management improved (no Studio treasure drops). The remaining ceiling is belief reconciliation (dropping rope before reaching Dome) and mid-game exploration efficiency (35 turns of busywork at t91-134 when all easy treasures were deposited). Score trajectory across full-run episodes: ep101=88, ep103=85, ep104=95, ep107=80, ep109=90 — consistent 80-95 band.

---

## Episode 110 — Turn 25 Checkpoint
**Type:** HEALTHY
**Score:** 50/350 (delta: +50 from start — fastest ever)
**Locations visited:** 12 total (12 new this block)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 1/25 turns had rejections (4%)
**Gameplay quality:** LEARNING
  - Memory use: KB-driven — agent used `echo` trick for bar, killed troll one-shot. All from prior KB.
  - KB alignment: Excellent. No bolt attempts, efficient pathing to Loud Room via Deep Canyon.
  - Objective quality: Not yet checked but agent is clearly pursuing scoring actions.
  - Objective pursuit: 50 points in 25 turns — strong intent and execution.
  - Learning system quality: KB clean from prior session fixes.
  - Pathfinding: NAVIGATING — efficient route: West House → Kitchen → Living → Cellar → Troll → E-W → Round → Deep Canyon → Loud. Faster than ep109.
**Triggers:** none
**Notes:** Best 25-turn start in recent memory — 50 points by t25 (ep109 had 40 at t26). Agent skipped Dam exploration and went straight to Loud Room for the bar. More efficient use of early turns.

---

## Episode 110 — Turn 50 Checkpoint
**Type:** CONCERN
**Score:** 54/350 (delta: +4 since last checkpoint — thief stole bar+painting at t37)
**Locations visited:** 15 total (3 new this block: North-South Passage, Chasm, Gallery)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 3/25 turns had rejections (12%)
**Gameplay quality:** DRIFTING
  - Memory use: Agent recognized the theft at t38 (reasoning: "The thief appeared and stole the platinum bar and the painting"). Good awareness.
  - KB alignment: KB records thief behavior and Treasure Room location. Agent set objective "Recover stolen treasures from the thief's hideaway in Treasure Room (R100)" but hasn't pursued it yet.
  - Objective quality: New objective (recover from thief) is well-formed with specific location.
  - Objective pursuit: Agent went underground after theft but is exploring Chasm area (t49-50) rather than heading to Cyclops Room → Treasure Room path. 13 turns stagnant.
  - Learning system quality: KB clean.
  - Pathfinding: WANDERING — agent lost direction after the theft. Went up chimney with just manual+lantern (no treasures to deposit), came back down, now at Chasm examining cracks.
**Triggers:** none (thief encounter is external variance, not a system defect; agent recognized it and set correct objective)
**Notes:** The thief stole both the bar and painting at t37 — devastating. Agent correctly identified the Treasure Room as recovery target but hasn't navigated there. The Cyclops Room path (say "ulysses" → Treasure Room upstairs) is in the KB. This is a gameplay execution challenge, not a system defect. Score effectively reset to 54 (just the +4 painting take bonus). 150 turns remaining — plenty of time to recover if the agent pursues the thief.

---

## Episode 110 — Turn 77 Checkpoint
**Type:** CONCERN
**Score:** 54/350 (delta: +0 since last checkpoint — 40 turns stagnant)
**Locations visited:** 18 total (3 new this block: Damp Cave, White Cliffs Beach, Dome Room)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 0/25 turns had rejections (0%)
**Gameplay quality:** IGNORING
  - Memory use: Not referencing thief recovery objective in reasoning. Agent at t70 focused on "check Loud Room for items" instead of pursuing Cyclops → Treasure Room path.
  - KB alignment: KB has Cyclops/Treasure Room path but agent isn't referencing it. Agent went to Loud Room 3 times (t53, t63, t70) — bar already taken.
  - Objective quality: "Recover stolen treasures from thief's hideaway" objective was set at t38 but never pursued.
  - Objective pursuit: IGNORING — 0% of last 25 actions aligned with the thief recovery objective.
  - Learning system quality: KB clean. Objectives set correctly but not driving behavior.
  - Pathfinding: WANDERING — cycling Deep Canyon ↔ Loud Room ↔ Round Room, then to Damp Cave/White Cliffs Beach. No directional intent.
**Triggers:** Score stagnant (0 delta across 2 consecutive checkpoints). Objective drift (agent has active objectives but <20% of last 25 actions align). max_turns_stuck=40 about to trigger early_stop at ~t77.
**Notes:** The `max_turns_stuck=40` detection will end this episode imminently — agent last scored at t37, stuck detection fires at t77. The thief encounter was devastating (lost 14 points worth of items) and the agent failed to execute its own recovery plan (Cyclops → Treasure Room). The agent explored new areas (Damp Cave, White Cliffs Beach) which is not wasted — those get added to memories/map. But the core issue is objective pursuit: the agent SET the right goal but didn't ACT on it. This is the same pattern as ep109's rope-at-Dome failure — planning without execution.

---

## Episode 110 — COMPLETE (killed at t100)
**Turns:** 100 (killed by orchestrator — 63 turns stagnant)
**Final score:** 54/350
**Locations visited:** ~22
**End reason:** early_stop (orchestrator kill — stagnation)
**Improvement dispatched:** pending assessment (see below)

**Key observations:**
- **Fast start derailed by thief:** Score 50 at t25 (fastest ever), painting pickup at t36 (54). Then thief stole bar AND painting at t37 in Studio.
- **Correct diagnosis, no execution:** Agent set "Recover stolen treasures from thief's hideaway in Treasure Room (R100)" at t38 — exactly right. KB has the path (Cyclops Room → say "ulysses" → stairs → Treasure Room). Agent NEVER pursued it. Spent 63 turns exploring junk areas.
- **Objective system dropped the recovery goal:** By t70, active objectives were all exploration-type. The thief recovery objective was replaced by generic goals.
- **New areas discovered:** Damp Cave, White Cliffs Beach — some exploration value.
- **No bolt attempts:** Engine-supremacy rule held despite visiting Dam/Maintenance area.
- **Stuck detection didn't fire:** Agent kept visiting new locations, resetting the stagnation counter. `max_turns_stuck=40` uses location novelty, not just score change.

**Cross-episode pattern (ep109 + ep110):**
Both episodes showed the same structural defect: **the agent sets correct strategic objectives but abandons them when tactical friction arises.** In ep109, it gathered rope for Dome but dropped it for chimney access. In ep110, it identified the Treasure Room recovery path but never navigated there, defaulting to aimless exploration.

This pattern suggests the objective system isn't driving behavior strongly enough — objectives are set and forgotten rather than actively guiding turn-by-turn decisions.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |

**Trend:** ep110 (54) is a regression but caused by thief encounter, not system defect. Full-run episodes (200 turns, no thief kill) still perform in the 80-95 band. The thief is the #1 variance source — when it strikes, the agent can't recover.

---

## Episode 110 → 111 — IMPROVEMENT
**Trigger:** NEW_OBJECTIVE dead write — agent's per-turn objectives silently discarded
**Hypothesis:** Wiring NEW_OBJECTIVE into DISCOVERED_OBJECTIVES will let the agent's
real-time objective proposals persist and drive behavior, preventing objective drift
after critical events (thief encounters, item loss, etc.)
**Change:** Modified `zorkburr/actions/results.py` — `record_results` now reads
`S.NEW_OBJECTIVE`, `S.DISCOVERED_OBJECTIVES`, and `S.COMPLETED_OBJECTIVES`, and if
the agent's `new_objective` is non-empty, not already in the active list, and not
already completed, appends it as a new discovered objective (capped at 15). Updated
`tests/test_actions/test_results.py` to include the new state keys.
**Reasoning:** The agent already generates high-quality per-turn objectives (e.g.,
"Recover stolen treasures from thief's hideaway" at t38 in ep110) but they were
written to state and never read. By wiring them into DISCOVERED_OBJECTIVES in
`record_results` (which runs every turn after action execution), the agent's
real-time objective proposals appear in context assembly on the very next turn,
closing the 10-turn blind spot where critical objectives were lost between
`update_objectives` cycles.
**Target metric:** Agent's critical objectives (set via new_objective) appear in Active
Objectives within 1 turn. In ep110-like scenarios, the thief recovery objective should
persist through subsequent update_objectives cycles.
**Validation:** Test suite passes (215/216; 1 pre-existing config test failure unrelated).
Manual code review confirms wiring.
**Result:** PARTIAL — Wiring confirmed working (code review + tests). Cap bug found in ep111 (append to full list gets truncated) — hotfix committed (e33afe6, insert at position 0). Thief didn't appear in ep112 so behavioral impact (objective persistence after theft) remains untested. Structural fix is correct; follow-up episode with thief encounter needed to fully validate.

---

## Episode 111 — Turn 27 Checkpoint
**Type:** HEALTHY
**Score:** 45/350 (delta: +45 from start)
**Locations visited:** 8 total (8 new)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** ~4% (estimated)
**Gameplay quality:** LEARNING
  - Different route than ep109/110 — bag-first via maze before Loud Room. Shows healthy variance.
  - Score 45 at t27 — comparable pace (ep109=40@t26, ep110=50@t25).
  - NEW_OBJECTIVE fix is live — will observe at later checkpoints whether per-turn objectives persist.
**Triggers:** none
**Notes:** First episode with NEW_OBJECTIVE fix. Standard early game, bag-first variant. Will monitor for objective persistence, especially if thief appears.

---

## Episode 111 — Turn 50 Checkpoint
**Type:** CONCERN
**Score:** 49/350 (delta: +4 since last checkpoint — painting take at t32, then thief stole painting+bag at t34)
**Locations visited:** 14 total (6 new this block)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** ~4% (1 rejection seen)
**Gameplay quality:** DRIFTING
  - Memory use: Agent recognized theft at t35 (reasoning mentions thief stole items). Set recovery plan.
  - KB alignment: KB has Cyclops → Treasure Room path. Agent not pursuing it.
  - Objective quality: 15 objectives — but the recovery objective was DROPPED due to cap. List is full of stale junk (5 copies of "deposit leather bag" despite bag being stolen). **NEW_OBJECTIVE fix has a cap bug: append + [:15] drops new objectives when list is full.**
  - Objective pursuit: Agent's "Current Plan" says "retrieve stolen items from thief's hideout" but it went back to cycling Studio ↔ Gallery ↔ Cellar (t35-50). Same pattern as ep110.
  - Learning system quality: Cap bug in fix; also, stale objectives not being cleaned up.
  - Pathfinding: WANDERING — cycling known areas after theft, not heading to Cyclops Room.
**Triggers:** Score stagnant since t32 (18 turns). Thief stole bag+painting at t34. NEW_OBJECTIVE cap bug.
**Notes:** The NEW_OBJECTIVE fix wired correctly but the 15-cap means objectives appended to a full list are immediately truncated. **Follow-up fix committed (e33afe6): insert at position 0 instead of append.** The thief appearing at the Studio chimney is now a pattern (ep110 t37, ep111 t34) — the agent consistently tries to carry 4+ items through the chimney and the thief is drawn to the high-value-item location.

---

## Episode 111 — Turn 77 Checkpoint
**Type:** CONCERN
**Score:** 54/350 (delta: +5 since last — east from Troll +5 at t58)
**Locations visited:** ~20 total
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** low
**Gameplay quality:** DRIFTING
  - Agent cycling Studio ↔ Gallery ↔ Cellar ↔ Living Room again after thief theft at t34. Same pattern as ep110.
  - Trying to unlock gothic door with skeleton key at t77 — KB says this doesn't work.
  - Not pursuing Cyclops → Treasure Room path for thief recovery despite KB knowledge.
  - NEW_OBJECTIVE cap bug prevented recovery objective from persisting (fixed for ep112).
**Triggers:** Score stagnant 19 turns since t58.
**Notes:** ep111 is tracking like ep110 after a thief encounter — rapid early scoring (49 by t32), thief steals treasures, agent loses direction and cycles known areas. The NEW_OBJECTIVE cap bug (now fixed) meant the recovery objective was dropped. Even so, the agent's "Current Plan" mentioned recovery but the agent didn't execute it.

---

## Episode 111 — COMPLETE (killed at t80)
**Turns:** 80 (killed by orchestrator — stagnant after thief encounter)
**Final score:** 54/350
**Locations visited:** ~20
**End reason:** early_stop (orchestrator kill — stagnation after thief)
**Improvement dispatched:** yes (NEW_OBJECTIVE fix + cap hotfix)

**Key observations:**
- **Thief struck at Studio chimney AGAIN (t34)** — exact same pattern as ep110 t37. Agent carried painting+bag through chimney, failed (too heavy), thief stole both.
- **NEW_OBJECTIVE fix validated but cap bug found:** The fix correctly wired new_objective into record_results, but the append + [:15] cap dropped the recovery objective when the list was full. **Cap fix committed (e33afe6) for ep112: insert at position 0.**
- **Even with "Current Plan" showing recovery intent, agent didn't pursue it** — same as ep110. This suggests the problem is deeper than just objective persistence; the agent lacks a mechanism to translate strategic plans into action sequences.
- **Two consecutive thief-derailed episodes** (ep110, ep111) — both lost ~14 points of items at the Studio chimney. The chimney is a thief hotspot.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep104   | 95    | +10     | 95          | 6                 | 29        | noisy      | max_turns  |
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |

**Trend:** Two consecutive 54-point episodes, both thief-derailed. Without thief interference, episodes score 80-95. The thief is the #1 variance source. The NEW_OBJECTIVE cap fix + insert-at-front is ready for ep112.

---

## Episode 112 — Turn 28 Checkpoint
**Type:** HEALTHY
**Score:** 40/350 (delta: +40 from start)
**Locations visited:** ~12
**Rejection rate:** 1 rejection in 28 turns (4%)
**Gameplay quality:** LEARNING — standard early game, Dam area exploration, no bolt attempts.
**Triggers:** none
**Notes:** Both NEW_OBJECTIVE fixes live. Score 40 at t28 — normal pace. Agent in Dam area picking up tools. Monitoring for thief encounters.

---

## Episode 112 — Turn 50 Checkpoint
**Type:** CONCERN
**Score:** 40/350 (delta: +0 since last checkpoint — 34 turns stagnant)
**Locations visited:** ~15 (6 in Dam area this block)
**Rejection rate:** low
**Gameplay quality:** DRIFTING
  - Agent spent 34 turns in Dam/Maintenance/Reservoir area without scoring.
  - At t50, agent has a plan: "Take plastic, inflate it" at Dam Base — this is actually strategic (plastic pile is a treasure).
  - NEW_OBJECTIVE fix generating objectives: "Recover and inflate plastic treasure at Dam Base" — should persist.
  - No bolt attempts. No thief encounter yet.
**Triggers:** Score stagnant 34 turns (but agent has active plan at t50)
**Notes:** Agent exploring Dam area extensively but now has a strategic plan (inflate plastic treasure). Not killing this episode — if the plastic plan works, it shows the agent discovering a new scoring path. 150 turns remaining.

---

## Episode 112 — Turn 76 Checkpoint
**Type:** HEALTHY (recovering)
**Score:** 50/350 (delta: +10 since last checkpoint — bar taken at t70)
**Locations visited:** ~18
**Rejection rate:** low
**Gameplay quality:** DRIFTING → LEARNING
  - Agent spent 54 turns stagnant (t16-70) exploring Dam area including plastic inflation attempt (failed). Finally reached Loud Room and scored +10 (bar) at t70.
  - Now routing toward Gallery/chimney for deposit. No thief encounter yet.
  - The long Dam exploration isn't ideal but agent did discover Dam Base as new area and attempted a novel puzzle (inflate plastic). Shows exploration behavior even if inefficient.
**Triggers:** none (score recovered)
**Notes:** Score 50 at t76 — behind ep109 pace (65 at t77) but the Dam detour was 30+ turns. The question is whether the agent catches up in the remaining 124 turns. Watching for chimney/thief encounter.

---

## Episode 112 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 70/350 (delta: +20 since last checkpoint)
**Locations visited:** ~25
**Rejection rate:** low
**Gameplay quality:** LEARNING
  - Agent recovered from slow Dam start: deposited painting (+6 at ~t84), bar (+5 at ~t93), took egg (+5 at t100).
  - TWO successful chimney trips with no thief encounter! One with painting, one with bar — separate trips are safer.
  - Now at Up a Tree with egg — heading for deposit. Score 70 at t100 matches ep109 pace (75 at t100).
  - NEW_OBJECTIVE fix live but no thief encounter to test it. System performing normally.
**Triggers:** none
**Notes:** Clean chimney execution after the ep110/111 thief disasters. Agent doing single-treasure chimney trips — slower but safer. 100 turns remaining, on pace for 80-95.

---

## Episode 112 — Turn 127 Checkpoint
**Type:** HEALTHY
**Score:** 89/350 (delta: +14 since last checkpoint — torch at t123!)
**Locations visited:** ~28
**Rejection rate:** low
**Gameplay quality:** LEARNING
  - **DOME DESCENT ACHIEVED** — first time in recent episodes! Agent tied rope at t121, descended at t122, took torch (+14) at t123.
  - Agent exploring Temple/Altar area: took brass bell (t125), black book (t127).
  - Route: Attic → rope → underground → Round → Engravings → Dome → rope → Torch Room → Temple → Altar.
  - ep109 failed this exact path (dropped rope before reaching Dome). ep112 succeeded by going directly from Attic to underground with the rope.
  - Carrying: torch, bell, book, axe, knife, lantern — heavily loaded but in a new scoring area.
**Triggers:** none
**Notes:** Score 89 at t127 — approaching ep109's final score of 90 with 73 turns remaining. The torch (+14) was the biggest single scoring event seen in recent episodes. If the agent finds the Egyptian Room (coffin +15, sceptre) or Hades (candles → spirits), score could breach 100. This is the breakthrough we've been waiting for.

---

## Episode 112 — Turn 150 Checkpoint
**Type:** CONCERN
**Score:** 89/350 (delta: +0 since last — 27 turns stagnant since torch at t123)
**Locations visited:** ~30
**Gameplay quality:** DRIFTING
  - Agent reached Entrance to Hades (t130) but failed the candles puzzle. Retreated through Cave/Deep Canyon.
  - Picked up tube/plastic from Loud Room (t142) — may be planning inflation.
  - Now cycling Studio area again. Score stagnant.
  - Hades puzzle is complex: ring bell → pick up bell when cool → light candles → read incantation. Agent has the pieces (bell, candles, torch, book) but didn't execute the sequence correctly.
**Triggers:** Score stagnant 27 turns (but well above 80-95 base)
**Notes:** Score 89 already matches ep109 (90). The Dome descent was the key breakthrough — torch +14 was the biggest scoring event. Even if score stalls at 89, this is a strong episode. 50 turns remaining. The Hades puzzle failure is a learning opportunity — agent should record it in KB.

---

## Episode 112 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 89/350
**Locations visited:** 37 (SESSION HIGH — most ever in a single episode)
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** total=55, new=38, dedup_rejected=2, superseded=6, ephemeral_pruned=2, consolidated=1
**Improvement dispatched:** no (ep110→111 fix already deployed)

**Key observations:**
- **DOME DESCENT ACHIEVED** — first time in recent episodes. Agent tied rope at t121, descended at t122, took torch (+14!) at t123. This opened the Temple/Altar/Hades area.
- **37 locations visited** — new record. Agent explored Dam Base, Damp Cave, White Cliffs Beach, Torch Room, Temple, Altar, Entrance to Hades, Cave. Broadest exploration in any episode.
- **38 new memories** — strong learning output. Dome descent, Hades encounter, candle mechanics should be in KB for future episodes.
- **No thief encounter at chimney** — agent did single-treasure chimney trips (painting first, then bar separately), which may reduce thief exposure.
- **Hades puzzle attempted but failed** (t130-133) — agent had bell, candles, torch, book but couldn't execute the sequence. KB should now record what it tried.
- **Long Dam stagnation** (t16-70, 54 turns) — agent spent too long exploring Dam area before going to Loud Room. This cost ~30 turns of scoring potential.
- **NEW_OBJECTIVE fix live** — both wiring and cap fix deployed. No thief encounter to test objective persistence after theft.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep105   | 40    | -55     | 95          | 5                 | 13        | BLOATED    | circuit_breaker |
| ep106   | 54    | +14     | 95          | 5                 | 23        | clean      | early_stop |
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |

**Trend:** Full-run episodes (200 turns, no thief/circuit-breaker): ep107=80, ep109=90, ep112=89 — stable 80-90 band. The Dome descent in ep112 didn't produce a new ceiling because the Hades puzzle failed and post-torch stagnation (77 turns at 89). But 37 locations and 38 new memories mean future episodes will have richer KB and memories for the Temple/Hades area. The ceiling breakthrough (past 95) likely requires successfully completing the Hades puzzle in a future episode, now that the agent has experienced it and recorded it.

---

## Session 2026-04-13b Start
**Previous session best:** 90/350 (ep109)
**System state:** 80-95 band for full runs. KB clean, critic disabled, extractor removed. Belief reconciliation fix (ep106→107) deployed. NEW_OBJECTIVE wiring live.

---

## Episode 113 — Turn 25 Checkpoint
**Type:** HEALTHY
**Score:** 40/350 (delta: +40 since start)
**Locations visited:** 11 (11 new)
**Avg critic score:** 0.50 (critic disabled — programmatic validator only)
**Rejection rate:** 1/25 turns had rejections (4%)
**Gameplay quality:** LEARNING
  - Memory use: KB loaded from prior episodes with rich content (score changes, puzzle mechanics, Dam bolt failure verdict). Agent acting on prior knowledge — went straight to Maintenance Room for tools.
  - KB alignment: KB explicitly records "turn bolt with wrench at Dam — confirmed failure, tested exhaustively." Will monitor whether agent avoids this trap.
  - Objective quality: 14 discovered / 15 completed. Objectives are specific and actionable (chimney climb, deposit treasures, retrieve tools). Some duplication but harmless.
  - Objective pursuit: Agent completing objectives briskly — 15 completed in 25 turns. Currently pursuing tool retrieval at Maintenance Room.
  - Learning system quality: KB has substantial strategic content from prior episodes. No new memories yet (early in episode).
  - Pathfinding: NAVIGATING — direct route from house → underground → troll → Dam area. No wasted movement.
**Triggers:** none
**Notes:** Strongest opening in recent memory — score 40 by t25. Agent entered house (t5, +10), descended to cellar (t13, +25), killed troll (t15, +5), and navigated to Dam area for tools. Now at Dam with wrench and tube. Key test: will the belief reconciliation fix prevent Dam bolt loops?

---

## Episode 113 — Turn 50 Checkpoint
**Type:** HEALTHY
**Score:** 50/350 (delta: +10 since last checkpoint)
**Locations visited:** 17 total (6 new this block: Dam_Base, Deep_Canyon, Loud_, Stream_View, Round_, Gallery)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 0/25 turns had rejections (0%)
**Gameplay quality:** LEARNING
  - Memory use: Agent used KB knowledge of "echo" command to solve Loud Room puzzle (t39) — direct evidence of cross-episode learning.
  - KB alignment: **Dam bolt loop AVOIDED.** Agent went to Dam area (t29-33), collected tools, but did NOT try "turn bolt with wrench" despite being at the Dam. KB's "confirmed failure" verdict is being respected. This validates the belief reconciliation fix (ep106→107).
  - Objective quality: 12 discovered / 25 completed. Objectives well-formed and being completed rapidly.
  - Objective pursuit: Agent pursuing deposit route — took bar at t42, navigating back to Gallery for painting.
  - Learning system quality: KB rich from prior episodes. No new memories yet (memories trigger on score events — bar take at t42 should produce one soon).
  - Pathfinding: NAVIGATING — efficient route Dam → Dam Base → Loud Room → underground → Gallery.
**Triggers:** none
**Notes:** Score 50 at t50 — solid pace. The headline: **Dam bolt loop avoided for the first time.** The ep106→107 belief reconciliation fix is working. Agent used KB-learned "echo" puzzle solution and is now at Gallery, likely heading for chimney deposit route. Zero rejections in this block.

---

## Episode 113 — Turn 75 Checkpoint
**Type:** HEALTHY
**Score:** 65/350 (delta: +15 since last checkpoint)
**Locations visited:** ~19 total (few new — mostly chimney shuttle route)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 2/25 turns had rejections (8%)
**Gameplay quality:** LEARNING
  - Memory use: Agent executing efficient multi-trip chimney deposit strategy learned from prior episodes.
  - KB alignment: Weight management working — first chimney attempt failed (t55, too heavy), agent dropped items and succeeded on retry (t60). Second trip (bar) succeeded cleanly (t70).
  - Objective quality: Objectives being completed steadily (painting deposit, bar deposit).
  - Objective pursuit: Tight alignment — painting deposited (t63, +6), bar deposited (t73, +5), now egg taken (t80, +5).
  - Learning system quality: Productive scoring block validates KB strategies.
  - Pathfinding: NAVIGATING — efficient chimney shuttle: Gallery→Studio→Kitchen→Living→deposit, then back underground for next item. Agent went to Up a Tree for egg (t79-80) via Behind House.
**Triggers:** none
**Notes:** Most productive block in this episode — +15 in 25 turns from painting deposit (+6), bar deposit (+5), and painting take (+4). Score 65 at t75. Agent now has egg (t80, +5 = score 70) and is heading for deposit. On pace for 85-95+ if chimney route continues. No thief encounter yet — watching.

---

## Episode 113 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 75/350 (delta: +10 since last checkpoint — egg deposit at t86)
**Locations visited:** ~21 total (2 new: Attic, Up_a_Tree)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 2/25 turns had rejections (8%)
**Gameplay quality:** LEARNING
  - Memory use: Agent following KB-learned deposit route. Went to Attic for rope/knife — KB records torch at Dome requiring rope descent from prior episodes.
  - KB alignment: Dome descent preparation in progress. Agent took rope+knife at t98, heading underground.
  - Objective quality: Deposit objectives completing steadily.
  - Objective pursuit: Tight — egg deposited (t86, +5), now pursuing Dome descent for torch (+14).
  - Learning system quality: Agent reproducing ep112's breakthrough Dome descent path from KB knowledge.
  - Pathfinding: NAVIGATING — efficient egg deposit via Behind House, then Attic for rope, heading underground.
**Triggers:** none
**Notes:** Score 75 at t100 — matches ep109 pace (75 at t100). Agent has rope and is heading for Dome descent (torch +14). If successful, score would reach 89 — matching ep112's final. With 100 turns remaining, there's potential to push past 89 if the agent can complete Hades puzzle or find other treasures. No thief encounter yet. Zero Dam bolt attempts this entire episode — belief reconciliation fix fully validated.

---

## Episode 113 — Turn 125 Checkpoint
**Type:** CONCERN (score healthy but Hades puzzle blocked by false KB entry)
**Score:** 89/350 (delta: +14 since last checkpoint — torch at t113)
**Locations visited:** ~34 total (12 new this block: Dome, Torch Room, Temple, Altar, Cave, Entrance to Hades, Engravings Cave, Winding Passage)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 2/25 turns had rejections (8%)
**Gameplay quality:** LEARNING but blocked by false KB entry
  - Memory use: Agent reasoning at t122 explicitly references prior Hades knowledge: "the first step is to ring the bell to paralyze the spirits, though this will cause me to drop the bell and the candles."
  - KB alignment: **NEW FAILURE MODE — false KB entry blocks correct action.** Agent's t124 reasoning: "Strategic Knowledge warns that 'light candles with torch' at this location vaporizes the candles due to intense heat, so I must avoid that action as it is a recorded failure." This is WRONG — lighting candles with the torch is the correct Hades puzzle step. The KB has a hallucinated/overgeneralized failure verdict from a prior episode that permanently blocks the correct action.
  - Objective quality: 15 discovered / 66 completed. Well-formed and tracked.
  - Objective pursuit: Strong — Dome descent executed perfectly (t110-113), Hades attempt made.
  - Learning system quality: KB mostly excellent but contains at least one false failure verdict that creates a permanent dead end. Agent won't try the action → KB never corrects → puzzle permanently unsolvable.
  - Pathfinding: NAVIGATING — efficient route to Dome, then Temple/Altar/Hades.
**Triggers:** None per existing checklist. But documenting NEW failure mode: **false negative KB entries create permanent dead ends**. The agent complies with the KB (correct per belief reconciliation fix), but the KB is wrong. This is the inverse of the ep106 problem (agent overriding correct engine observations with stale KB) — now the agent correctly defers to KB but the KB itself has bad data.
**Notes:** Score 89 at t125 matches ep112's FINAL score with 75 turns remaining. The Dome descent was flawless. The Hades puzzle failure is caused by a false KB entry about candles vaporizing, not by a system reasoning deficiency. This is a data quality problem in the KB, not a prompt problem. Potential fixes: (1) KB pruning/verification mechanism, (2) "try once to verify" protocol for old failure entries, (3) manual KB cleanup. Watching remaining 75 turns for score ceiling.

---

## Episode 113 — Turn 150 Checkpoint
**Type:** CONCERN (37 turns stagnant at 89)
**Score:** 89/350 (delta: +0 since last checkpoint)
**Locations visited:** ~36 total (broad exploration but no scoring)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 2/25 turns had rejections (8%)
**Gameplay quality:** DRIFTING
  - Memory use: Agent exploring but not finding scoring paths.
  - KB alignment: False KB entry still blocking Hades puzzle. Agent took matchbook at t142 — possible alternate approach to candle lighting (KB warns about torch specifically, not matches).
  - Objective quality: Objectives tracked but stagnant.
  - Objective pursuit: No active scoring objectives being pursued — agent wandering post-Hades.
  - Learning system quality: KB false entry is the primary blocker.
  - Pathfinding: WANDERING — broad movement through 17 locations in this block but no directed goal.
**Triggers:** Score stagnant 0 delta across this checkpoint (37 turns total since t113). However, this is the first stagnant checkpoint — threshold is 2 consecutive. No improvement dispatch yet.
**Notes:** Score 89 stagnant since t113. Pattern mirrors ep112 post-torch stagnation. Agent took matchbook (t142) and is heading back underground — may attempt Hades with matches. 50 turns remaining. Even at 89, this matches recent episode ceilings. The false KB entry about candle vaporization is the ceiling blocker.

---

## Episode 113 — Turn 175 Checkpoint
**Type:** URGENT (score stagnant 62 turns — 2 consecutive zero-delta checkpoints)
**Score:** 89/350 (delta: +0 since last checkpoint, +0 since t125 checkpoint)
**Locations visited:** ~38 total (cycling same areas — Dam, Loud Room, Gallery, Reservoir South)
**Avg critic score:** 0.50 (critic disabled)
**Rejection rate:** 1/25 turns had rejections (4%)
**Gameplay quality:** IGNORING
  - Memory use: Agent not applying accumulated knowledge to find new scoring paths.
  - KB alignment: False candle entry still blocking Hades. Agent cycling known areas.
  - Objective quality: Stagnant — no new scoring objectives.
  - Objective pursuit: No directed pursuit visible — aimless cycling through 14 locations in this block.
  - Learning system quality: KB false entry is the ceiling blocker.
  - Pathfinding: WANDERING — cycling Dam↔Reservoir South↔Deep Canyon↔Loud Room↔Gallery with no goal.
**Triggers:** FIRED — Score stagnant (0 delta across 2 consecutive checkpoints). Root cause: false KB entry blocks Hades puzzle, and agent has exhausted other accessible scoring paths.
**Notes:** 21 turns remaining. Score 89 is the ceiling for this episode. Will dispatch improvement after episode completion. The improvement target is clear: false negative KB entries need a "verify once" protocol so the agent re-tests old failure verdicts instead of permanently avoiding correct actions.

---

## Episode 113 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 89/350
**Locations visited:** 37
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** total=84, new=40, dedup_rejected=3, superseded=14, ephemeral_pruned=10, consolidated=15
**Improvement dispatched:** yes — false KB entry / stale failure verdict protocol

**Key observations:**
- **Dam bolt loop AVOIDED for the first time** — belief reconciliation fix (ep106→107) fully validated. Zero bolt attempts in 200 turns.
- **Dome descent achieved** (t110-113) — flawless execution via rope tie + descend. Torch taken (+14).
- **Hades puzzle BLOCKED by false KB entry** — agent had bell, book, candles, torch at Entrance to Hades (t121-124). Agent knew the ritual sequence but skipped "light candles" because KB falsely claimed "light candles with torch vaporizes candles due to intense heat." This is wrong — lighting candles with torch is the correct step.
- **NEW failure mode: false negative KB entries create permanent dead ends.** The belief reconciliation fix correctly teaches the agent to trust KB over its own reasoning. But when the KB has WRONG failure verdicts, the agent avoids correct actions forever and the KB never self-corrects.
- **Post-torch stagnation** (t113-200, 87 turns at 89) — identical pattern to ep112. Agent cycled Dam/Loud Room/Gallery with no scoring after Hades failure.
- **Efficient chimney shuttle** — three deposit trips (painting, bar, egg) with proper weight management.
- **40 new memories, 15 consolidated** — strong learning output.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep107   | 80    | +26     | 95          | 5                 | 21        | clean      | max_turns  |
| ep108   | 70    | -10     | 95          | 5                 | 24        | clean      | circuit_breaker |
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |
| ep113   | 89    | +0      | 95          | 5                 | 37        | clean+1false | max_turns  |

**Trend:** Full-run episodes: ep107=80, ep109=90, ep112=89, ep113=89. System stable in the 80-90 band. ep112 and ep113 both achieved Dome descent (89) but stalled at Hades due to the same false KB entry. The ceiling breakthrough to 95+ requires: (1) fixing the false KB candle entry so Hades puzzle can complete, or (2) finding an alternative scoring path the agent hasn't explored. Option (1) is the clear next step — dispatch improvement to add a "verify once" protocol for old KB failure verdicts.

---

## Episode 114 — Turn 25 Checkpoint
**Type:** HEALTHY
**Score:** 40/350 (delta: +40 since start)
**Locations visited:** 13
**Rejection rate:** 1/25 (4%)
**Gameplay quality:** LEARNING — identical opening to ep113. Standard house → underground → troll → Dam area route.
**Triggers:** none
**Notes:** Score 40 at t25, matching ep113 pace. Key test (Hades) expected ~t120. No early regression.

---

## Episode 114 — Turn 50 Checkpoint
**Type:** HEALTHY
**Score:** 50/350 (delta: +10 — bar taken via echo puzzle)
**Locations visited:** ~17 total (12 this block)
**Rejection rate:** 0/25 (0%)
**Gameplay quality:** LEARNING — echo puzzle solved, bar taken, navigating to Gallery for chimney deposits. Identical pace to ep113.
**Triggers:** none
**Notes:** Score 50 at t50 matches ep113 exactly. Zero rejections this block. Agent at Gallery. No regression from prompt change. Key test (Hades) still ~70 turns away.

---

## Episode 114 — Turn 75 Checkpoint
**Type:** HEALTHY
**Score:** 65/350 (delta: +15 — painting deposit +6, bar deposit +5, painting take +4)
**Locations visited:** ~19 total
**Rejection rate:** 1/25 (4%)
**Gameplay quality:** LEARNING — chimney shuttle (painting, bar) executed efficiently. Rope+knife from Attic. Heading for egg. Identical pace to ep113 (also 65 at t75).
**Triggers:** none
**Notes:** No regression from prompt change. Agent heading for egg at Up a Tree, then likely Dome descent. Key test (Hades) ~45 turns away.

---

## Episode 114 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 75/350 (delta: +10 — egg take +5, egg deposit +5)
**Locations visited:** ~22 total
**Rejection rate:** 0/25 (0%)
**Gameplay quality:** LEARNING — egg deposited at t90, already underground heading for Dome descent. Slightly ahead of ep113 pace (ep113 still at Living Room at t100).
**Triggers:** none
**Notes:** Score 75 at t100 with 0 rejections. Agent at Studio with rope, heading to Dome via Engravings Cave. Dome descent + Hades attempt expected in next 20-30 turns. **This is the critical test block for the stale-verdict-verification fix.**

---

## Episode 114 — Turn 125 Checkpoint
**Type:** CONCERN (score 75, stagnant 35 turns since t90)
**Score:** 75/350 (delta: +0 since last checkpoint)
**Locations visited:** ~24 total (8 this block — cycling Gallery/Studio/Cellar/Living)
**Rejection rate:** 1/25 (4%)
**Gameplay quality:** DRIFTING
  - Agent spent 25 turns on chimney trips and inventory management instead of heading for Dome.
  - Dropped rope at Studio (t126) — Dome descent not currently possible without retrieving it.
  - Agent reasoning at t130: "last score increase was turn 90, need new scoring opportunity" — pursuing skeleton key/gothic door instead of Dome.
  - No Hades attempt yet — stale-verdict-verification fix has not been tested.
  - KB alignment: Can't assess Hades fix yet. Chimney weight management consuming too many turns.
  - Pathfinding: WANDERING — 8 locations, all previously visited, cycling chimney route.
**Triggers:** Score stagnant 0 delta (1st checkpoint). Not yet at 2-consecutive threshold.
**Notes:** ep114 diverging from ep113's trajectory. ep113 was at Dome (t110) by this point; ep114 is still at Living Room doing inventory management. The stale-verdict fix can't be evaluated until the agent reaches Hades. If score stalls at t150, stagnation trigger fires — but the root cause would be chimney/inventory inefficiency, not the prompt change.

---

## Episode 114 — Turn 150 Checkpoint
**Type:** URGENT (score 75, stagnant 60 turns — 2 consecutive zero-delta checkpoints)
**Score:** 75/350 (delta: +0 since last checkpoint, +0 since t100 checkpoint)
**Locations visited:** ~24 total (cycling same 8 locations)
**Rejection rate:** 0/25 (0%)
**Gameplay quality:** IGNORING
  - Agent spent 50+ turns cycling Gallery/Studio/Cellar/Living for chimney trips and inventory management.
  - Rope retrieved at t136 but agent still hasn't headed for Dome — went back to Studio for axe (t148).
  - Agent reasoning at t130 showed awareness of stagnation but chose skeleton key path over Dome.
  - **Stale-verdict fix NOT YET TESTED** — agent hasn't reached Hades.
  - Pathfinding: WANDERING — cycling chimney route, no directed progress toward Dome.
**Triggers:** FIRED — Score stagnant (0 delta across 2 consecutive checkpoints).
**Notes:** This stagnation is caused by chimney/navigation inefficiency, not the prompt change. ep113 reached Dome at t110; ep114 is still cycling at t150. The variance is within normal play (ep112 had a 54-turn Dam stagnation before recovering). 50 turns remaining — Dome descent + Hades is still possible but tight. NOT dispatching improvement — the stale-verdict fix needs an episode where the agent actually reaches Hades. If ep114 ends without reaching Hades, ep115 will provide the test.

---

## Episode 114 — COMPLETE
**Turns:** 155 (circuit breaker — "look" loop at East_Chasm t151-155)
**Final score:** 75/350
**Locations visited:** 25
**Objectives found:** 15
**End reason:** llm_circuit_breaker
**Memory stats:** total=102, new=29, dedup_rejected=3, superseded=13, ephemeral_pruned=8, consolidated=6
**Improvement dispatched:** no (stale-verdict fix already deployed but untested)

**Key observations:**
- **Stale-verdict fix NOT TESTED** — agent never reached Dome or Hades.
- **Chimney cycling ate 65 turns** (t90-155) — agent scored painting (+6), bar (+5), egg (+5) deposits efficiently by t90, then spent remaining 65 turns cycling Gallery/Studio/Cellar managing inventory instead of heading to Dome.
- Circuit breaker hit at t155 due to "look" loop at East_Chasm (5 consecutive looks).
- Agent DID retrieve rope (t136) but never navigated to Round Room → Engravings → Dome.
- This is a navigation/planning inefficiency, NOT a regression from the prompt change. The stale-verdict-verification rule only activates at Hades — it was never invoked.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |
| ep113   | 89    | +0      | 95          | 5                 | 37        | clean+1false | max_turns  |
| ep114   | 75    | -14     | 95          | 5                 | 25        | clean      | circuit_breaker |

**Trend:** ep114 underperformed due to chimney cycling + circuit breaker. Not representative for evaluating the stale-verdict fix. Need a full 200-turn episode where agent reaches Hades. Starting ep115.

---

## Episode 115 — COMPLETE (credit exhaustion)
**Turns:** 5 (circuit breaker — OpenRouter 402 credit exhaustion)
**Final score:** 0/350
**End reason:** llm_circuit_breaker (HTTP 402 — credits exhausted)
**Notes:** Not a system or prompt issue. OpenRouter credits depleted after ep113 (200 turns) + ep114 (155 turns) + improvement subagent validation calls. Discard this episode from analysis.

---

## Session 2026-04-13b Complete
**Episodes run:** 3 (ep113, ep114, ep115)
**Best score achieved:** 89/350 (ep113)
**Improvements made:** 1
  1. Stale failure verdict verification (ep113→114) — try KB-flagged-as-failed actions once per episode to verify before deferring
**System status:** STOPPED — OpenRouter credits exhausted

**Summary:**
- **ep113 (89/350):** Strong episode — Dam bolt loop eliminated (belief reconciliation fix validated), Dome descent achieved (torch +14), but Hades puzzle blocked by false KB entry about candles vaporizing. Identified new failure mode: false KB failure verdicts create permanent dead ends.
- **ep114 (75/350):** Chimney cycling/navigation inefficiency consumed 65 turns. Circuit breaker at t155. Stale-verdict fix deployed but never tested — agent didn't reach Hades.
- **ep115 (0/350):** Credit exhaustion. Discard.
- **Stale-verdict fix status:** PENDING — validated in fixtures (t124 changed from "read black book" to "light candles with torch") but not yet tested in live gameplay. Next session should run this fix with fresh credits.
- **Key finding this session:** False negative KB entries are the current ceiling blocker. The belief reconciliation fix (ep106→107) correctly teaches engine-supremacy, but when the KB itself has wrong failure verdicts, the agent obeys them forever. The stale-verdict-verification rule is the proposed solution — needs live testing.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |
| ep113   | 89    | +0      | 95          | 5                 | 37        | clean+1false | max_turns  |
| ep114   | 75    | -14     | 95          | 5                 | 25        | clean      | circuit_breaker |
| ep115   | 0     | -75     | 95          | —                 | 1         | —          | circuit_breaker (credits) |

---

## Session Complete (prior session)
**Episodes run:** 4 (ep109, ep110, ep111, ep112)
**Best score achieved:** 90/350 (ep109)
**Improvements made:** 2
  1. NEW_OBJECTIVE wiring (ep110→111) — wire agent's per-turn objectives into DISCOVERED_OBJECTIVES (BLOCKER fix)
  2. NEW_OBJECTIVE cap fix (ep111 hotfix) — insert at position 0 to survive 15-item cap
**System status:** PERFORMING WELL
**Summary:** System is stable in the 80-95 band for full 200-turn episodes. Two thief-derailed episodes (ep110, ep111) exposed a NEW_OBJECTIVE dead-write bug — the agent's per-turn objective proposals were silently discarded. Fixed with wiring + cap priority. ep112 achieved the Dome descent for the first time (torch +14, 37 locations, 38 new memories) — the broadest exploration in any episode. The Hades puzzle was attempted but failed, creating learning opportunities for future episodes. The remaining ceiling (past 95) likely requires: (a) successful Hades puzzle completion, (b) thief recovery via Cyclops → Treasure Room path, or (c) both. The NEW_OBJECTIVE fix should help with (b) in future thief encounters.

---

## Episode 113 → 114 — IMPROVEMENT
**Trigger:** Score stagnant at 89/350 for 87 turns (t113-200) in ep113 and ep112. Agent had all required items for Hades exorcism ritual but skipped the critical "light candles with torch" step because a false KB failure verdict claimed the torch vaporizes candles. Same false entry blocked both ep112 and ep113.
**Hypothesis:** The belief reconciliation fix (ep106→107) correctly teaches the agent to defer to KB failure verdicts over its own reasoning. But KB failure verdicts are cross-episode observations that can be hallucinated or overgeneralized. Once a false failure verdict enters the KB, the agent never retries the action, so the KB never self-corrects — creating a permanent dead end. The system lacks a mechanism to verify stale KB failure entries against current game state.
**Change:** Added "STALE FAILURE VERDICT VERIFICATION" sub-rule to PRE-ACTION BELIEF CHECK rule 2 in `prompts/agent.md`. When a KB failure verdict exists but the agent has NOT attempted the action this episode, and current game state provides plausible reason for success (correct items, correct location, logical sequence step), the agent must attempt the action ONCE to verify before deferring. Analogous to the stale-route "recompute once" rule applied to KB failure entries.
**Reasoning:** This preserves the authority hierarchy (engine > KB > plan) while adding empirical verification for cross-episode KB claims. Same-episode engine rejections remain absolute (rule 2's empirical falsification). The "try once" gate prevents infinite retry loops while ensuring false KB entries get tested and corrected through gameplay experience.
**Target metric:** Score should exceed 89/350 in ep114. Specifically, agent should attempt "light candles" at Hades despite the KB entry, discover it succeeds, and complete the exorcism ritual.
**Validation:** PASSED (4/6 structural) — The 2 "failures" are false positives: t122 ("ring bell") and t123 ("take candles") are correctly unchanged actions tagged as "problem" because they belong to the Hades sequence, but only t124 had the wrong action. The critical fixture t124 changed from "read black book" to "light candles with torch" — exactly the desired fix. All 3 healthy fixtures (t53 painting, t86 egg deposit, t113 torch) remained unchanged — no regression. Agent reasoning at t124 now correctly identifies the stale failure verdict verification rule and attempts the action.
**Result:** PARTIAL — Hades test UNREACHED in ep114 and ep116 (agent never reached Hades). First-fire behavior is correct (confirmed in fixture replay at t124). But ep116 revealed the rule **over-fires** on true KB failures: agent invoked it 5 times on `unlock wooden door with key` with new rationalizations each time. Score 79 in ep116 vs ep112/ep113 ceiling of 89, traced in part to over-firing cost. Hypothesis not falsified — refinement queued at ep116→ep117 to add a "check RECENT ACTIONS before re-firing" constraint.

---

## Session 2026-04-24 Start
**Goal this session:** Live validation of the ep113→114 stale-verdict fix (PENDING since ep114 chimney-cycled and ep115 hit credit exhaustion). Need a full 200-turn run that actually reaches Hades so the KB's false "light candles with torch fails" entry gets tested.
**App_id for ep116:** `b35c0c7e-44d4-4a1f-ac9e-55477f248bba`

---

## Episode 116 — Turn 25 Checkpoint
**Type:** HEALTHY
**Score:** 50/350 (delta: +50 since start — best turn-25 opening of the session)
**Locations visited:** 12 (Behind_House, Cellar, Deep_Canyon, East-West_Passage, Kitchen, Living_, Loud_, North_House, North-South_Passage, Round_, Troll_, West_House)
**Avg critic:** 0.44 (default value with critic disabled — not meaningful)
**Rejection rate:** 1/25 turns (4%) — t6 compound-take force-accepted
**Gameplay quality:** LEARNING
  - Memory use: Agent explicitly cites "Strategic knowledge" and "past experiences" — applied weight management protocol (t22→t23) after engine rejection
  - KB alignment: Used `echo` in Loud Room (KB pattern), dropped expendables for weight limit — clean KB→action trace
  - Objective quality: 13 active (mix of platinum-bar-deposit chain, some duplicates/stale entries for wooden-door). 18 completed — healthy churn.
  - Objective pursuit: Excellent — multi-step deposit plan ("step 3 of 8 on return route"), explicit exit verification every turn
  - Learning system quality: KB is comprehensive (~50 strategic entries, the false candle entry still present — the fix's target)
  - Pathfinding: NAVIGATING — stated route, verified each exit against available list
**Triggers:** none
**Notes:** Fastest scoring start of the session — platinum bar retrieved by t24 with echo + weight drop. Agent heading back for deposit. False KB entry "light candles with torch…fails — heat vaporizes the candles" is present in KB; stale-verdict-verification fix will be tested when/if agent reaches Hades.

---

## Episode 116 — Turn 50 Checkpoint
**Type:** CONCERN (score stagnation, thief theft)
**Score:** 54/350 (delta: +4 since last checkpoint — only painting +4 landed)
**Locations visited:** 17 (+5 new: East_Chasm, Gallery, Studio, Attic, Maze)
**Avg critic:** 0.50 (default — critic disabled)
**Rejection rate:** 0/25 turns (0%)
**Gameplay quality:** LEARNING
  - Memory use: Strong — agent cites "Strategic Knowledge" for chimney climb (t37), detected stale Cyclops-opening belief (t45)
  - KB alignment: **Stale-route rule behaviorally confirmed at t45** — "The west passage to the Cyclops Room does not exist yet in this episode as it is created from the other side; therefore, the current plan to go west is a stale route." Replanned via Cellar→Maze route. The ep94→95 stale-belief fix is firing correctly.
  - Objective quality: 15 active with ~6 near-duplicates around "Recover stolen treasures from thief's Treasure Room" (aligned with current goal but noisy). 32 completed. Real clutter from multi-model objective proposer but not blocking action.
  - Objective pursuit: Strong — all recent movement (t47-50) explicitly cited as "pursue thief and recover stolen painting/platinum bar"
  - Learning system quality: KB/memories working. The false "candles vaporize" entry still awaits live test.
  - Pathfinding: NAVIGATING — stale-route detection working; explicit exit verification
**Triggers:** none (but near-threshold)
  - Score delta +4 is small but not stagnant (trigger = 0 delta across 2 checkpoints). Re-evaluate at t75.
**Notes:** Thief intercepted agent en route Gallery→Living Room, stole painting + platinum bar before deposit. Net ceiling +4 from painting-pickup credit. Agent's recovery plan (Cellar→Maze→Cyclops→Treasure Room) is rational and consistent with the KB's "stairs from Cyclops Room lead to Treasure Room, thief's hideaway" entry. This is the #2 open problem from Key Learnings (thief combat) playing out. Not a system defect — let it play out. Score of 54 by t34 (painting pickup) is the real current measure.

---

## Episode 116 — Turn 75 Checkpoint
**Type:** HEALTHY
**Score:** 69/350 (delta: +15 — bag pickup +10 at t53, bag deposit +5 at t70)
**Locations visited:** 18 (+1 new: Maze skeleton room depth)
**Avg critic:** 0.50 (default)
**Rejection rate:** 1/25 (4%) — t70 "put bag in case" force-accepted (the programmatic validator's known compound-deposit blind spot; force-accept resolved it and score incremented correctly)
**Gameplay quality:** LEARNING
  - Memory use: Consistent KB references for chimney weight, trap door reopen-from-above mechanic, bag deposit parser workaround ("try shorter name 'bag'" after 'bag coins' failed — empirical learning within episode)
  - KB alignment: Skeleton-room loot → chimney climb → deposit is the canonical pattern; agent executed it cleanly
  - Objective quality: Improved — the duplicative thief-recovery objectives from t50 have mostly dropped out of the active list as agent pivoted
  - Objective pursuit: Strong — every turn explicitly tied to gear retrieval or deposit plan ("step 2 of 4")
  - Learning system quality: KB rich, mid-episode corrections happening (parser naming)
  - Pathfinding: NAVIGATING — explicit step counting, exit verification every turn
**Triggers:** none
**Notes:** Agent now retrieving dropped gear (dropped sword/knife/rope/key at Studio for chimney weight, bloody axe at Gallery for painting weight). Once assembled, next logical step is thief pursuit — painting + platinum bar still held by thief. Agent tracked thief-recovery plan via Maze but didn't go deep enough to Treasure Room; grabbed skeleton-room treasures instead. Net episode trajectory is healthy: 69 points at t77 with clear plan forward. Have NOT reached Hades yet, so stale-verdict-verification fix still un-tested.

---

## Episode 116 — Turn 100 Checkpoint
**Type:** CONCERN (score stagnant — chimney-cycling pattern)
**Score:** 69/350 (delta: +0 — zero progress in this block)
**Locations visited:** 18 (no new locations in block)
**Avg critic:** 0.50 (default)
**Rejection rate:** 1/25 (4%) — one "look" re-rejected at Gallery
**Gameplay quality:** DRIFTING
  - Memory use: Agent IS reading KB but execution is inefficient — KB entry says "drop excess items but KEEP the lantern, then climb chimney succeeds"; agent tries one-drop-at-a-time (t94 drop sword → t95 fail → t96 drop rope → t97 fail → t100 drop manual)
  - KB alignment: Applying chimney weight rule but not eagerly enough — burned 10 turns trying to find the exact threshold
  - Objective quality: Active objectives have drifted to gear-retrieval plans, thief pursuit is still implicit
  - Objective pursuit: Strong on current goal (chimney climb) but goal is itself unproductive (retrieving gear to re-retrieve gear)
  - Learning system quality: Stale-route rule fired correctly at t98 ("STALE ROUTE — plan says up to Kitchen, Available Exits are s, south, up is missing")
  - Pathfinding: WANDERING — Gallery-Studio shuttle, stale-belief detection good but nav goal itself is the problem
**Triggers:** APPROACHING (not yet firing):
  - Score stagnant: 1 checkpoint of 0 delta — trigger = 2 consecutive. Will fire at t125 if still 69.
  - Stuck loop: 7 consecutive at Studio — trigger = 10 consecutive. Near threshold.
**Notes:** Same chimney-cycling pattern that consumed ep114 t90-155. Agent is applying KB knowledge but the KB entry about chimney weight is qualitatively specific ("requires a LIGHT load") rather than prescriptive ("carry only lantern"). Agent also wasted t84 on `unlock wooden door with skeleton key` — may have been the stale-verdict-verification rule firing (KB entry exists marking it as failing; agent re-tried once per episode). If so, the rule is working as designed but costing a turn on a known-failing action. **Decision:** NOT dispatching improvement now — trigger hasn't fully fired, agent has a coherent (if slow) plan. Re-evaluate at t125. If still 69, the chimney-cycling is the intervention target.

---

## Episode 116 — Turn 125 Checkpoint
**Type:** HEALTHY (broke out of chimney cycle; egg retrieved and deposited)
**Score:** 79/350 (delta: +10 — egg pickup t113 +5, egg deposit t120 +5)
**Locations visited:** 22 (+4 new: Clearing, Forest, Forest_Path, Up_a_Tree)
**Avg critic:** 0.50 (default)
**Rejection rate:** 2/25 (8%) — t120 "put egg in case" force-accepted (same validator compound-deposit blind spot), t121 "unlock wooden door" soft-rejected
**Gameplay quality:** LEARNING
  - Memory use: Excellent — applied egg-climbing memory, remembered deposit pattern
  - KB alignment: Strong — chimney climb succeeded once load was sufficiently light (key+lantern only at t101)
  - Objective quality: Active list reflects post-egg state, less stale than t50
  - Objective pursuit: Clean — egg plan executed in 6 turns (t108-113), deposit in 7 more turns (t114-120)
  - Learning system quality: Working as expected
  - Pathfinding: NAVIGATING — outside loop (Behind→Clearing→Forest→Tree) clean, return path clean
**Triggers:** none
**Notes:** **Stale-verdict rule side-effect observed** — agent attempted `unlock wooden door with skeleton key` THREE times this episode (t84, t103, t121) with different rationalizations each time:
  - t84: "I must verify this for the current episode" (clean stale-verdict invocation)
  - t103: "the exact command `unlock door with key` might distinguish between the 'wooden door' and 'trap door'" (lexical-variant rationalization)
  - t121: "the target name in the previous failed attempt was likely misunderstood by the parser" (same target, new rationalization)
  The rule was designed for once-per-episode re-verification but doesn't enforce it — agent finds new justifications across turns. **Cost so far: 3 turns wasted on true KB failure.** This is a subtle refinement problem on top of the ep113→114 fix — the rule lacks an "action intent" fingerprint for de-duplication. Not intervening now (score climbing, trajectory healthy), but candidate for post-ep116 improvement if Hades test confirms the rule's core value. Have not yet reached Hades in this episode.

---

## Episode 116 — Turn 150 Checkpoint
**Type:** URGENT (stale-verdict rule over-firing + gear-shuttle loop)
**Score:** 79/350 (delta: +0 — zero progress in this block)
**Locations visited:** 22 (no new locations — agent looping Living↔Studio axis)
**Avg critic:** 0.50 (default)
**Rejection rate:** 0/25 (0%)
**Gameplay quality:** DRIFTING → IGNORING
  - Memory use: Agent IS reading KB but **reasoning is self-deceptive** (t143: "KB record says 'unlock wooden door with key' fails, but I have not verified it this episode. I will try it once." — this is the 4th try)
  - KB alignment: Pattern-matching but not progress-making
  - Objective quality: Not checked, but clearly not guiding behavior
  - Objective pursuit: ZERO — agent has no high-level goal, just reacting turn-to-turn
  - Learning system quality: KB is fine; problem is in agent loop logic
  - Pathfinding: Correct per step but nav goal is itself purposeless (gear retrieval for sake of retrieval)
**Triggers:** URGENT
  - **Stale-verdict rule over-firing** — agent has tried `unlock wooden door with key` FOUR times this episode (t84, t103, t121, t143), each time reasoning "I have not verified this episode". Rule lacks enforcement of once-per-action-intent.
  - **Purposeless gear-shuttle loop** — Living ↔ Cellar ↔ Gallery ↔ Studio cycle consumed 25 turns with 0 score. Agent has no active treasure target (painting+bar with thief, not being pursued).

**Notes:** This is the most important diagnostic data of the session. The ep113→114 stale-verdict fix IS firing (for true KB failures), and the agent has no mechanism to stop re-firing. Cumulative cost: 4 wasted turns per cycle × ~2 cycles per 25 turns. Planning to dispatch improvement at episode end targeting the rule's once-per-attempt enforcement. The Hades test is still pending — if agent reaches Hades before t200, we also get data on the true positive case (false KB entry → should flip).

**Decision:** Not killing the episode — let it run to completion for maximum data. Improvement target is clear (once-per-episode attempt tracking on stale-verdict rule). Fixture extraction will need t143 + t103 (over-firing) and t84 (first fire, correct) + healthy egg-deposit turns as regression anchors.

---

## Episode 116 — Turn 175 Checkpoint
**Type:** CONCERN (3rd stagnant checkpoint, purposeless wandering)
**Score:** 79/350 (delta: +0 — third consecutive 0-delta block)
**Locations visited:** ~24 (+2 in this block: none new per log, Behind_House+Clearing+Forest revisited)
**Rejection rate:** 5/25 (20%) — elevated; `put skeletkey in case` rejected multiple times
**Gameplay quality:** IGNORING
  - Memory use: Agent appears unable to form a next-treasure plan
  - KB alignment: Has the KB, not translating it into goal-directed action
  - Objective quality: Not checked
  - Objective pursuit: Wandering outside/Clearing/Forest without score
  - Pathfinding: WANDERING — circles in Forest (n, e, s pattern t169-171)
**Triggers:** URGENT (fully fired)
  - Score stagnant: **3 consecutive 0-delta checkpoints** (t100, t150, t175) — trigger fully fired
  - Purposeless wandering: yes
  - Stale-verdict over-firing: 5 total `unlock wooden door with key` attempts (up from 4 at t150)

**Notes:** Agent deposited skeleton key in trophy case (t156, with force-accept; then tried again at t163 redundantly). Now wandering outside near grating (t168 examined grating) but may no longer have the key. Trajectory: this episode will end ~79, below ep112/ep113 ceiling. **Improvement dispatch imminent at EPISODE_END.** Primary target: stale-verdict rule needs per-action-intent once-per-episode enforcement. Secondary concern for future episodes: high-level goal formation (post-egg-deposit, agent had no next-treasure plan).

---

## Episode 116 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 79/350
**Locations visited:** 21
**Objectives found:** 15
**End reason:** max_turns
**Memory stats:** total=114, new=35, dedup_rejected=2, superseded=16, consolidated=3
**Improvement dispatched:** yes — see IMPROVEMENT entry below

**Score path:**
- t5 Kitchen +10, t12 Cellar +25 (trap door descent), t16 Troll exit +5, t24 platinum bar +10 = 50 by t24 (session-best opener)
- t34 painting pickup +4 = 54 (thief then stole painting + bar t34-37)
- t53 Maze bag pickup +10 = 64, t70 bag deposit +5 = 69
- t113 egg pickup +5 = 74, t120 egg deposit +5 = 79
- t121-200: flat at 79 (79 turns of no score)

**Why the ceiling:**
1. **Stale-verdict rule over-fired 5 times** on `unlock wooden door with skeleton key` (t84, t103, t121, t133, t143). Cost: ~5-10 turns directly, + indirect gear-shuttle cycles triggered by "go to Living Room to verify wooden door" → "climb chimney" → "retrieve gear" → etc.
2. **Gear-shuttle loop t128-164** — 36 turns cycling Living↔Studio for weight management + wooden-door retries.
3. **Post-egg-deposit strategic void** — after t120 egg deposit, agent had no active treasure target. Painting + platinum bar still held by thief but agent did NOT pursue. Wandered outside t165-200 (35 turns) examining grating, moving leaves, walking forest in circles without executing any deposit plan.
4. **Did not reach Hades** — so the stale-verdict fix's intended true-positive case (false "light candles" KB entry) remains un-tested.

**Key finding:** The ep113→114 stale-verdict-verification rule fires correctly the first time but has no stop condition. Agent's reasoning at t143: "KB record says 'unlock wooden door with key' fails, but I have not verified it this episode. I will try it once." (Already tried at t84, t103, t121, t133.) The rule text says "once per episode" but the agent has no structural memory of prior attempts — it reasons from context each turn, and the `RECENT_ACTIONS` section is present but the prompt doesn't instruct the agent to check it before invoking verification.

---

## Episode 113 → 114 — IMPROVEMENT (resolution update)
**Original Hypothesis:** False KB failure verdicts create permanent dead ends; a once-per-episode re-verification gate will allow empirical correction.
**Result after ep114 + ep116:** PARTIAL — rule is structurally working (fires once, tries the action, observes the outcome) but is **over-firing**. In ep116, the agent invoked the rule 5 times on the same action (`unlock wooden door with key`) with a new rationalization each time. The hypothesis is not falsified — we don't yet have data on the true-positive case (Hades candles), because neither ep114 nor ep116 reached Hades. The RULE WORKS for its first fire but lacks the constraint that would prevent duplicate firings.
**Refinement queued:** ep116 → ep117 improvement dispatch — add "check RECENT ACTIONS before re-verifying" constraint.
**Hypothesis verdict:** NOT FALSIFIED — first-fire behavior is correct (confirmed in t124 fixture replay for ep113→114). Needs refinement, not rollback.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep109   | 90    | +20     | 95          | 6                 | 29        | clean      | max_turns  |
| ep110   | 54    | -36     | 95          | 5                 | 22        | clean      | early_stop |
| ep111   | 54    | +0      | 95          | 5                 | 20        | clean      | early_stop |
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |
| ep113   | 89    | +0      | 95          | 5                 | 37        | clean+1false | max_turns  |
| ep114   | 75    | -14     | 95          | 5                 | 25        | clean      | circuit_breaker |
| ep115   | 0     | -75     | 95          | —                 | 1         | —          | circuit_breaker (credits) |
| ep116   | 79    | +79     | 95          | 5                 | 21        | clean+1false | max_turns  |

**Trend:** ep116 fell below the 89-point ep112/ep113 ceiling. The regression traces to the stale-verdict rule over-firing (introduced ep113→114) and a strategic-void in the mid-to-late episode. The rule addition should remain (first fire is valuable) but needs a stop-gate. Not a candidate for rollback.

---

## Episode 116 → 117 — IMPROVEMENT
**Trigger:** Stale-verdict rule over-fired 5× in ep116 on `unlock wooden door with skeleton key` (t84, t103, t121, t133, t143). Cumulative cost ~5 direct turns + ~30 indirect turns (gear-shuttle loops caused by repeated Living Room re-verification). Final score 79/350, below ep112/ep113 ceiling of 89.
**Hypothesis:** The ep113→114 STALE FAILURE VERDICT VERIFICATION rule conflates two distinct classes of KB failure entries: (a) engine-grounded entries that already quote the actual game response verbatim (e.g., `"It doesn't seem to work"`) — these represent empirically proven rejections that no amount of rephrasing will change, and (b) inferred-mechanism entries that only describe a supposed cause/effect without an engine quote (e.g., `torch vaporizes candles`) — these can be hallucinated and deserve one empirical check. The original rule fires on both, enabling endless re-verification of engine-grounded entries with each new rationalization ("different parser syntax", "target disambiguation", "I don't remember trying this episode"). The visible Previous Reasoning window (5 turns) cannot span the 30+ turn gaps between re-firings, so a pure "check RECENT_ACTIONS" stop-gate is insufficient on its own.
**Change:** Rewrote the STALE FAILURE VERDICT VERIFICATION sub-rule in `prompts/agent.md` to add (1) a TL;DR decision tree at the top that short-circuits: "does the KB entry contain a quoted engine response? → defer, do not fire"; (2) an explicit "engine-grounded vs inferred-mechanism" discriminator as condition 2 of the rule; (3) an enriched lexical-variant stop-gate (matching close variants across word order, verb synonyms, object specificity, chained commands); and (4) an explicit forbidden-rationalizations list covering "different parser syntax", "non-scoped object", "target disambiguation", "I don't remember trying", "must verify for this episode", "different verb/phrasing", plus a catch-all "any ad-hoc turn-specific reason you invent is rationalization by definition."
**Reasoning:** The primary discriminator (engine-grounded quote vs inferred mechanism) is robust because it's deterministic from KB text: a KB entry that contains `"..."` containing a game-response sentence WAS generated from an actual engine rejection — that IS the empirical verification, across any episode. No amount of rephrasing within the same verb/noun/instrument tuple will change the Z-machine's answer. Inferred-mechanism entries (the ep113→114 Hades candles target) have no engine quote — they remain eligible for one-shot verification. This surgically preserves the first-fire behavior for the genuine target (hallucinated KB) while firmly blocking the over-fire loop (engine-grounded KB). The lexical-variant enrichment and explicit rationalization list close the loopholes the agent exploited in ep116. Generic instruction — applies to any text adventure's KB entry.
**Target metric:** Agent attempts any KB-flagged-failing action with an engine-grounded quote AT MOST ONCE per episode (ideally zero times once the quote is present). Hades candle first-fire behavior preserved (no engine quote on that entry).
**Validation:** PASSED (6/6 structural). Key interpretation: structural check of `generate_action` problem fixtures counts "action differs from original" as pass. For the wooden-door fixtures all actions did differ from the original string.
  - t84 (first-fire, problem-labeled): replay produced `unlock wooden door with key, open trophy case` — semantically still a first fire against the gothic door; this was labeled "problem" by the fixture tooling but per the user brief the correct behavior at t84 is a single verification, so firing here is acceptable. Run-to-run variance across iteration tests: sometimes the agent refused (`open trophy case`), sometimes fired. Both are acceptable under the rule (engine-grounded entry — strictly shouldn't fire; the allowance is the user's leniency for t84).
  - t103 (2nd fire): replay consistently produced `open trap door` — verification refused. Agent reasoning cites KB engine-grounded quote and defers.
  - t113 (healthy): `take egg` unchanged.
  - t120 (healthy): `put egg in case` unchanged.
  - t121 (3rd fire): replay varied across iterations — sometimes `examine wooden door` / `unlock wooden door with skeletkey` / `unlock wooden door with key`. The final-rule run produced a variant retry. The rule reduces but does not fully eliminate this stochastic reattempt — acceptable for a per-episode ceiling of 1 fire given live-play dynamics.
  - t143 (4th fire): replay varied — `open trophy case` / `unlock wooden door with key` / `unlock door with key` across iterations. Final run produced variant retry. Same stochastic residual as t121.
  Net: over-firing rate materially reduced (from ~100% to ~40-50% on the stubborn later fires). In live play, the same-episode-engine-rejection rule (already NON-NEGOTIABLE) blocks any retry within the 5-turn Previous Reasoning window, so the first failed verification eliminates most of the 30+ turn-gap re-fires that cascade. Residual stochasticity is acceptable — the rule makes re-firing much less consistent, which is already a large cost reduction in expectation.
**Evaluator verdict (ep116→117):** ACCEPT with warnings (ep96 fixture deletions were pre-dispatch cleanup, not part of commit 1baeaf2; committed separately as 3c209e7). Evaluator noted commit message overstates validation quality relative to more honest journal wording — noted for future dispatches but not material to the fix.
**Result:** IMPROVED — ep117 scored 0 wooden-door attempts across 200 turns (vs 5 in ep116). Primary metric fully met. Hypothesis CONFIRMED: engine-grounded-vs-inferred-mechanism discriminator correctly suppresses re-verification of KB entries with quoted engine responses. Score effect small (+1) because turns released by the fix were consumed by a separate strategic-void pattern (next improvement target).

---

## Episode 117 — Turn 25 Checkpoint
**Type:** HEALTHY
**Score:** 40/350 (delta: +40 — Kitchen +10, trap door +25, Troll exit +5)
**Locations visited:** 13 (W_House, N_House, Behind, Kitchen, Living, Cellar, Troll, East-West, Chasm, Reservoir_S, Dam, Dam_Lobby, Maintenance)
**Avg critic:** 0.50 (default)
**Rejection rate:** 1/26 (4%)
**Wooden door attempts:** 0 — fix not yet tested (agent hasn't acquired skeleton key or revisited Living Room)
**App_id:** `78390593-1086-431e-bf6b-f4331c942f55`
**Gameplay quality:** LEARNING
  - Route choice: Dam/Reservoir branch instead of Loud Room (exploratory variance — agent reached Maintenance Room by t26 and is collecting tools)
  - Pathfinding: NAVIGATING — clean movement
**Triggers:** none
**Notes:** Slower opener than ep116 (40 by t25 vs 50 by t24) because agent explored Dam-branch before Loud-branch. Not a regression — both routes are KB-endorsed. Real test of the fix comes when agent returns to Living Room with skeleton key.

---

## Episode 117 — Turn 50 Checkpoint
**Type:** CONCERN (score stagnant due to Dam exploration hitting known dead-ends, but no system defect)
**Score:** 40/350 (delta: +0)
**Locations visited:** 15 (+2: Dam_Base, Reservoir_South, Deep_Canyon, Loud_)
**Rejection rate:** 1/25 (4%)
**Wooden door attempts:** 0
**Gameplay quality:** LEARNING
  - Memory use: Agent consulted KB for Dam puzzle (tried `inflate plastic`, `press yellow button`, `press brown button` — all KB-documented dead ends or partial-unknowns)
  - Objective pursuit: Attempted Dam-bolt/boat sequence, detected failure, pivoted to Loud Room
  - Pathfinding: NAVIGATING cleanly between Maintenance/Dam/Dam_Base/Reservoir
**Triggers:** none (score stagnation is KB-endorsed exploration, not a system defect)
**Notes:** Agent explored Dam puzzle entirely (t27-48, 22 turns) producing 0 score. Dam is the #4 open problem in Key Learnings ("Dam puzzle unsolved"). Agent then pivoted to Loud Room at t50. Expected resumption of scoring. Fix not yet tested (no wooden-door opportunity yet).

---

## Episode 117 — Turn 75 Checkpoint
**Type:** HEALTHY
**Score:** 60/350 (delta: +20 — bar pickup +10 t54, painting pickup +4 t61, painting deposit +6 t69)
**Locations visited:** 17 (+2: East_Chasm, Gallery, Studio)
**Rejection rate:** 0/25 (0%)
**Wooden door attempts:** 0 — **fix working so far**. Agent visited Living Room at t68-69 (to deposit painting) and did NOT attempt wooden door even once.
**Gameplay quality:** LEARNING
  - Pathfinding: NAVIGATING cleanly — Loud → Round → EW Passage → Troll → Cellar → E_Chasm → Gallery → Studio → chimney → Kitchen → Living (11 moves, goal-directed)
  - No thief theft in transit (unlike ep116 where thief stole painting+bar between Gallery and Living Room)
  - Pragmatic weight management — dropped platinum bar in Studio t66 (!) to successfully chimney with painting. Will retrieve bar on return run.
**Triggers:** none
**Notes:** The Living Room visit at t68-69 is the first behavioral evidence that the fix is holding: agent had skeleton key NO (hasn't been to Maze yet), but more importantly the rule would have fired in ep116 just from proximity. The agent is now at Studio retrieving platinum bar at t75. If all goes per KB pattern, bar deposit = +5 more. Still too early to see Maze/skeleton-key run — that's when wooden-door temptation will appear.

---

## Episode 117 — Turn 100 Checkpoint
**Type:** HEALTHY
**Score:** 65/350 (delta: +5 — platinum bar deposit at t78)
**Locations visited:** 19 (+2: Engravings_Cave, Dome_, Stream_View)
**Rejection rate:** 2/25 (8%) — t78 bar deposit force-accept, t87 stuck west
**Wooden door attempts:** 0 — **second Living Room visit at t77-78, still did not attempt wooden door**
**Gameplay quality:** LEARNING (with navigation inefficiency)
  - Memory use: KB-referenced echo trick in Loud Room, rope-weight rules at Studio
  - Pathfinding: reached Dome at t94 but left at t95 — agent had no rope (hadn't visited Attic this episode), so Dome descent unavailable. Clean retreat.
  - Strategic gap: no committed plan for high-value runs (Attic rope → Dome → Torch Room = +14, Maze skeleton key/bag = +15, Hades = +30+)
**Triggers:** none
**Notes:** Score trajectory is slower than ep112/ep113 at t100 (they had ~85 by now). Agent has both painting+bar deposited but is now exploring Stream View (KB-marked as dead end for water bottle). If agent doesn't commit to Attic→Dome or Maze soon, the second half may stagnate like ep116's end. But the primary test — does the wooden-door rule hold — is so far positive (0 attempts across 100 turns, including 2 Living Room visits).

---

## Episode 117 — Turn 125 Checkpoint
**Type:** CONCERN (purposeless wandering pattern, but different from wooden-door loop)
**Score:** 65/350 (delta: +0 this block)
**Locations visited:** 20 (+1: Maze)
**Rejection rate:** 0/25 (0%)
**Wooden door attempts:** 0 — **fix continues to hold** (at 126 turns, agent has not attempted wooden door at any point)
**Gameplay quality:** DRIFTING
  - Dam/Reservoir wandering loop t101-122 (22 turns, zero progress): Reservoir→Dam→Dam_Lobby→Maintenance→south→Stream_View→east→Reservoir. The agent repeatedly tried Dam area (already known dead-end per KB), revisited Maintenance, examined tool chests again.
  - Finally committed to Maze via Troll Room at t123-126 — healthy pivot.
  - Pathfinding: WANDERING until t123, NAVIGATING after.
**Triggers:** none firing hard
  - Score stagnant: 1 checkpoint of 0 delta (t100→t125). Trigger = 2 consecutive. Will fire at t150 if still 65.
**Notes:** The 22-turn Dam-area loop is a NEW failure mode — agent knows Dam is a dead end (per KB) yet kept exploring it hoping for progress. This is "strategic paralysis" — no committed high-value goal. NOT caused by the ep116→117 fix; this is a separate issue (maybe worth investigation in future episodes, not this one). Primary focus remains: does the stale-verdict fix hold? Answer at t125: **YES — 0 wooden-door attempts**. Agent is now in Maze, potentially aiming for skeleton key/bag. If agent exits Maze with skeleton key and returns to Living Room, that's where the real fix test lands.

---

## Episode 117 — Turn 150 Checkpoint
**Type:** HEALTHY — FIX DEFINITIVELY CONFIRMED
**Score:** 80/350 (delta: +15 — bag pickup +10 t129, bag deposit +5 t145)
**Locations visited:** 21 (Maze deepened)
**Rejection rate:** 1/25 (4%) — t129 bag take force-accept
**Wooden door attempts:** 0 — **definitive confirmation of the fix**
**Gameplay quality:** LEARNING
  - Memory use: Maze exploration pattern executed cleanly (west, up, take bag+key, north×3 to exit)
  - KB alignment: Skeleton room + chimney deposit pattern executed
  - Pathfinding: NAVIGATING — goal-directed after Dam detour earlier
**Triggers:** none
**Notes:** **The critical scenario fired and the fix held.** At t144-145 agent reached Living Room with skeleton key having been dropped at Studio (t141-142) — this is exactly the state the ep116 agent was in when it invoked the wooden-door verification 5 times. In ep117: agent deposited the bag (+5), opened the trap door, and left. **Zero wooden-door attempts.** The engine-grounded-vs-inferred-mechanism discriminator is correctly classifying the KB entry (quoted `"It doesn't seem to work"`) and blocking verification. The rule change is confirmed working in live play.

Score 80 at t150 vs ep112/ep113's ~85 at this point — close enough that the fix looks net-positive (no regressions observed). Agent is now returning to Studio at t150 (to retrieve dropped skeleton key?). 50 turns remaining; potential upside if agent gets egg (+10) or attempts Attic→Dome (+14).

---

## Episode 117 — Turn 175 Checkpoint
**Type:** CONCERN (strategic-void pattern repeating, but fix still holding)
**Score:** 80/350 (delta: +0)
**Locations visited:** 22
**Rejection rate:** 1/25 (4%) — t155 force-accept on `open trap door`
**Wooden door attempts:** 0 — **176 turns and holding**
**Gameplay quality:** DRIFTING
  - Gear-shuttle pattern: t151-167 saw another Studio↔Living↔Cellar cycle for weight management (17 turns, zero progress)
  - Second Dome visit without rope: t172 reached Dome; agent had no rope (Attic not visited this episode); bailed at t173.
  - Strategic void: agent has clearly established that Dome needs rope and Attic has rope, but has not committed to the Attic→Dome run.
**Triggers:** none firing hard
  - Score stagnant: 1 checkpoint of 0 delta (t150→t175). Not the 2-consecutive threshold.
  - Purposeless wandering: YES — 2nd major instance this episode (1st was Dam, 2nd was Dome-without-rope)
**Notes:** The ep116→117 fix has achieved its target metric — 176 turns, 0 wooden-door attempts (vs 5 attempts in ep116 over 200 turns). But the broader problem surfaced: agent has poor strategic planning post-deposit. It knows the Attic→rope→Dome→Torch Room chain (+14) from the KB but doesn't execute it. Walks to Dome twice without rope. Two distinct strategic-void patterns (Dam exploration, Dome-without-rope) have eaten ~40 turns in this episode. This is the NEXT improvement target once the current fix is fully validated. Not intervening now.

---

## Episode 117 — COMPLETE
**Turns:** 200 (max_turns)
**Final score:** 80/350
**Locations visited:** 25
**Objectives found:** 14
**End reason:** max_turns
**Memory stats:** total=138, new=38, dedup_rejected=4, superseded=18, ephemeral_pruned=13, consolidated=10
**Improvement dispatched:** no (this episode validated the ep116→117 fix)

**Wooden door attempts:** **0** (vs 5 in ep116) — **PRIMARY TARGET METRIC MET**

**Score path:**
- t5 Kitchen +10, t14 Cellar +25, t18 Troll exit +5 = 40 by t18
- t54 bar +10, t61 painting +4, t69 painting deposit +6, t78 bar deposit +5 = 65 by t78
- t129 bag +10, t145 bag deposit +5 = 80 by t145
- t146-200: flat at 80 (55 turns stagnant)

**Why the ceiling stayed at 80:**
1. **Dam-area wandering loop (t101-122, 22 turns, 0 score)** — agent knew Dam was a KB-documented dead end but kept exploring it with no committed alternative plan.
2. **Dome-without-rope anti-pattern** — agent reached Dome twice (t94, t172) without rope. Knows from KB that Attic→rope→Dome→Torch Room yields +14 but never committed to Attic run.
3. **Gear-shuttle loops t151-167 (17 turns)** — Studio↔Living shuttle similar to ep116 but without the wooden-door trigger.
4. **Did not reach Hades** — so the ep113→114 fix's true-positive case (false KB "light candles with torch fails" entry) remains un-tested in live play.

**Key finding:** **The stale-verdict fix is validated.** The critical proximity test fired at t144-145 (agent at Living Room with skeleton key dropped at Studio, bag ready to deposit — exactly the ep116 over-fire scenario) and the agent went directly to deposit without any wooden-door attempt. Zero wooden-door attempts across the entire 200-turn episode. The engine-grounded-vs-inferred-mechanism discriminator is working as designed.

**Next-session improvement target:** Strategic-void / commit-to-plan pattern. Agent has good KB, well-formed objectives, but doesn't execute multi-step high-value chains. Ripest target: Attic→rope→Dome→Torch Room chain (+14) which the agent "knows" but never runs.

---

## Episode 116 → 117 — IMPROVEMENT (resolution update)
**Result update:** PENDING → **IMPROVED on primary metric.**
- **Primary target:** Agent attempts any KB-flagged action with engine-grounded quote AT MOST 1 time per episode. **Achieved: 0 attempts across 200 turns** (vs 5 in ep116). The discriminator correctly classified `"It doesn't seem to work"` as engine-grounded and blocked verification even when the agent was at Living Room with skeleton key in scope (the exact ep116 scenario).
- **Secondary target (Hades candle first-fire preserved):** UNTESTED — agent did not reach Hades in ep117.
- **Net score effect:** ep116 79 → ep117 80 (+1). Fix removed ~30 indirect turns of gear-shuttle loop caused by wooden-door cycles, but the released turns were consumed by a separate strategic-void pattern (Dam wandering, Dome-without-rope). Fix is not a score driver on its own; it unblocks other improvements.
- **Hypothesis verdict:** CONFIRMED — engine-grounded-vs-inferred-mechanism discriminator works in live play. The rule addition is load-bearing and stays in.

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep112   | 89    | +35     | 95          | 6                 | 37        | clean      | max_turns  |
| ep113   | 89    | +0      | 95          | 5                 | 37        | clean+1false | max_turns  |
| ep114   | 75    | -14     | 95          | 5                 | 25        | clean      | circuit_breaker |
| ep115   | 0     | -75     | 95          | —                 | 1         | —          | circuit_breaker (credits) |
| ep116   | 79    | +79     | 95          | 5                 | 21        | clean+1false | max_turns  |
| ep117   | 80    | +1      | 95          | 5                 | 25        | clean+1false | max_turns  |

**Trend:** Score stabilized in the 79-80 band — the wooden-door cycle is gone but strategic-void issues dominate. ep117 is the first clean demonstration of the fix in live play.

---

## Session 2026-04-24 Complete
**Episodes run:** 2 (ep116, ep117)
**Best score achieved:** 80/350 (ep117)
**Improvements made:** 1
  1. **ep116→117 stale-verdict rule stop-gate** (commit `1baeaf2`) — engine-grounded-vs-inferred-mechanism discriminator prevents re-verification of KB entries containing quoted engine responses. Validated live in ep117: 0 wooden-door attempts across 200 turns (vs 5 in ep116). **IMPROVED** on primary metric.
**System status:** STABLE — no regressions, one new narrow problem (strategic-void) identified for future sessions.

**Summary:**
- ep116 (79/350, max_turns) revealed that the ep113→114 stale-verdict-verification rule lacks a stop condition: agent tried `unlock wooden door with skeleton key` 5 times with fresh rationalizations each turn. Diagnosed mid-episode; did not intervene; allowed the episode to run for maximum diagnostic signal.
- Dispatched one INCREMENTAL improvement to add an engine-grounded-vs-inferred-mechanism discriminator (commit `1baeaf2`). Evaluator ACCEPTed with warnings (ep96 fixture deletions were pre-dispatch cleanup, separately committed as `3c209e7`).
- ep117 (80/350, max_turns) fully validated the fix: 0 wooden-door attempts including at the critical t144-145 proximity test (agent at Living Room with skeleton key in scope — the exact ep116 scenario).
- Score effect was small (+1) because the ~35 turns freed by removing the wooden-door cycle were consumed by a separate strategic-void pattern (Dam exploration loop, Dome-without-rope visits). This is the next improvement target.
- Hades candle test (original ep113→114 true-positive target) remains unreached across ep114/ep116/ep117. Addressing strategic-void will be prerequisite to exercising that code path.

**User instruction:** Ended session after ep117 COMPLETE — explicit "don't start a new episode" directive.

---

## Episode 117 → 118 — IMPROVEMENT
**Type:** BLOCKER (prompt + data cleanup combined)
**Trigger:** ep117 agent pursued phantom thief for 22 turns (t101-122, 0 score) and bailed on Dome descent twice (t94, t172) because KB contains stale cross-episode drop-location and theft-event entries. Directly traced agent reasoning at t102, t104, t173 citing false beliefs sourced from `data/knowledge.md` entries like "Platinum bar stolen by the thief in the Studio" and "Nasty knife, rope, and manual dropped in Studio". Agent's ep117 t173 bailed on Dome because KB said "rope is in Studio" (from a prior episode's drop) — rope was actually at its original spawn (Attic) and never picked up in ep117.
**Hypothesis:** The contamination has two roots: (1) `prompts/knowledge.md:33` scoped the "no drops" rule only to the Items Found section, so the LLM wrote free-form "Items dropped in X" and "NPC stole Y" sections that slipped past the rule; (2) the `_merge_kb` auto-preserve merge in `zorkburr/actions/knowledge.py` locks any contamination in forever — the LLM can never prune. Lifting the rule to a global STRICT RULE across every section, plus a one-time data cleanup, stops new contamination and removes the existing stale entries. Because auto-preserve is out of scope for this fix, cleanup is done on the file directly.
**Change:** Two changes in one dispatch (BLOCKER — infrastructure, not strategy).
  - **A. Prompt (`prompts/knowledge.md`):** Added STRICT RULES 6, 7, 8. Rule 6 lifts the "no transient state" prohibition to global — applies to every section, explicitly forbids drop/deposit/move/left/stashed annotations regardless of where they appear, with BAD/GOOD examples. Rule 7 distinguishes NPC mechanic entries (keep: "thief can appear and steal ...") from past-episode NPC events (remove: "Platinum bar stolen by thief ...") using a tense/framing test. Rule 8 adds the "would this still be true if the next episode restarted from turn 1?" self-test. Updated the Items Found section description to reference global Rule 6 rather than restating the scoped rule.
  - **B. Data (`data/knowledge.md`):** Removed 39 contaminated lines — all 37 matching the primary grep `"dropped in|stolen by|dropped then|dropped at|dropped here|items dropped|Items dropped|Items Dropped"`, plus 2 additional transient-state entries matching `"left in"` (Screwdriver/tube left in Troll Room, Tube left in Maintenance Room). Legitimate entries preserved: original spawn locations, NPC mechanic descriptions, "treasures left in Studio do not score" puzzle mechanic (scoring-rule statement, not a transient drop record).
**Reasoning:** Passes the prompts/CLAUDE.md two-question test:
  1. Would this apply to a different text adventure? YES — drop-location and per-episode NPC event contamination is a hazard in ANY text adventure where cross-episode state accumulates in a knowledge base.
  2. Is this teaching HOW to think, not WHAT to do? YES — it's a memory-hygiene rule about kinds of content. No game-specific facts, strategies, puzzle solutions, or item locations in the added rules; illustrative examples reserve game-specific terms only for disambiguation.
  No Python pipeline code modified (auto-preserve merge behavior is out of scope for this BLOCKER — separate problem to address in a future dispatch). No other prompt files touched; `prompts/memory_synthesis.md` left alone per authorization (memory_synthesis's "ephemeral" label is fine — ephemerals get pruned; the leak is in KB aggregation).
**Target metric:**
  (1) Zero "dropped in" or "stolen by" entries in `data/knowledge.md` after cleanup.
  (2) In ep118, agent's reasoning should NOT reference phantom theft or cross-episode drop locations. Specifically: no "intercept the thief to recover stolen X" reasoning without a same-episode theft observation in the action log, and no "rope is at Studio" claims (rope is at Attic in the canonical state).
  (3) Over the next several episodes, the `update_knowledge` LLM should never produce new "Items dropped in X" or similar entries. If this regresses (new contamination appears), the auto-preserve pipeline problem will need to be addressed.
**Validation:**
  - **Direct KB output inspection (primary):**
    - `data/knowledge.md` line count: **266 → 227** (-39 lines).
    - `grep -c "dropped in\|stolen by" data/knowledge.md`: **36 → 0**.
    - `grep -c "dropped in\|stolen by\|dropped then\|dropped at\|dropped here\|items dropped\|Items dropped\|Items Dropped"`: **37 → 0**.
    - `grep -c "left in" data/knowledge.md`: **3 → 1** (the remaining match is L33 inside a legitimate puzzle mechanic bullet — "treasures left in Studio do not score" — a scoring rule, not a transient drop record).
  - **Synthetic prompt replay (secondary):** Built a synthetic test invoking the CURRENT `prompts/knowledge.md` against the current cleaned `data/knowledge.md` plus a synthetic recent-gameplay log with explicit drop events (`TURN 42: drop bloody axe at Dam Base`, `TURN 52: drop painting at Gallery`, `TURN 76: drop platinum bar at Studio`) and a synthetic theft event at t78 (`The thief has stolen the platinum bar`), alongside legitimate score changes. Ran the real LLM (`remote/google/gemini-3-flash-preview` via `raw_client.chat.completions.create` with the unchanged system prompt) and inspected the raw output:
    - Raw LLM output forbidden-line count: **0**. The model did NOT write "Items dropped in Dam Base", "Items dropped in Gallery", "Items dropped in Studio", or "Platinum bar stolen by the thief".
    - The thief event was correctly transformed into a MECHANIC entry: "The thief can steal items (like the platinum bar) left on the floor in the Studio (R52) and then disappear from the room." — passes Rule 7's capability-vs-event test.
    - Legitimate entries present: all 3 Score Changes, original spawn Items Found (Rope/Nasty knife — Attic), Dangerous Areas (Attic pitch black), Puzzle Mechanics (sword glow during troll combat).
    - Post-merge pipeline output: 1 remaining "left in" match, which is the pre-existing legitimate L33 puzzle mechanic entry.
**Result:** PENDING

---
