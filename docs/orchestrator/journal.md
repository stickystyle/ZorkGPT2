# ZorkBurr Orchestrator Journal

Started: 2026-03-30

---

## Episode 6 — COMPLETE (90 turns, crashed)
**Turns:** 90 (crashed turn 91 — qwen/qwen3-14b returned `{}` empty JSON, AgentResponse validation failure; 16880 prompt tokens at crash point)
**Final score:** 15/350
**Locations visited:** 10 unique (West_House, North_House, Behind_House, Forest, Forest_Path, Clearing, Up_a_Tree, Kitchen, Living_Room, Attic)
**Objectives found:** unknown
**End reason:** LLM crash (empty response) — not max_turns, not death
**Improvement dispatched:** yes
**Notes:** Best score to date (15). Score stalled for last 50 turns. Agent spent turns 81-90 in futile grue combat (Attic, dark area — grue unbeatable without light). Multi-variation same-target failure rule didn't catch grue loop because game responses were varied, not "nothing happens". Rejection rate consistently 40% across all blocks — structural artifact from object tree validator rejecting architectural-feature interactions.

---

## Episode 6 → 7 — IMPROVEMENT (Futile Combat / Exploration Escape)
**Trigger:** Agent spent 10+ turns in futile combat (Attic grue, turns 81-90) with score=15 throughout. After retreating, oscillated Kitchen↔Attic instead of exploring new areas. Multi-variation same-target failure rule doesn't cover this because grue combat returns varied responses.
**Evidence:** Turns 81-90 all show Attic + score=15 + grue attack variants. Agent returned to Attic on turn 89 despite just retreating on turn 88.
**Change:** Subagent added two rules to critic.md: (1) Futile Combat Detection — penalizes combat after 3+ turns with no score/inventory change; (2) Anti-Oscillation After Retreat — penalizes moving back to a location just left.
**Target metric:** Agent should leave dangerous/unproductive areas within 3 turns (not 10+). Score should progress past 15 in first 75 turns.
**Result:** DEGRADED — ep07 turn-25 checkpoint: rejection rate 68% (up from ep06's 40%), avg critic 0.24 (down from 0.54). Root cause: Anti-Oscillation After Retreat rule fires on ALL location revisits, not just combat retreats. Normal Forest_Path↔Clearing exploration got penalized as "retreat oscillation." Reverted Anti-Oscillation After Retreat rule. Futile Combat Detection rule retained (correct logic, narrower scope). Episode killed.

---

## Episode 8 — Turn 50 Checkpoint
**Type:** URGENT — fixation loop, high rejection rate
**Score:** 5/350 (delta: +5 from turn 25 — scored egg between turns 25-50, then stalled)
**Locations visited (turns 26-50):** 3 unique (Up_a_Tree, Clearing, Forest_Path) — severely narrowed
**Avg critic score:** 0.38 (below 0.5)
**Rejection rate:** 14/25 (56%) — URGENT
**Triggers:** Avg critic < 0.5, rejection rate > 30%, stuck at Clearing 15+ consecutive turns
**Root cause (from Burr trace):** Critic IS correctly rejecting grating actions (-1.0). But agent hits max_rejections=3 (force-executes) then RE-PROPOSES grating on the NEXT turn. The agent's within-turn rejection recovery works, but it doesn't check CROSS-TURN history to notice "I've tried this target 5+ times and failed." Episode killed. Dispatching improvement.

---

## Episode 8 — Turn 25 Checkpoint
**Type:** CONCERN (borderline — single trigger, recovering from ep07 regression)
**Score:** 0/350 at turn 25 (delta: 0 — first checkpoint); NOTABLE: scored 5 pts at turn 28 (agent took egg at Up_a_Tree)
**Locations visited (turns 1-25):** 6 unique (West_House, North_House, Forest_Path, Forest, Clearing, Up_a_Tree) — broad exploration
**Avg critic score:** 0.53 — ABOVE 0.5 threshold (first time since ep06 turn 25)
**Rejection rate:** 8/25 (32%) — barely above 30%, vs ep07's 68% — major recovery
**Triggers:** Rejection rate barely above threshold (32%). No other triggers.
**Notes:** Anti-oscillation revert confirmed working — rejection rate dropped from 68% to 32%. Futile combat detection rule retained. Agent reached tree quickly (egg at turn 28 vs ep06 turn ~47). Not dispatching improvement; monitoring to turn 50.

---

## Episode 9 — Turn 50 Checkpoint
**Type:** URGENT — score stagnant, multiple triggers
**Score:** 0/350 (delta: 0 from turn 25 — stagnant across 2 consecutive checkpoints)
**Locations visited (turns 26-50):** 4 unique (North_House, Forest_Path, Forest, Clearing) — never reached Up_a_Tree or house interior
**Avg critic score:** 0.42 (below 0.5)
**Rejection rate:** 11/25 (44%) — above 30%
**Triggers:** Score stagnant (0 delta, 2 checkpoints), avg critic < 0.5, rejection rate > 30%
**Root cause:** Agent tried "examine tree" at Forest_Path (turn 34, rejected), then anti-oscillation rule prevented return to Forest_Path (visited 2 turns ago, "nothing changed" — but agent HAD a different strategy: climb vs examine). Agent stayed in Forest/Clearing area all 50 turns. Score=0 (vs ep06's 10 pts by turn 25). Episode killed. Dispatching improvement.

---

## Episode 10 — Turn 50 Checkpoint
**Type:** URGENT — score stagnant, local area trap
**Score:** 5/350 (delta: 0 from turn 25 — scored at turn 12, nothing since)
**Locations visited (turns 26-50):** 3 unique (Forest_Path, Clearing, Up_a_Tree) — severely narrowed from turn-25's 5 locations
**Avg critic score:** 0.35 (below 0.5)
**Rejection rate:** 10/25 (40%) — above 30%
**Triggers:** Score stagnant (delta=0), avg critic < 0.5, rejection rate > 30%
**Root cause:** "New strategy exception" to anti-oscillation caused OVERUSE — agent kept returning to Up_a_Tree and Clearing with marginally different strategies. Up_a_Tree is depleted (egg taken at turn 12), but agent kept climbing back. Agent never navigated back to West_House or south/east areas in the second 25 turns. Episode killed.

---

## Episode 11 — Turn 50 Checkpoint
**Type:** URGENT — score stagnant 2 consecutive checkpoints
**Score:** 0/350 (delta: 0 from turn 25 — 2 consecutive stagnant checkpoints)
**Locations visited (turns 26-50):** 4 unique (Forest, Clearing, South_House, Behind_House) — new: South_House and Behind_House found!
**Avg critic score:** 0.52 (recovered from turn-25's 0.27 — HEALTHY)
**Rejection rate:** 11/25 (44%) — above 30%
**Triggers:** Score stagnant × 2 checkpoints, rejection rate > 30%
**Root cause:** Agent at Behind_House (turns 31-50) but fixated on "leaflet + window" combinations (turns 42-50: "use leaflet window", "insert leaflet in window", "push leaflet into window"). Never tried simplest verb: "open window". Cross-turn stuck detection doesn't block window fixation because responses vary ("The window is closed", "You can't insert that"). Episode killed.
**Positive finding:** Local area trap detection IS working — agent found South_House and Behind_House. Just needs to actually OPEN the window.

---

## Episode 11 → 12 — IMPROVEMENT (Simple Verbs First for Structural Features)
**Trigger:** Score stagnant at 0 for 50 turns. Agent at Behind_House but can't open window.
**Root cause:** Agent tried 5+ complex "leaflet + window" combinations without ever trying "open window". Agent over-complicates structural interactions by thinking inventory items are required.
**Change:** Add rule to agent prompt: "When you encounter a closed door, window, hatch, or openable structural feature, the FIRST interaction is ALWAYS 'open [target]'. Do not use inventory items with structural features until 'open' has been tried and failed. Simple verbs first."
**Target metric:** Agent should open the window and enter the house by turn 25 in ep12. Score should be > 0 by turn 25.
**Result:** PENDING

---

## Episode 11 — Turn 25 Checkpoint
**Type:** CONCERN — metrics degraded vs ep10, rule interaction problem
**Score:** 0/350 (delta: 0 — first checkpoint; agent didn't climb tree)
**Locations visited (turns 1-25):** 6 unique (West_House, North_House, Forest_Path, Forest, Clearing, CanyView) — new CanyView found
**Avg critic score:** 0.27 — REGRESSION (vs ep10's 0.62, worst since ep07 regression)
**Rejection rate:** 13/25 (52%) — REGRESSION (vs ep10's 12%)
**Triggers:** Avg critic < 0.5, rejection rate > 30%
**Root cause:** Rule stack conflict — agent tried "examine tree/branches" (failing object tree validator) multiple times, cross-turn stuck detection + depleted location rules then pushed agent AWAY from Forest_Path before it tried "climb tree". Local area trap detection fired correctly (CanyView found) but no scoring there. vs ep10: agent climbed tree at turn 11, scored 5 pts. Not dispatching yet — monitoring to turn 50 to see if CanyView exploration yields scoring.

---

## Episode 10 → 11 — IMPROVEMENT (Depleted Location Priority + Exploration Breadth)
**Trigger:** Score stagnant at 5 for 38 consecutive turns. Agent trapped in 3-location loop.
**Root cause:** Agent repeatedly revisits "interesting" locations (tree, clearing) even after fully depleting them (egg taken). No mechanism to flag a location as depleted and deprioritize it.
**Change:** Add DEPLETED LOCATION and EXPLORATION BREADTH rules to agent prompt: (1) After collecting all available items from a location, mark it as "depleted" in thinking and reduce visit priority. (2) If you have visited the same 3-4 locations for 10+ turns with no score, you are in a local area trap — prioritize exits you have NOT tried from any recently-visited location.
**Target metric:** Agent should visit 6+ unique locations by turn 50, score >5 by turn 50.
**Result:** MIXED — ep11 visited 8 unique locations (6 by turn 25, 4 more by turn 50 including South_House and Behind_House). Exploration breadth IMPROVED. But avg critic at turn 25 degraded to 0.27 (rule stack conflicts preventing tree climb). Score stayed 0 for 50 turns despite reaching Behind_House. Local area trap detection working; window-entry failure is a separate issue addressed in ep11→12.

---

## Episode 10 — Turn 25 Checkpoint
**Type:** HEALTHY — best turn-25 performance ever across all metrics
**Score:** 5/350 (delta: +5 — FIRST TIME scoring by turn 25; egg taken at turn 12)
**Locations visited (turns 1-25):** 5 unique (West_House, North_House, Forest_Path, Clearing, Up_a_Tree) — Up_a_Tree included for first time in a turn-25 checkpoint
**Avg critic score:** 0.62 — HIGHEST EVER at turn 25
**Rejection rate:** 3/25 (12%) — LOWEST EVER
**Triggers:** None — all metrics healthy
**Notes:** New strategy exception to anti-oscillation is confirmed working. Agent reached tree at turn 11 (vs ep09 never in 50 turns). Took egg at turn 12 with no egg-nest loop. Agent now exploring Forest_Path/North_House area. Not yet in house interior — monitoring to turn 50.

---

## Episode 9 → 10 — IMPROVEMENT (Anti-Oscillation Rule Exception for New Strategy)
**Trigger:** Score stagnant 0 across 50 turns. Agent never climbed tree or entered house.
**Root cause:** Anti-oscillation rule prevents revisiting a location "if nothing has changed." But having a DIFFERENT ACTION STRATEGY counts as meaningful change — the agent should be allowed to return to a location if it has a new approach to try. Rule has no "new strategy" exception.
**Change:** Add exception to the anti-oscillation rule in agent.md: "Exception: if you identified a different verb or approach to try at that location (different from prior attempts), revisiting is appropriate and NOT anti-oscillation."
**Target metric:** Agent should reach Up_a_Tree and/or house interior (Kitchen/Living_Room) by turn 25 in ep10. Score should be >0 by turn 25.
**Result:** PENDING

---

## Episode 9 — Turn 25 Checkpoint
**Type:** HEALTHY — best turn-25 metrics ever
**Score:** 0/350 (delta: 0 — first checkpoint; no tree/house score yet)
**Locations visited (turns 1-25):** 5 unique (West_House, North_House, Forest_Path, Forest, Clearing) — broad exploration
**Avg critic score:** 0.52 — ABOVE threshold (HEALTHY)
**Rejection rate:** 6/25 (24%) — BELOW 30% threshold (HEALTHY, best ever)
**Triggers:** None — first checkpoint with BOTH metrics healthy simultaneously
**Notes:** Cross-turn stuck detection rule working — no grating fixation observed. Agent exploring freely. Rejection rate down from ep08's 32% at turn 25. Monitoring to turn 50.

---

## Episode 8 → 9 — IMPROVEMENT (Cross-Turn Stuck Pattern Recognition)
**Trigger:** Agent stuck at Clearing turns 30-55 (15+ consecutive turns), score=5, 56% rejection rate, repeatedly proposing grating interactions despite 3 rejections per turn.
**Root cause:** The critic correctly penalizes grating (-1.0) within each turn. But after force-execution hits max_rejections=3, the agent doesn't log the failure as "abandoned" — it re-proposes the same target NEXT TURN because it only tracks within-turn rejections, not cross-turn cumulative failures.
**Change:** Add CROSS-TURN STUCK PATTERN RECOGNITION section to agent prompt: before proposing any action, review recent_actions for the current location. If the same target (object or puzzle) has been proposed and rejected/failed 3+ times across different turns, do NOT propose it again until a major state change occurs (new item acquired, new location discovered). Instead, prioritize exploring completely new areas.
**Target metric:** Agent should not propose the same failed target more than 3 turns in a row. Score should progress past 5 by turn 50 in ep09.
**Result:** PENDING

---

## Episode 7 — Turn 25 Checkpoint (KILLED — regression)
**Type:** URGENT — regression from ep06→7 improvement
**Score:** 0/350 (delta: 0 — first checkpoint)
**Locations visited (last 25):** 4 unique (West_House, North_House, Forest_Path, Clearing)
**Avg critic score:** 0.24 (DEGRADED — ep06 was 0.54 at turn 25)
**Rejection rate:** 17/25 (68%) — WORST EVER (ep01 was 52%)
**Triggers:** Rejection rate >> 30%, avg critic << 0.5, both URGENT
**Root cause:** Anti-Oscillation After Retreat rule in critic.md treats ALL movement back to a recently-visited location as "retreat oscillation." Forest_Path↔Clearing is normal exploration, not retreat. Rule reverted. Futile Combat Detection retained.
**Notes:** Episode killed. Starting ep08 with reverted critic and retained futile combat rule.

---

---

## Pre-Episode — Suspicious Session Investigation
**Session:** 71c9ffa2-d535-4b13-ab77-e0968406ea97
**Type:** URGENT — LLM error pile-up (100% failure rate)
**Finding:** Previous run had 65/65 turns with LLM 404 errors. Error: "No endpoints found that support the provided 'tool_choice' value." Model qwen/qwen3-14b on OpenRouter did not support the tool_choice parameter Instructor uses for structured output. Every agent and critic call failed; agent fell back to "look" every turn; critic auto-accepted at score 0.5. Score stuck at 0 for all 65 turns. No locations explored. Session was still in-flight when this orchestrator session started.
**Resolution:** Current ep01 (session 1b0f4646) IS working — turns 1-3 show real actions (examine mailbox, open mailbox, take leaflet with critic=0.70), confirming the model now supports tool_choice on OpenRouter. No code changes needed; the issue was transient OpenRouter endpoint availability.
**Notes:** Add a startup health-check that detects consecutive LLM errors early (e.g., abort after 3 consecutive fallback "look" actions) to prevent silent failure loops in the future.

---

## Episode 4 — Turn 75 Checkpoint
**Type:** URGENT — score stagnant, high rejection rate, same-target failure loop
**Score:** 5/350 (delta: 0 from turn 50 — stagnant)
**Locations visited (last 25):** Up_a_Tree, Forest_Path, Clearing — only 3 (severely stuck)
**Avg critic score:** 0.21 (very low)
**Rejection rate:** 14/25 (56%) — URGENT
**Triggers:** Score stagnant (0 delta), avg critic < 0.5 (0.21), rejection rate > 30% (56%), agent stuck in same-target failure loop (20+ turns trying egg+nest variations)
**Notes:** Episode killed at turn 84. Dispatching improvement to address same-target failure pattern in critic.

---

## Episode 5 — Partial (38 turns, killed early to fix extractor)
**Score:** 5/350 at turn 35 (faster than ep04 — turn 35 vs turn 47)
**Key observations:**
- Agent climbed tree and took egg on turn 35 with 0 rejections (critic=0.90)
- NO egg-nest loop after scoring! Agent moved down immediately (turn 36). Critic improvement working.
- Grating loop: only 11 turns (turns 21-31) vs 25+ turns for nest in ep04. Improvement confirmed.
- Episode killed at turn 38 — extractor bug (qwen/qwen3-14b repetition) making each turn take 3-4 minutes. Not viable for rapid RL iteration.
**Critic improvement result:** IMPROVED — same-target failure rule working. Egg-nest loop eliminated.

## Episode 6 — Turn 75 Checkpoint
**Type:** CONCERN — rejection rate consistently 40%, avg critic 0.30 in third block
**Score:** 15/350 (delta: +5 from turn 50 — score IS progressing)
**Locations visited (last 25):** Behind_House, North_House, Forest_Path, Up_a_Tree, Kitchen, Attic — 6 unique
**Avg critic score:** 0.30 (low — skewed by -1.0 object tree failures: "descend staircase", "look through window", "look through small window", "go east from Behind_House", "look in Attic")
**Rejection rate:** 10/25 (40%) — consistently 40% across all 3 blocks
**Triggers:** Low avg critic 0.30 < 0.5. But score is progressing (+5 this block). NOT dispatching.
**Notes:** Agent found jeweled egg (turn 62, efficiently), glass bottle (turn 68, critic=1.00), discovered Attic (turn 72). The 40% rejection rate and low avg critic are structural artifacts from the object tree validator rejecting directional/interaction commands. Score progressed 10→15. Monitoring to completion.

---

## Episode 6 — Turn 50 Checkpoint
**Type:** CONCERN — score stagnant 10→10, rejection rate 40%
**Score:** 10/350 (delta: 0 from turn 25)
**Locations visited (last 25):** Kitchen, Living_Room, Behind_House — 3 unique (narrowed to house interior)
**Avg critic score:** 0.44
**Rejection rate:** 10/25 (40%) — consistent
**Triggers:** Score stagnant (0 delta), avg critic < 0.5, rejection rate > 30%
**Notes:** Agent exploring house interior (Kitchen/Living) — found elvish sword, took sack. Not yet depositing treasures in trophy case. Score hasn't increased despite exploration. Continuing to monitor.

---

## Episode 6 — Turn 25 Checkpoint
**Type:** CONCERN — rejection rate 40% (above 30% threshold), but strong progress
**Score:** 10/350 (delta: +10 — BEST EVER, achieved in just 21 turns)
**Locations visited:** 8 unique (West_House, North_House, Forest_Path, Clearing, Forest, Behind_House, Kitchen, Living_Room) — broadest exploration yet
**Avg critic score:** 0.54 — FIRST TIME above 0.5 threshold
**Rejection rate:** 10/25 (40%) — above threshold but agent IS scoring/progressing
**Triggers:** Rejection rate > 30% (barely — 40%). BUT no other triggers fire. Score is strong.
**Notes:** Llama extractor working (no errors, turns ~20-30s each vs 3-4 min with qwen). Agent entered the house on turn 21 via kitchen window, scored 10 points. Found trophy case at Living_Room (turn 24). This is the system's best performance. The 40% rejection rate may be acceptable given strong score progress. Will monitor to turn 50 before deciding on improvement dispatch.

---

## Episode 5 → 6 — IMPROVEMENT (Extractor Model Fix)
**Trigger:** qwen/qwen3-14b extractor repetition bug causing each extract_info call to fail with ~6K wasted tokens × 3 retries = 3-4 minutes per turn. Episodes take 5-6 hours to run 100 turns. Cannot iterate the RL loop meaningfully.
**Change:** Changing `extractor_model` in pyproject.toml to `meta-llama/llama-3.1-8b-instruct` — valid OpenRouter model, proven reliable for JSON extraction, $0.00000002/token.
**Target metric:** Extract_info calls should complete in <5 seconds with valid JSON. Episode turns should complete in <60 seconds each.
**Result:** IMPROVED — ep06 turns completed in 20-30s each (vs 3-4 min). No extractor errors in 90 turns. Target met.

---

## Episode 4 → 5 — IMPROVEMENT
**Trigger:** Score stagnant (5→5, 0 delta turns 50-75), avg critic 0.21, rejection rate 56%
**Root cause (from Burr trace):** Agent stuck in Up_a_Tree turns 57-80 trying 20+ variations of "put/use/drop jewel-encrusted egg in nest" (same hard-failure outcome each time). The critic's anti-repetition rule only catches EXACT string repetition. "use egg on nest" vs "put egg in nest" vs "drop egg in nest" are all different strings, so the critic keeps approving them. But the game gives the same hard-failure response every time.
**Change:** Improve critic prompt to add same-TARGET same-OUTCOME penalization: when recent action history shows 2+ different actions on the SAME OBJECT that all produced the same "nothing happens" / "I don't understand" / failed responses, new actions targeting that same object should score negatively (-0.5 to -0.8) — treat this as a multi-variation hard failure pattern, not systematic experimentation.
**Target metric:** Score delta > 0 between turns 25-50 AND no more than 3 consecutive same-object failed variations before switching to a different target/approach.
**Result:** IMPROVED — ep05 confirmed: egg-nest loop eliminated (0 rejections on tree climb, agent moved down immediately after scoring). ep06 showed faster initial progress (10 pts by turn 21). Rule working for hard-failure patterns. Combat loop against grue still bypasses rule (varied responses, not "nothing happens").

---

## Episode 4 — Turn 50 Checkpoint
**Type:** HEALTHY — first score achieved, rejection rate below threshold
**Score:** 5/350 (delta: +5 from turn 25 — first points scored in session!)
**Locations visited (last 25):** 3 unique (Clearing, Forest_Path, Up_a_Tree — focused tree puzzle)
**Avg critic score:** 0.45 (improved from 0.32 in first half)
**Rejection rate:** 7/25 (28%) — BELOW 30% threshold
**Triggers:** None — all triggers cleared
**Notes:** Agent climbed tree at Forest_Path on turn 46 (after 20 turns of oscillating between Forest_Path/Clearing), reached Up_a_Tree, took jeweled egg for 5 points. Rejection recovery protocol + critic movement fix are working. System is progressing. Agent needs to explore the house area (West_House, South_House, Behind_House) where more scoring opportunities exist.

---

## Episode 4 — Turn 25 Checkpoint
**Type:** CONCERN — avg critic below 0.5, rejection rate slightly above 30%
**Score:** 0/350 (delta: 0 — first checkpoint, no prior)
**Locations visited:** 5 unique (West_House, North_House, Forest_Path, Clearing, Forest)
**Avg critic score:** 0.32
**Rejection rate:** 8/25 (32%)
**Triggers:**
- Low avg critic: 0.32 < 0.5 (skewed by 3 object-tree -1.0 failures)
- Rejection rate barely above threshold (32% vs 30% limit)
**Notes:** Massive improvement over ep03. Agent left West_House on turn 7 — critic movement fix working. The remaining -1.0 scores are from object tree validator (not exits issue). The 32% rejection rate is borderline; will continue monitoring to 50 turns before considering another improvement dispatch.

---

## Episode 3 → 4 — IMPROVEMENT (Critic Movement + Extractor Revert)
**Trigger:** ep03 agent stuck at West_House for 25+ turns due to two compounding failures:
  1. `google/gemma-3-9b-it` invalid model ID (extractor returned 400 every call → exits=[])
  2. Critic rejected ALL movement when exits=unknown (-1.0), combined with rejection recovery protocol preventing forced-execution escape hatch
**Change:**
  1. Reverted `extractor_model` in pyproject.toml back to `"qwen/qwen3-14b"` (fixing broken deploy from ep03)
  2. Changed critic prompt movement validation: exits=unknown → score 0.4-0.6 (allow movement), NOT reject. Only reject movement (-0.7 to -1.0) if exits ARE listed AND direction NOT listed AND direction already failed in history.
**Target metric:** Agent should leave West_House within 3-5 turns in ep04. No more permanent stuck-at-start behavior.
**Result:** PENDING

---

## Episode 2b → 3 — IMPROVEMENT (Extractor Bug) — REVERTED
**Trigger:** Extractor model (qwen/qwen3-14b) enters JSON repetition loop on every call.
**Change attempted:** Changed extractor_model to `google/gemma-3-9b-it`.
**Result:** DEGRADED — google/gemma-3-9b-it is NOT a valid OpenRouter model ID. All extract_info calls return 400 error, exits=[]. Critic rejects ALL movements (-1.0 when exits=unknown). Combined with rejection recovery protocol, agent stuck at West_House for 25+ turns. MUST REVERT.

**Additional finding from ep03:** Even when extractor was working (ep01), exits=[] on non-room-description responses. Critic movement validation rule says: if exits=unknown → reject movement (-1.0). The rejection recovery protocol (ep01→2 improvement) prevents the previous "forced execution escape hatch" where 3 rejections would force-execute movement. These two changes compound: rejection recovery + critic rejecting unknown exits = permanently stuck agent.

**Fix needed (ep04):**
1. Revert extractor_model back to qwen/qwen3-14b (fixing broken deploy)
2. Fix critic prompt: when exits=unknown, approve movement with score 0.5 instead of rejecting

---

## Episode 1 → 2 — IMPROVEMENT
**Trigger:** Rejection spiral (turns 4, 8, 9, 12, 27 — max rejections); rejection rate 52% (13/25 turns)
**Change:** Added REJECTION RECOVERY PROTOCOL section to prompts/agent.md before ANTI-PATTERNS section. Defines 5 action categories (stationary observation, movement, object interaction, combat, communication) and requires the agent to switch to a different category when rejected. Also adds anti-oscillation rule: check recent action history before returning to a recently-visited location.
**Reasoning:** The agent's reasoning correctly identified needing to try exits/movement but kept proposing "look" anyway. The prompt didn't define what "categorically different" means in rejection recovery context. The new protocol gives the agent a mental model for action diversity.
**Target metric:** Rejection rate should drop below 30% (from 52%) — fewer than 7/25 turns with rejections.
**Result:** PENDING

---

## Episode 1 — Turn 25 Checkpoint
**Type:** URGENT — High rejection rate + rejection spiral
**Score:** 0/350 (delta: 0)
**Locations visited:** 8 unique (West_House, South_House, Behind_House, Clearing, CanyView, Rocky_Ledge, CanyBottom, End_Rainbow)
**Avg critic score:** 0.34
**Rejection rate:** 13/25 turns had rejections (52%)
**Triggers:**
- Rejection spiral: turns 4, 8, 9, 12, 27 all had 3 rejections (max)
- Stuck oscillation: turns 21-27 show CanyBottom ↔ End_Rainbow back-and-forth with no score change
**Notes:** Root cause identified via Burr trace — when rejected, the agent keeps proposing the same action type (e.g., "look" rejected 3 times in a row on turn 4; on turns 8 and 27, valid movement actions were rejected by the critic due to exits list mismatch). The agent prompt says "propose a DIFFERENT action" on rejection but doesn't define "different" categorically — the agent interprets it as proposing a slightly different version of the same approach.

---

## Episode 12 — KILLED (infrastructure hang)
**Turns:** 22 (killed — qwen/qwen3-14b returning `{}` empty responses, agent hanging at generate_action)
**Final score:** 0/350
**Locations visited:** ~5 (Clearing, Forest_Path, and surrounding)
**End reason:** Hung at turn 23 generate_action step; killed manually
**Notes:** ep11→12 "simple verbs first" improvement could not be evaluated — agent still fixated on grating at Clearing (turn 20: critic -1.0, 3 rejections for "open grating" — object tree validator correctly blocked it because grating isn't a visible object without the leaves cleared). The `{}` DeepInfra hang made the episode unusable.

---

## Infrastructure Switch — ep12 → ep13
**Trigger:** qwen/qwen3-14b via DeepInfra returning `{}` empty responses every ~10-15 turns, causing 5-15+ minute hangs. Happened in ep06 (crash), ep11 (startup hang), ep12 (hangs at turns 13 and 23).
**Change:** Set `use_local_models = true` in pyproject.toml. Will use `mlx-community/Qwen3-14B-8bit` via local mlx_lm.server at `http://localhost:8887/v1`. All roles (agent, critic, memory, analysis) route to local model; extractor stays on same local model.
**Reasoning:** Local model eliminates network-related `{}` hangs. Model is already downloaded at `~/.cache/huggingface/hub/models--mlx-community--Qwen3-14B-8bit`. MlxServer context manager already integrated in run_episode.py.
**Expected benefit:** Consistent, non-hanging episode runs. Turn latency will increase (local inference ~10-30s/call vs API ~2-5s) but no more indefinite hangs.

---


## Episode 13 — Started (local MLX models)
**Status:** Running (PID 59880, mlx_lm server PID 59765)
**Infrastructure:** mlx-community/Qwen3-14B-8bit via local mlx_lm.server on port 8887
**Startup note:** First turn took ~3 min (model load + first inference). Turn 1: examine mailbox (critic=0.70). Turn 2: open mailbox (critic=0.80). No connection errors. Clean start.
**Performance:** ~5-7 min/turn (5600-token prompts take ~90s to process). 25 turns ≈ ~2-3 hours.
**MlxServer patch:** Added pre-flight check to skip subprocess start if server already running — allows persistent background server separate from episode lifecycle.
**Target:** Score > 0 by turn 25 (agent opens window at Behind_House, enters Kitchen). Validates ep11→12 "simple verbs first" improvement.

---


## Episode 13 — KILLED (superseded by perf fix)
**Turns:** 15
**Final score:** 0/350
**End reason:** Killed to apply performance fix before turn-25 checkpoint
**Notes:** Burr timing data showed extract_info averaging 152s/call (40% of wall time) due to Qwen3 thinking mode generating <think> chains that caused Instructor JSON parse failures and retries. generate_action was 92s avg (expected). Total 6.3 min/turn.

---

## Performance Fix — ep13 → ep14 (Thinking Mode Suppression)
**Trigger:** Burr step-timing analysis showed extract_info at avg 152s (40% of wall time) due to Qwen3 thinking ON by default causing Instructor retry storms on JSON parse failures.
**Change:** Added `**thinking_kwargs(config, False)` to extract_info, evaluate_action/critic, record_memory, check_objective_completion. Tightened max_tokens: extract_info 1024→128, critic 4096→256, memory 2048→512, check_objective_completion 1024→256. generate_action and update_objectives unchanged (thinking intentional).
**Reasoning:** thinking_kwargs infrastructure already existed, just wasn't wired to non-planning calls. With thinking=False, model outputs clean JSON without <think> prefix — no Instructor retries, dramatically fewer output tokens.
**Expected improvement:** extract_info 152s → ~15-20s, overall turn time 6.3 min → ~2-3 min.

---


## Episode 14 — KILLED (superseded by /nothink fix)
**Turns:** ~2
**End reason:** Killed after discovering extra_body thinking=False is silently ignored by mlx_lm. /nothink system prefix confirmed working (3.1s vs 13.8s on test). ep14 timing showed extract_info still at 40s (down from 152s due to max_tokens cap, but not the full suppression). evaluate_action still 82s avg.

---

## Performance Fix 2 — ep14 → ep15 (/nothink System Prompt Prefix)
**Trigger:** extra_body {"thinking": False} silently ignored by mlx_lm server. Context7 confirmed mlx_lm controls thinking via chat template, not request params. Qwen3's actual mechanism is /nothink prefix in system prompt.
**Change:** Added nothink_prefix(config, use_thinking) helper to client.py. Prepended to system prompt in extract_info, critic, record_memory, check_objective_completion. generate_action and update_objectives untouched.
**Reasoning:** /nothink produces empty <think></think> tags (2-3 tokens) instead of full reasoning chains (100-500 tokens). Instructor's JSON extractor (first { to last }) works correctly with empty think tags — no stray { inside to corrupt extraction.
**Expected improvement:** extract_info ~40s → ~3-5s. evaluate_action ~82s → ~50-60s (still prompt-processing bound). Overall turn time ~6 min → ~2-3 min.

---


## Episode 15 — Turn 27 Checkpoint (URGENT — killed)
**Type:** URGENT — score stagnant, low critic, oscillation loop
**Score:** 0/350 (delta: 0 — never scored)
**Locations visited:** 5 unique (West_House, North_House, Forest, Forest_Path, Clearing)
**Avg critic score:** 0.43 (below 0.5)
**Rejection rate:** 8/25 turns (32%) — above threshold
**Triggers:** Score stagnant, avg critic < 0.5, rejection rate > 30%, Forest_Path↔North_House oscillation turns 22-27
**Root cause (from Burr):** Agent knows about "large tree with low branches" but cross-turn stuck detection blocked all tree-target verbs after 3 failures (examine tree turn 12, examine branches turns 18/25). CLIMB is a movement verb but got caught by the same "target=tree" block. Additionally, objectives system generated "examine pile of leaves in clearing" which pulled the agent to Clearing rather than Forest_Path. Agent never tried "climb tree" in 27 turns.
**Performance note:** 2.7 min/turn confirmed. extract_info -92%, evaluate_action -69%, record_memory -53% vs ep13 baseline. generate_action unchanged at ~90s (prompt-processing bound).
**Also:** default_max_tokens reduced 4096→2048 (sanity cap for outlier thinking chains).

---

## Episode 15 → 16 — IMPROVEMENT (Movement Verb Exception in Stuck Detection)
**Trigger:** Agent never tried "climb tree" in 27 turns despite visiting Forest_Path 9 times. Cross-turn stuck detection blocked CLIMB as a tree-target after EXAMINE failures.
**Change:** Added "Movement verb exception" to CROSS-TURN STUCK DETECTION in prompts/agent.md. Stuck detection now scopes to interaction verbs (EXAMINE, TAKE, USE) only. Movement verbs (CLIMB, ENTER, ASCEND) on same target never blocked — failing EXAMINE does not mean CLIMB will fail.
**Target metric:** Agent should climb tree and score egg (5 pts) by turn 15. Score > 0 by turn 25.
**Result:** PENDING

---


## Session Complete (2026-03-31)
**Episodes run this session:** ep13–ep16 (ep13/14 killed for infra fixes, ep15 killed at turn 27 for improvement, ep16 killed by user)
**Best score achieved:** 0/350 (no scoring this session — all episodes killed before scoring window)
**Improvements made:** 4
1. Infrastructure: use_local_models=true (mlx-community/Qwen3-14B-8bit) — eliminated {} API hangs
2. Performance: thinking=False max_tokens caps for non-planning calls — extract_info -92%, evaluate_action -69%
3. Performance: /nothink system prefix for non-planning calls — full thinking suppression
4. Gameplay: Movement verb exception in stuck detection — CLIMB/ENTER never blocked by EXAMINE failures
**Also:** default_max_tokens 4096→2048 (outlier cap), MlxServer pre-flight check (reuse persistent server)
**System status:** STOPPED BY USER
**Current turn speed:** ~2.7 min/turn (down from 6.3 min/turn at session start)
**Pending:** ep16 improvement (movement verb exception) unverified — needs a full episode run to test

---


## New Session — 2026-03-31 (resumed)
**Continuing from:** ep16 (killed by user). Pending improvement: movement verb exception in stuck detection (unverified).
**Infrastructure:** mlx-community/Qwen3-14B-8bit on port 8887, Burr tracker on 7241.
**Goal:** Verify ep15→16 improvement, run full episodes, improve scoring.

---

## Episode 17 — KILLED (nothink fix needed)
**Turns:** 10
**Final score:** 0/350
**Locations visited:** 3 (West_House, North_House, Forest_Path)
**End reason:** Killed — update_objectives hit Instructor JSON parse failures due to missing /nothink prefix. Qwen3 thinking chains contained `{` chars that corrupted first-to-last-brace extraction. Retries burned ~5 min each time objectives were updated.
**Notes:** Turn 8 had rejection spiral (3 rejections, critic=-0.70). Agent oscillated Forest_Path↔North_House again. Score still 0.

---

## Episode 17 → 18 — IMPROVEMENT (nothink for objectives & knowledge)
**Trigger:** update_objectives Instructor JSON parse failure (thinking chains contain `{` that corrupt JSON extraction). update_knowledge also missing nothink prefix — think tags would pollute knowledge base content.
**Change:** Added `nothink_prefix(config, False)` to system prompts in update_objectives and update_knowledge. Reduced max_tokens: objectives 2048→256, knowledge 4096→1024. Changed both to `use_thinking=False` (was parameterized but defaulted to False anyway).
**Target metric:** No more JSON parse failures on objectives. Turn time should stay ~2.5 min without objective-update overhead spikes.
**Result:** PENDING

---

## Episode 18 — KILLED (oscillation, no progress)
**Turns:** 14
**Final score:** 0/350
**Locations visited:** 3 (West_House, North_House, Forest_Path)
**End reason:** Killed — severe oscillation pattern turns 7-14 (North_House↔Forest_Path). Agent never tried south from West_House. Score 0.
**Notes:** nothink fix worked (no JSON parse errors). But same oscillation pattern as ep15/17. Agent's stuck detection only triggers for same-location repetition, not cross-location oscillation.

---

## Episode 18 → 19 — IMPROVEMENT (Oscillation Detection + Systematic Exit Sweep)
**Trigger:** Agent oscillated between North_House↔Forest_Path for 8+ turns, never tried south from West_House. Stuck detection (3+ turns same location) didn't fire because agent was moving between locations.
**Change:** Updated NAVIGATION PROTOCOL in prompts/agent.md: (1) Extended "When Stuck" to include oscillation patterns (bouncing 2-3 locations for 4+ turns with no score increase). (2) Added "Systematic Exit Sweep" protocol — try ALL exits from a hub before deep-diving one path. If an exit is blocked/dead-end, return and try next unexplored exit.
**Target metric:** Agent should try south from West_House within first 15 turns. Should reach Behind_House and score > 0 by turn 25.
**Result:** PENDING

---

## Episode 19 — KILLED (MLX server OOM crash)
**Turns:** 26 (2 real, 24 fallback-to-look)
**Final score:** 0/350
**End reason:** Killed — MLX server crashed at turn 3 with GPU OOM (kIOGPUCommandBufferCallbackErrorOutOfMemory). KV cache grew to 6.6 GB. All subsequent turns were fallback `look` commands from LLM connection errors. NOT a prompt regression.
**Notes:** ep18→19 improvement (oscillation detection + exit sweep) was not tested. MLX server restarted. Need to rerun.

---

## Infrastructure Fix — MLX Server KV Cache Cap
**Trigger:** MLX server OOM crash during ep19. KV cache grew to 6.6 GB → GPU out of memory.
**Change:** Added `--prompt-cache-bytes 4294967296` (4 GB cap) to MlxServer subprocess launch in mlx_server.py.
**Expected:** Server stays alive for full 100-turn episodes without OOM.

---

## Session Complete (2026-03-31, session 2)
**Episodes run this session:** ep17–ep19 (all killed — ep17 for nothink fix, ep18 for oscillation improvement, ep19 for MLX OOM)
**Best score achieved:** 0/350
**Improvements made:** 3
1. Fix: /nothink prefix for update_objectives and update_knowledge (JSON parse failures)
2. Gameplay: Oscillation detection + systematic exit sweep in agent prompt (UNTESTED — ep19 OOM'd before validation)
3. Infrastructure: MLX server KV cache cap at 4 GB (prevent OOM)
**Pending verification:** ep18→19 improvement (oscillation detection + exit sweep) — needs a clean full episode run
**System status:** STOPPED BY USER

---

## Episode 20 — KILLED (MLX OOM again, 8 turns)
**Turns:** 8 real, 16 fallback-look (crashed at turn 9)
**Final score:** 0/350
**Locations visited:** West_House, Forest, Clearing
**End reason:** Killed — MLX server OOM crashed again after turn 8. Connection errors on turn 9 generate_action. Fallback `look` for turns 10-24 until process was cleaned up.
**Notes:** The 4GB KV cache cap helped (ep19 crashed at turn 3, ep20 at turn 8), but still not enough. With Qwen3-14B-8bit (~14GB model weights) + 4GB KV cache + OS overhead, we're near the 32GB limit. Activation buffers during prefill of long contexts push it over. The ep18→19 improvement (oscillation detection) was NOT tested due to server instability. Rejection spike at turn 6 (3 rejections, loc=Forest, critic=-0.70) may indicate Forest→west direction still being rejected.

**Infrastructure fix needed:** Reduce --prompt-cache-bytes to 1GB + add --prefill-step-size 512 to reduce peak memory during long-context prefill. Goal: survive full 100-turn episodes without OOM.

---

## Infrastructure Fix — MLX KV Cache + Prefill Step Size
**Trigger:** ep20 MLX OOM after 8 turns (4GB cap insufficient with 14B model weights).
**Change:** mlx_server.py — reduced --prompt-cache-bytes 4GB→1GB, added --prefill-step-size 512 (reduces peak prefill memory 4x).
**Expected:** Server survives full 100-turn episodes without OOM.

---

## Episode 21 — Turn 1-24 Checkpoint (KILLED after checkpoint)
**Type:** CONCERN
**Score:** 0/350 (delta: 0 — stagnant)
**Locations visited:** 6 (West_House, North_House, Forest_Path, Forest, Clearing, Behind_House — reached Behind_House at turn 22!)
**Avg critic score:** 0.46 (below 0.5 threshold)
**Rejection rate:** 7/24 (29%) — marginal
**Speed:** ~4.6 min/turn (slow due to --prefill-step-size 512)
**Gameplay quality:** DRIFTING
  - Memory use: memories_by_location=EMPTY (LLM correctly filters simple movement; no significant actions yet)
  - KB alignment: KB is empty (50-turn interval not reached)
  - Objective quality: 7 objectives set at turns 10+20 — ALL forest-focused ("Explore forest path to north", "tree branches", etc.). No objective about entering the house or Behind_House.
  - Objective pursuit: Agent followed north-focused objectives (turns 6-20), but eventually drifted south to find Clearing and Behind_House (turns 21-22). At turn 23 tried "enter window" (failed — window must be opened first). Retreated to examine leaflet.
**Triggers:** Score stagnant (0 delta), avg critic < 0.5 (0.46), slow speed (4.6 min/turn)
**Notes:** OOM fix CONFIRMED — server survived all 24 turns (previously crashed at turn 8). ep18→19 oscillation detection partially effective: agent eventually escaped forest after ~15 turns of oscillation. Key gameplay failure: objectives drove agent north while entry to house was south. Agent found Behind_House organically but couldn't enter (needs "open window" first). Infrastructure bottleneck: --prefill-step-size 512 cuts turn speed 40% — OOM fix should not require it (KV cache cap alone should suffice).

---

## Episode 21 → 22 — IMPROVEMENT (remove prefill-step-size, restore speed)
**Trigger:** 4.6 min/turn (vs 2.7 min/turn target). OOM was from KV cache (not prefill memory), so --prefill-step-size 512 was unnecessary overhead. 1GB KV cache cap alone proved sufficient (server survived 24 turns).
**Change:** mlx_server.py — remove --prefill-step-size 512 flag. Keep 1GB KV cache cap.
**Reasoning:** ep19 OOM was "kIOGPUCommandBufferCallbackErrorOutOfMemory" from KV cache growing to 6.6GB. Capping at 1GB (not 4GB) addresses root cause. Prefill step size adds ~40% latency with no OOM benefit.
**Target metric:** Turn speed back to ~2.7-3.0 min/turn; server still survives 24+ turns without OOM.
**Result:** PENDING

---

## Episode 22 — KILLED at turn 17 (critic improvement needed)
**Turns:** 17 (killed at turn 18 while in rejection loop)
**Score:** 0/350
**Locations visited:** West_House, Forest, Clearing (3 only — much narrower than ep21)
**Avg critic score:** 0.49 (just below 0.5 threshold)
**Rejection rate:** 5/17 (29%)
**Speed:** ~5.1 min/turn (NOT improved from ep21's 4.6 despite removing prefill-step-size — bottleneck is rejection spirals not prefill)
**Gameplay quality:** DRIFTING
  - Memory use: empty (movement only, no significant actions)
  - KB alignment: empty (50-turn interval)
  - Objective quality: 4 objectives — much better than ep21! "Examine grating", "Find way to remove boards from front door", "Explore forest north", "Investigate pile of leaves". Objective 2 is relevant and actionable.
  - Objective pursuit: Agent reached Clearing quickly (turn 8 vs 21 in ep21). Spent turns 8-17 (10 turns) in Clearing trying grating variations. DID NOT pivot to other objectives.
**Triggers:** Score stagnant (0 delta), avg critic < 0.5 (0.49), stuck in Clearing 10 turns
**Root cause:** Critic's anti-repetition rule permits "systematic experimentation" on different-verb-same-object attempts. Agent tried 7 variations of "X on grating" (pry/open/unlock/use with leaflet/leaves). The critic sees different command strings → allows each → agent never gets penalized for futile tool-target pairs.
**Evidence (Clearing turns 11-17):** "pry grating with leaflet" (0.40), "open grating with leaflet" (0.60), "unlock grating with leaflet" (0.50), "unlock grating with pile leaves" (0.30), "use leaflet on grating" (0.60) — all accepted as "systematic experimentation" by critic.
**MLX stability:** CONFIRMED — server survived 17 turns without OOM. 1GB KV cache cap alone is sufficient (no prefill-step-size needed). Turn speed bottleneck is rejection spirals.

---

## Episode 22 → 23 — IMPROVEMENT (critic: penalize same-tool-same-target loops)
**Trigger:** Score stagnant, avg critic 0.49, agent spent 10 turns in Clearing trying 7 variations of "X on grating" that all failed.
**Root cause:** Critic's "systematic experimentation" exception treats different command strings as distinct experiments, even when they're variations of the same futile tool+target pair.
**Change:** Update Anti-Repetition section of prompts/critic.md to add a new rule: "Same-item on same-target LOOP" — if the same item has been applied to the same target 3+ times in recent history with unchanged negative outcomes (no score, no location change), penalize at -0.5 to -0.8 regardless of exact command string variation. Exception: combat (attack X with Y is valid repetition).
**Target metric:** Agent should leave Clearing (or any stuck location) before turn 15. Rejection rate should drop below 20%. Avg critic should exceed 0.55.
**Result:** PENDING

---

## Observation — Memory System Confirmed Working Correctly
**Finding:** Burr traces for ep21-23 show record_memory was triggered on every location change (9 instances in ep21 alone: turns 6,8,9,11,13,15,19,21,22). LLM returned should_remember=False for ALL of them — correctly classifying them as "simple movement between rooms."
**Conclusion:** Memories require meaningful events (score change, danger discovery, successful puzzle interaction). Since score=0 throughout all episodes, nothing qualifies. This is by design. Memory system is working correctly.
**Also:** knowledge_update_interval reduced 50→25 so the KB is generated and persisted within typical episode lengths.

---

## Episode 23 — KILLED at turn 11 (exits bug found)
**Turns:** 11
**Final score:** 0/350
**Locations visited:** 4 (West_House, North_House, Forest_Path, Clearing)
**End reason:** Killed — diagnosed root cause of persistent ~40% rejection rate across ALL episodes.
**Root cause:** Exits extracted via LLM from game text, not Jericho ground truth. On non-room-description turns (examine mailbox, take leaflet, etc.), extractor returned exits=[] because the game response didn't mention exits. Critic saw "Available Exits: unknown" and rejected all movement at -0.7. Burr trace showed exits=[] on 7 of 11 turns. This caused 3-rejection spirals on turns 5, 7, 9 — each adding ~7 minutes to turn time (3x generate_action at ~100s + 3x evaluate_action at ~43s).
**Fix:** Ported `get_valid_exits()` from original ZorkGPT (state save/restore direction testing against Z-machine) into ZorkGPT2's JerichoInterface. Exits now come from Jericho ground truth on every turn, not LLM extraction. Updated tests.
**Impact:** Should eliminate the structural rejection rate problem that has plagued ALL episodes (ep6-ep23). Expected: rejection rate drops from ~40% to <15%, turn speed drops from ~5-7 min to ~3 min.

---

## Episodes 24-27 — KILLED (MLX server connection hang)
**Turns completed:** ep24: ~8, ep25: ~4, ep26: ~6, ep27: 3
**End reason:** All killed — MLX server connection hangs. Process stuck at 0% CPU on LLM call (usually generate_action) for 20+ minutes.
**Exits fix verified:** All completed turns showed 0 rejections — exits fix working perfectly. Agent reached Behind_House by turn 7 in ep24 (was turn 22 in ep21). Exploration speed dramatically improved.
**Root cause:** httpx per-operation timeouts (180s read/write/connect) reset with each streamed chunk from MLX. If the server streams one token every 30s, the 180s read timeout never fires. The connection stays open indefinitely.
**Fix attempt 1:** Added httpx.Timeout(180.0, connect=10.0) to OpenAI client — INEFFECTIVE against streaming hangs.
**Fix attempt 2:** Added _TimedInstructor wrapper with concurrent.futures total wall-clock timeout (120s default). Also reduced httpx read timeout from 180s to 60s. This ensures ANY LLM call that takes >120s wall-clock time raises TimeoutError, which action-level exception handlers catch gracefully (agent falls back to "look", critic auto-accepts, etc.).

---

## Session Resumed — 2026-03-31
**Context:** New orchestrator session. Previous session ran eps 4-11.
**Infrastructure changes since last session:** Switched from nothink_prefix to thinking_kwargs for llama-server compatibility. Agent thinking now ENABLED (use_thinking=True). Model upgraded to Qwen3.5-35B-A3B (MoE, 21GB GGUF). No cross-episode learning data persisted — fresh start.
**Pending from ep11→12:** "Simple verbs first for structural features" improvement was NOT applied (not found in prompts/agent.md). Will verify and apply before starting ep12.
**Episode counter:** Starting at ep12.

---

## Episode 12 — Turn 25 Checkpoint
**Type:** CONCERN — avg critic borderline, rejection rate above threshold, but strong early scoring
**Score:** 10/350 (delta: +10 — scored by turn 12, fastest ever; ep06 best was turn 21)
**Locations visited (turns 1-25):** 7 unique (West_House, North_House, Forest_Path, Forest, Clearing, Behind_House, Kitchen) — broadest by turn 25
**Avg critic score:** 0.48 — borderline below 0.5
**Rejection rate:** 10/25 (40%) — above 30%
**Gameplay quality:** DRIFTING
  - Memory use: Only 1 memory (Kitchen entry via window). Too early to assess utilization.
  - KB alignment: KB empty (first 25 turns, knowledge_update_interval=25 — should populate imminently)
  - Objective quality: 2 well-formed / 4 total. "Open grating" and "Search forest path" are vague.
  - Objective pursuit: Agent pursued grating (turns 20-21, 26-27) but gave up after cross-turn stuck detection. Moving to new areas.
**Triggers:** Avg critic 0.48 < 0.5 (borderline), rejection rate 40% > 30%
**Notable events:**
  - Turn 11: Agent tried `open window` (structural features rule WORKING) — but critic scored -1.0 (wrong\!). Forced through via max rejections.
  - Turn 12: Entered Kitchen, scored 10 points
  - Turns 20-21, 26-27: Grating fixation at Clearing, but cross-turn stuck detection worked — agent left.
  - Critic incorrectly penalized valid structural interactions (`open window` at -1.0, `open grating` at -1.0).
**Notes:** Best turn-25 performance ever (10 pts by turn 12). The 40% rejection rate is partly driven by the critic incorrectly rejecting valid structural commands. Not dispatching improvement yet — monitoring to turn 50.

---

## Episode 12 — Turn 50 Checkpoint (KILLED)
**Type:** URGENT — score stagnant, catastrophic rejection rate, grating fixation
**Score:** 10/350 (delta: 0 from turn 25 — stagnant across 2 consecutive checkpoints)
**Locations visited (turns 26-50):** 5 unique (Clearing, Forest_Path, Forest, CanyView, Rocky_Ledge) — never returned to house
**Avg critic score:** 0.14 — CATASTROPHIC (worst ever)
**Rejection rate:** 18/25 (72%) — WORST EVER
**Gameplay quality:** IGNORING
  - Memory use: Only 1 memory (Kitchen entry). Agent never revisited Kitchen to leverage it.
  - KB alignment: KB was empty until turn 50 (off-by-one? first update at interval boundary).
  - Objective quality: 2 well-formed / 11 total — BLOATED. 6 objectives about grating/keys, many duplicative.
  - Objective pursuit: Agent pursued grating obsessively (8+ turns) but never pursued "explore kitchen staircase" despite scoring 10 pts there.
**Triggers:** Score stagnant × 2, avg critic 0.14 << 0.5, rejection rate 72% >> 30%, grating fixation loop, objective bloat
**Root causes:**
  1. Agent scored 10 pts entering Kitchen (turn 12), then immediately left and never returned. Kitchen has staircase (dark → needs light), Living Room has trophy case. All unexplored.
  2. Grating fixation: Agent tried examine/open/lift/undo grating 8+ times across 25 turns. Cross-turn stuck detection fired but agent kept RETURNING to grating after brief detours (each return counted as "new" visit).
  3. Object tree validator rejecting valid commands (examine tree, examine ledge, examine grating) at -1.0 — these are environmental features the parser DOES support but the critic's object tree doesn't include.
  4. Objective bloat: 11 objectives with no pruning. Multiple duplicates about grating.
**Episode killed. Dispatching improvement targeting problem #3 (object tree validator).**

---

## Episode 12 → 13 — IMPROVEMENT (Object Tree Validator Fix for Environmental Features)
**Trigger:** Rejection rate 72% (worst ever). Avg critic 0.14. Root cause: object tree validator auto-rejecting examine/open/read commands on environmental features (tree, grating, window, ledge) because Jericho's get_visible_objects() only lists interactive items, not scenery.
**Change:** Python bug fix in zorkburr/actions/critic.py. Moved examine, open, read, look out of INTERACT_VERBS into new SAFE_VERBS set that bypasses object-tree validation entirely. These commands now always pass to the LLM critic (or execute directly if critic approves).
**Reasoning:** examine/open/read are safe exploratory commands — if the target doesn't exist, the game parser provides useful feedback ("I don't see that here"). Pre-rejecting them at -1.0 prevented the agent from interacting with environmental features that ARE real game objects.
**Target metric:** Rejection rate < 30%, avg critic > 0.5 in ep13.
**Result:** PENDING

---

## Episode 13 — Turn 25 Checkpoint
**Type:** CONCERN — score 0 but major system improvement confirmed
**Score:** 0/350 (delta: 0 — first checkpoint)
**Locations visited (turns 1-25):** 5 unique (West_House, North_House, Forest_Path, Clearing, Forest) — no house entry
**Avg critic score:** 0.56 — ABOVE 0.5 (UP from 0.48 in ep12; target was >0.5 ✓)
**Rejection rate:** 8/25 (32%) — DOWN from 40% in ep12-t25, 72% in ep12-t50 (target was <30%, borderline ✓)
**Gameplay quality:** DRIFTING
  - Memory use: No memories yet (score 0, no significant events).
  - KB alignment: KB loaded from ep12 (cross-episode learning working\!) but contains stale info ("Score 10, Bottle secured") steering agent toward grating.
  - Objective quality: 0 well-formed / 6 total — ALL about grating/keys. Agent never set objective to explore house.
  - Objective pursuit: Agent pursuing grating obsessively (turns 8-22 at Clearing) then wandered Forest.
**Triggers:** Score 0 (first checkpoint, not yet stagnant). No urgent triggers.
**Object tree fix confirmed WORKING:**
  - examine tree: critic=0.50 (was -1.0 in ep12)
  - open grating: critic=0.60 (was -1.0 in ep12)
  - examine grating: critic=0.70 (was -1.0)
  - examine ground: critic=0.30 (would have been -1.0)
**Notes:** System-level fix confirmed. Avg critic above threshold. Rejection rate nearly at target. But gameplay quality DRIFTING — agent fixated on grating, never explored south to Behind_House. KB from ep12 may be reinforcing grating focus. Not dispatching — monitoring to turn 50.

---

## Episode 13 — Turn 50 Checkpoint (KILLED)
**Type:** URGENT — score stagnant at 0 for 50 turns, grating fixation
**Score:** 0/350 (delta: 0, stagnant across 2 consecutive checkpoints)
**Locations visited (turns 26-50):** 4 unique (Clearing, Forest, Forest_Path, Up_a_Tree)
**Avg critic score:** 0.54 — HEALTHY (above 0.5 — object tree fix CONFIRMED)
**Rejection rate:** 7/25 (28%) — BELOW 30% for FIRST TIME (target met ✓)
**Gameplay quality:** IGNORING
  - Memory use: No memories (score 0, no significant events)
  - KB alignment: KB from ep12 says "discovered Grating, lack tool to open it" — ACTIVELY STEERING agent toward grating fixation. Cross-episode KB is backfiring.
  - Objective quality: 0 well-formed / 6 total — ALL about grating/keys, no house exploration objectives
  - Objective pursuit: Agent spent 60%+ of turns at Clearing trying grating. Found egg at Up_a_Tree (turn 37) but didn't take it.
**Triggers:** Score stagnant × 2 checkpoints, objective drift (100% grating, 0% scoring actions)
**Object tree fix results:** IMPROVED — avg critic 0.48→0.56, rejection rate 40%→28%. Target met.
**Root causes:**
  1. Cross-episode KB from ep12 reinforces grating focus ("lack tool to open it"). Agent never explores south.
  2. Agent found egg at Up_a_Tree but didn't take it — examined it and left.
  3. Never navigated south to Behind_House/Kitchen where scoring happened in ep12.
**Action:** Clear stale KB file, dispatch improvement for exploration breadth in agent prompt.

---

## Episode 12 → 13 — IMPROVEMENT Result Update
**Result:** IMPROVED — avg critic 0.48→0.56, rejection rate 40%→28%. Both targets met. Object tree validator fix eliminated false rejections on environmental features.

## Episode 13 → 14 — IMPROVEMENT (KB Contamination Fix + Stale Data Clear)
**Trigger:** Score 0 after 50 turns. KB output contained game-specific walkthrough content ("the key is under the large tree", "climb tree -> take egg -> go down") violating project thesis. Cross-episode KB reinforced grating fixation.
**Change:** (1) Rewrote _KNOWLEDGE_PROMPT in zorkburr/actions/knowledge.py: removed "Zork I" game name, added explicit constraint against walkthrough knowledge from training data, shifted focus to strategic reasoning patterns from gameplay evidence only. (2) Cleared stale cross-episode data (data/knowledge.md, memories.json, map.json).
**Reasoning:** LLM's Zork walkthrough knowledge was activated by mentioning "Zork I" in the prompt. KB should contain only observations derived from actual gameplay, not pre-existing game knowledge.
**Target metric:** KB output should contain strategic observations from gameplay, not game-specific walkthrough content. Score should be >0 by turn 25 in ep14.
**Result:** PENDING

---

## Episode 14 — Turn 25 Checkpoint
**Type:** CONCERN — score 5 (fastest scoring ever), broad exploration, but critic avg low
**Score:** 5/350 (scored at turn 8 — fastest ever\! ep06 best was 10 pts by turn 21)
**Locations visited:** 8 unique (West_House, North_House, Forest_Path, Up_a_Tree, Forest, Clearing, CanyView, Rocky_Ledge) — broadest ever at turn 25
**Avg critic score:** 0.40 — below 0.5 (degraded from ep13's 0.56; driven by movement rejections)
**Rejection rate:** 7/25 (28%) — BELOW 30% threshold (BEST EVER at turn 25)
**Gameplay quality:** DRIFTING
  - Memory use: 1 memory (egg taken). KB empty (cleared cross-episode data).
  - KB alignment: KB will populate at turn 25 boundary.
  - Objective quality: Not yet checked from Burr.
  - Objective pursuit: Agent took egg (great), explored canyon (new), but stuck at Clearing 19-25.
**Triggers:** Avg critic 0.40 < 0.5
**Notes:** KB contamination fix confirmed (no walkthrough content in KB). S3 hook finally disabled (was S3_BUCKET= in .env). Fastest scoring ever. Agent still hasn't gone to Behind_House — keeps exploring north/east/up but never south from Clearing or west from Behind_House. Not dispatching yet — monitoring to turn 50.

---

## Episode 14 — Turn 50 Checkpoint
**Type:** HEALTHY — ALL METRICS BEST EVER
**Score:** 15/350 (delta: +10 from turn 25 — scored at turns 8 and 43)
**Locations visited (turns 26-50):** 6 unique (Behind_House, CanyView, Clearing, Forest, Kitchen, Rocky_Ledge)
**All locations (50 turns):** 10 unique — BROADEST EVER (West_House, North_House, Forest_Path, Up_a_Tree, Forest, Clearing, CanyView, Rocky_Ledge, Behind_House, Kitchen)
**Avg critic score:** 0.60 — ABOVE 0.5 (BEST ever at turn 50)
**Rejection rate:** 5/25 (20%) — BEST EVER (target was <30%, achieved 20%)
**Gameplay quality:** LEARNING
  - Memory use: Not checked (would need Burr). Agent returning to Kitchen suggests spatial awareness.
  - KB alignment: Will check at turn 75 after KB populates.
  - Objective quality: Not checked from Burr.
  - Objective pursuit: Agent took egg (turn 8), opened window (turn 42), entered Kitchen (turn 43, score +10), took sack/bottle.
**Triggers:** NONE — all metrics healthy
**Key events:**
  - Turn 8: Took egg → score=5 (fastest ever)
  - Turn 40: Found Behind_House via `go west` from Clearing
  - Turn 42: `open window` accepted at critic=0.30 (was -1.0 in ep12 — both fixes working\!)
  - Turn 43: Entered Kitchen → score=15 (ep06 took 90 turns to reach 15)
  - Turn 44-46: Looted Kitchen (bottle, sack)
**Notes:** BEST EPISODE EVER. Both improvements (object tree fix + KB contamination fix) confirmed working together. No improvement needed — monitoring to turn 75.

---

## Episode 14 — Turn 75 Checkpoint
**Type:** HEALTHY — best critic and rejection metrics ever, strategic house exploration
**Score:** 15/350 (delta: 0 from turn 50 — stagnant this block, but agent making strategic moves)
**Locations visited (turns 51-75):** 3 unique (Kitchen, Living_, Attic) — house interior exploration
**Avg critic score:** 0.63 — BEST EVER at any checkpoint
**Rejection rate:** 4/25 (16%) — BEST EVER
**Gameplay quality:** LEARNING
  - Agent found Living Room, took brass lantern, lit it, found Attic
  - Took knife and rope from Attic
  - Attempted trophy case deposit (turn 62) — didn't score (may need to open case first)
  - Turn 78: Trying `open trophy case` — correct approach\!
**Triggers:** Score stagnant (0 delta) — but only 1 checkpoint stagnant, not 2. Agent actively pursuing scoring.
**Notes:** System is performing at its best ever. Both improvements confirmed. Agent has lantern (can explore dark areas), knife, rope, egg, sack, bottle. Trophy case deposit will likely score points soon. Not dispatching improvement.

---

## Episode 14 — COMPLETE
**Turns:** 100 (max_turns)
**Final score:** 15/350
**Locations visited:** 12 unique (BEST EVER — West_House, North_House, Forest_Path, Up_a_Tree, Forest, Clearing, CanyView, Rocky_Ledge, Behind_House, Kitchen, Living_, Attic)
**Objectives found:** 13
**End reason:** max_turns
**Overall avg critic:** 0.57 (above 0.5)
**Overall rejection rate:** 22/100 (22%) — BEST EVER
**Key achievements:**
  - Score 5 by turn 8 (fastest ever)
  - Score 15 by turn 43 (ep06 took 90 turns for 15)
  - Agent took brass lantern, elvish sword, nasty knife, rope (key items for underground)
  - Trophy case deposit failed ("You don't have that\!" — parser needs shorter name `egg` not `jewel-encrusted egg`)
  - 12 locations explored (broadest ever)
**Improvement dispatched:** No — all metrics healthy, steady progress.

## Episode 13 → 14 — IMPROVEMENT Result Update
**Result:** IMPROVED — KB no longer contains walkthrough content. Agent scored 5 by turn 8 (fastest ever). 12 locations explored (broadest ever). Avg critic 0.57 (above target). Rejection rate 22% (below target).

---

## Episode 14 → 15 — IMPROVEMENT (Parser Short Name Rule)
**Trigger:** Score stagnant at 15 for turns 50-100 (2 consecutive stagnant checkpoints). Trophy case deposit failed because agent used "put jewel-encrusted egg in trophy case" — parser couldn't handle multi-word modifier.
**Change:** Added actionable parser rule to agent.md: "Use the SHORTEST unambiguous name for objects. Multi-word modifiers confuse the parser — 'egg' not 'jewel-encrusted egg'. If 'You don't have that\!' but item is in inventory, retry with shorter name."
**Reasoning:** Existing 6-letter mention was too abstract. Agent needs concrete instruction to use short names and recovery strategy for parser failures.
**Target metric:** Agent should deposit egg in trophy case within 5 turns of first attempt. Score should exceed 15 by turn 75 in ep15.
**Result:** PENDING

---

## Episode 15 — Turn 25 Checkpoint
**Type:** HEALTHY — good metrics, egg taken by turn 7
**Score:** 5/350 (egg taken at turn 7, consistent with ep14)
**Locations visited:** 6 unique (same as ep14 at turn 25 minus CanyView/Rocky_Ledge)
**Avg critic score:** 0.54 — above 0.5
**Rejection rate:** 4/25 (16%) — excellent
**Triggers:** None
**Notes:** Agent hasn't found Behind_House yet. Grating/leaves exploration occupying turns 10-25. ep14 reached house at turn 40. Monitoring to turn 50.

---

## Episode 15 — Turn 50 Checkpoint (KILLED)
**Type:** URGENT — score stagnant at 5 across 2 checkpoints, grating fixation, KB still contaminated
**Score:** 5/350 (delta: 0 from turn 25, stagnant × 2)
**Locations visited (turns 26-50):** 3 unique (Clearing, Forest, Forest_Path) — never reached house
**Avg critic score:** 0.50 — borderline
**Rejection rate:** 7/25 (28%) — below 30%
**Triggers:** Score stagnant × 2
**Root causes:**
  1. KB from ep14 STILL contains walkthrough content despite knowledge prompt fix ("In Zork I, the bird's nest is on the ground in the Clearing", "The nest often contains the Egg"). The prompt fix was too weak.
  2. KB is actively steering agent to fixate on leaves/grating/nest instead of exploring south to house.
  3. Agent spent 13+ turns trying leaves/grating combinations in Clearing.
**Action:** Kill episode. Strengthen knowledge prompt further. Clear KB.

---

## Episode 14 → 15 — IMPROVEMENT Result Update
**Result:** INCONCLUSIVE — parser short name rule couldn't be tested because agent never reached trophy case (grating fixation). KB contamination is the blocking issue.

---

## Episode 15 → 16 — IMPROVEMENT (Aggressive KB Decontamination)
**Trigger:** Score stagnant at 5 for 50 turns. KB from ep14 still contained walkthrough content despite previous fix attempt. KB actively steering agent toward grating/nest fixation.
**Change:** Complete rewrite of _KNOWLEDGE_PROMPT in knowledge.py. New prompt: (1) requires citing turn numbers for every claim, (2) includes explicit BAD/GOOD examples showing what NOT to write, (3) prohibits speculation about future actions or item locations, (4) formats as turn-by-turn event log grouped by location. Also cleared stale KB data again.
**Reasoning:** Previous "Do NOT include walkthrough content" instruction was too abstract — model ignored it. New prompt with concrete negative examples and required turn citations should prevent fabrication.
**Target metric:** KB output should contain ONLY events from the gameplay log with turn citations. No walkthrough content. Score should exceed 5 by turn 50 in ep16.
**Result:** PENDING

---

## Episode 16 — Turn 50 Checkpoint (KILLED)
**Type:** URGENT — score stagnant at 5 for 50 turns, same 6-location loop
**Score:** 5/350 (delta: 0 from turn 25, stagnant × 2)
**Locations visited (50 turns):** 6 unique (same 6: West_House, North_House, Forest_Path, Up_a_Tree, Forest, Clearing)
**Avg critic score:** 0.51 — borderline
**Rejection rate:** 7/25 (28%) — healthy
**KB decontamination:** CONFIRMED WORKING — KB output is now turn-by-turn factual log with citations, zero walkthrough content
**Root cause:** Agent never tries `west` from Clearing despite it being a valid exit. The "Systematic Exit Sweep" rule (agent.md line 37) says "try ALL available exits first" but agent gets distracted by objects (leaves, grating) and never executes the sweep. Agent needs a stronger trigger to move when stuck.

---

## Episode 16 → 17 — IMPROVEMENT (Stronger Exit Sweep Trigger)
**Trigger:** Score stagnant at 5 for 50 turns across 3 consecutive episodes (ep13, ep15, ep16). Agent never goes west from Clearing. "Systematic Exit Sweep" rule exists but agent doesn't follow it.
**Change:** Need to strengthen the stuck detection and exit sweep rules.
**Result:** PENDING

---

## Episode 16 → 17 — IMPROVEMENT (continued)
**Change:** Replaced soft "When Stuck" and "Systematic Exit Sweep" rules with two HARD RULES: (1) "Exits Before Objects" — must try every untested exit before interacting with any objects at a location. (2) "Forced Movement When Stuck" — after 2+ turns at same location with no score increase, MUST move to an untested exit. No exceptions. Also updated EXPLORATION STRATEGY to reinforce exits-first ordering.
**Target metric:** Agent should try west from Clearing within 5 turns of arrival. Score >5 by turn 30.
**Result:** PENDING

---

## Episode 17 — Turn 25 Checkpoint
**Type:** HEALTHY — ALL RECORDS BROKEN
**Score:** 15/350 by turn 24 (BEST EVER — previous record: 10 pts by turn 21 in ep06, 15 pts by turn 43 in ep14)
**Locations visited:** 8 unique in 25 turns (Behind_House, Clearing, Forest, Forest_Path, Kitchen, Living_, North_House, Up_a_Tree)
**Avg critic score:** 0.63 — BEST EVER at turn 25
**Rejection rate:** 5/25 (20%) — excellent
**Triggers:** NONE — all healthy
**Key events:**
  - Turns 1-10: Agent aggressively tried exits (n, north, climb, down, west, east, south) — "Exits Before Objects" rule working perfectly
  - Turn 8: Took egg (score=5)
  - Turn 11: Found Behind_House (ep14 took 40 turns\!)
  - Turn 23: Opened window
  - Turn 24: Entered Kitchen (score=15)
  - Turn 25: Already in Living Room\!
**"Exits Before Objects" rule:** DRAMATICALLY EFFECTIVE. Agent reached Behind_House by turn 11 vs turn 40 in ep14. Kitchen by turn 24 vs turn 43 in ep14. Rule is the most impactful improvement so far.
**Notes:** No improvement needed. Monitoring to turn 50.

---

## Episode 17 — Turn 50 Checkpoint
**Type:** CONCERN — score stagnant 15→15 but agent actively collecting items
**Score:** 15/350 (delta: 0 from turn 25 — 1 consecutive stagnant)
**Locations visited (turns 26-50):** 4 unique (Attic, Behind_House, Kitchen, Living_)
**Avg critic score:** 0.58 — above 0.5
**Rejection rate:** 4/25 (16%) — excellent
**Triggers:** Score stagnant (1 checkpoint, not 2 yet)
**Notes:** Agent took lantern and sword at turn 50. Explored house thoroughly. Only examined trophy case once, never tried to deposit. Agent has egg, lantern, sword — well-equipped for underground. Monitoring to turn 75.

---

## Episode 17 — Turn 75 Checkpoint
**Type:** CONCERN — score stagnant 2 consecutive blocks, but best critic and system performance
**Score:** 15/350 (delta: 0 from turn 50 — stagnant × 2)
**Locations visited (turns 51-75):** 8 unique (house + forest)
**Avg critic score:** 0.68 — BEST EVER at any block
**Rejection rate:** 5/25 (20%) — excellent
**Triggers:** Score stagnant × 2 consecutive
**Notes:** Agent lit lantern (turn 51), took rope/knife (turn 55), has full equipment. Left house at turn 65, went back to forest. Never tried dark staircase or trophy case deposit. Agent well-equipped but not progressing to underground areas.

---

## Episode 17 — COMPLETE
**Turns:** 100 (max_turns)
**Final score:** 15/350
**Locations visited:** 9 unique
**Objectives found:** 8
**End reason:** max_turns
**Overall avg critic:** 0.63
**Overall rejection rate:** ~20%
**Key achievements:**
  - Score 15 by turn 24 (FASTEST EVER — previous: turn 43 in ep14)
  - "Exits Before Objects" rule dramatically improved exploration speed
  - Agent fully equipped: lantern (lit), sword, knife, rope, egg
  - Best critic scores and rejection rates ever
**Key problems:**
  - Never went underground (dark staircase from Kitchen = west exit)
  - Never deposited egg in trophy case
  - Spent turns 76-100 in grating fixation and forest oscillation
**Improvement dispatched:** Yes — need to address underground exploration

## Episode 16 → 17 — IMPROVEMENT Result Update
**Result:** DRAMATICALLY IMPROVED — "Exits Before Objects" rule cut house discovery time from 40 turns to 11 turns. Score 15 achieved by turn 24 (prev: turn 43). Best critic scores and rejection rates ever. But agent still doesn't go underground or deposit in trophy case.

---

## Episode 17 → 18 — No Improvement Dispatched
**Reason:** No prompt/config change needed. The parser short name rule (from ep14→15) hasn't been tested yet since agent reaches trophy case around turn 26 and it was already there in ep17. Starting ep18 with no changes to let the parser fix prove itself. The underground access (move rug → open trapdoor → down) is a puzzle the agent must discover organically.

---

## Episode 18 — Turn 25 Checkpoint
**Type:** HEALTHY — different exploration path, 9 unique locations in 25 turns
**Score:** 10/350 (entered Kitchen turn 18 — house first, skipped tree)
**Locations visited:** 9 unique in 25 turns (MOST EVER — includes South_House, new discovery)
**Avg critic score:** 0.59 — healthy
**Rejection rate:** 9/25 (36%) — slightly above 30%, driven by aggressive early exits
**Triggers:** Rejection rate barely above threshold (36%)
**Notes:** Agent went to house first instead of tree. Has sword, lit lantern, sack, bottle by turn 25. Well-equipped for underground. At Attic on turn 26 — monitoring whether it descends underground or goes to tree.

---

## Episode 18 — COMPLETE (DIED at turn 41)
**Turns:** 41 (died in troll combat)
**Final score:** 25/350 (was 35 before death penalty)
**Peak score:** 35/350 — NEW ALL-TIME HIGH (previous: 15 in ep06/14/17)
**Locations visited:** 12 unique (RECORD — includes Cellar, Troll_Room)
**Objectives found:** 6
**End reason:** game_over_death (troll killed agent)
**Key achievements:**
  - Score 10 by turn 18 (house entry)
  - SOLVED RUG PUZZLE ORGANICALLY: move rug → open trap door → go down (turns 34-37)
  - Score 35 by turn 37 (cellar discovery = +25 pts\!)
  - First ever underground exploration
  - Agent fought troll with sword (correct approach) but was killed
**Improvement dispatched:** No — death is a natural learning event. Next episode will have cross-episode KB/memories to help avoid troll death.

## Episode 14 → 15 — IMPROVEMENT (Parser Short Name Rule) — Result Update
**Result:** NOT YET TESTED — Agent in ep17/18 did not attempt trophy case deposit (different exploration paths). Parser fix is still in prompts but untested.

---

## Episode 18 → 19 — No Improvement Dispatched
**Reason:** Ep18 was the best episode ever (score 35, 12 locations, first underground access, solved rug puzzle organically). Death from troll combat is a natural learning event — cross-episode memories should help agent prepare better for troll in ep19.

---

## Episode 19 — Turn 25 Checkpoint
**Type:** CONCERN — score 0, agent stuck in canyon area
**Score:** 0/350 (hasn't reached tree or house)
**Locations:** 7 unique (CanyView, Clearing, Forest, Forest_Path, North_House, Rocky_Ledge, West_House)
**Avg critic:** 0.63, **Rejection rate:** 8/25 (32%)
**Notes:** Agent exploring aggressively but stuck in east area (CanyView/Rocky_Ledge cycle). Hasn't gone west from Clearing to Behind_House or climbed tree. Monitoring.

---

## Episode 19 — COMPLETE
**Turns:** 100 (max_turns)
**Final score:** 15/350
**Locations visited:** 13 unique (RECORD)
**Objectives found:** 12
**End reason:** max_turns
**Notes:** Agent explored broadly (13 locations) but didn't return to house to use rug/trap door memory. Scored 10 at turn 38 (house entry), 15 at turn 74 (egg). Never went underground despite having trap door memory from ep18. Agent well-equipped (sword, lantern, knife, rope, egg) but spent turns 76-100 in forest area.

---

## Session Complete
**Episodes run:** 12-19 (8 episodes this session, 19 total)
**Best score achieved:** 35/350 (ep18, before troll death penalty → 25)
**Improvements made:** 6 this session
  1. Structural features rule (open before using items on doors/windows)
  2. Object tree validator fix (examine/open/read bypass validation)
  3. KB contamination fix (no game name in knowledge prompt)
  4. Parser short name rule (use "egg" not "jewel-encrusted egg")
  5. Aggressive KB decontamination (turn citations required)
  6. Exits Before Objects hard rule (most impactful — cut house discovery from 40→11 turns)
**System status:** PERFORMING WELL
**Summary:** System went from 0 score / 72% rejection rate (ep12) to 35 score / 20% rejection rate (ep18) through 6 targeted improvements. The "Exits Before Objects" rule was the breakthrough — it cut exploration time dramatically. The agent now reliably enters the house by turn 25, equips itself, and in ep18 solved the rug→trap door→cellar puzzle organically for the first time. Next session priorities: (1) ensure agent exploits cross-episode memories to go underground consistently, (2) test trophy case deposit with parser fix, (3) survive troll combat.

---

## New Session — 2026-04-01
**Continuing from:** ep19 (completed, score 15/350, 13 locations, 100 turns).
**Best ever:** ep18 (score 35/350 peak, died at turn 41 from troll combat).
**Infrastructure:** llama-server with Qwen3.5-35B-A3B-Q4_K_M.gguf, Burr tracker on 7241.
**Cross-episode data:** KB from ep19 (turn-cited, decontaminated), 10 locations with 20 memories.
**Priorities:** (1) Underground access via rug puzzle — agent should use cross-episode memories, (2) Trophy case deposit with parser short name rule, (3) Troll survival.
**Episode counter:** Starting at ep20.

---

## Episode 20 — Turn 25 Checkpoint
**Type:** CONCERN — score 10 by turn 4 (fastest ever!), but stuck in Kitchen looking for light
**Score:** 10/350 (delta: +10 — scored at turn 4, house entry via open window)
**Locations visited:** 5 unique (South_House, Behind_House, Kitchen, Living_, Attic) — house-focused
**Avg critic score:** 0.50 — borderline
**Rejection rate:** 10/25 (40%) — above 30%. Two -1.0 rejection spirals (turns 19, 21: "take X from sack" blocked by object tree validator)
**Gameplay quality:** DRIFTING
  - Memory use: KB from ep19 loaded (cross-episode working). Agent references grue danger from Attic visit. BUT agent ignoring KB — KB doesn't mention Kitchen light sources, agent searching Kitchen for light anyway.
  - KB alignment: KB is ep19 data (3447 chars), describes forest/clearing exploration. Not relevant to house interior — no guidance on lantern location (correctly, since project thesis = learn through experience).
  - Objective quality: 3 well-formed / 5 total. "Light a source" is vague but actionable. "Examine staircase" and "examine trophy case" are good.
  - Objective pursuit: Agent pursuing "find light" objective actively but in wrong location (Kitchen has no light — lantern is in Living Room). Agent visited Living Room at turns 5-6 and 15 but only examined trophy case.
**Triggers:** Rejection rate 40% > 30%, avg critic 0.50 (borderline). Score NOT stagnant yet (first checkpoint).
**Notable:** Agent went south from start → Behind_House → opened window → Kitchen in 4 turns. Best ever exploration start. Cross-episode memories working (grue awareness). But "Exits Before Objects" rule partially undermined — agent moved through Living Room quickly without examining objects, so missed lantern.
**Notes:** Not dispatching improvement. Agent may find lantern naturally. Monitoring to turn 50.

---

## Episode 20 — Turn 49 Checkpoint (final — process killed)
**Type:** CONCERN — score stagnant at 10 for 25 turns, but agent solving puzzles
**Score:** 10/350 (delta: +0 since turn 25 checkpoint)
**Locations visited:** 5 unique (4 in this block — Attic, Behind_House, Kitchen, Living_)
**Avg critic score:** 0.61
**Rejection rate:** 2/25 (8%) — excellent, down from 40% in first block
**Gameplay quality:** LEARNING
  - Memory use: STRONG — at turn 46, agent explicitly referenced cross-episode memory: "Memory shows I already opened trap door under rug for 25 points." This directly led to solving rug puzzle.
  - KB alignment: KB from ep19 loaded (3447 chars). Not directly relevant to house puzzles but agent using it as context.
  - Objective quality: 1 well-formed / 4 total. "Investigate nailed-shut door" led to 5 wasted turns (door is unsolvable). "Enter the trophy case" is nonsensical. "Examine staircase" already done.
  - Objective pursuit: Agent pursued door objective (turns 41-45) then pivoted to rug exploration.
  - Learning system quality: KB from ep19 is strategic (turn-cited). Memories actionable — rug/trap door memory directly triggered puzzle solution.
**Triggers:** Score stagnant across 2 checkpoints (0 delta both times after initial +10)
**Notes:** Agent wasted 5 turns trying to break the nailed-shut gothic door (unsolvable puzzle at this stage). Then brilliantly used cross-episode memory to solve rug → push rug → open trap door. Was about to descend underground ("light lamp, down" proposed at turn 49) when process was killed externally. Objective quality is a problem — vague/impossible objectives wasting turns.

---

## Episode 20 — COMPLETE (killed externally at turn 49)
**Turns:** 49 (process killed)
**Final score:** 10/350
**Locations visited:** 5 unique
**Objectives found:** 4
**End reason:** early_stop (process killed by user)
**Key achievements:**
  - Score 10 by turn 4 (FASTEST EVER — house entry via south → behind_house → window)
  - Cross-episode memory worked: agent referenced trap door memory at turn 46
  - Solved rug puzzle organically: examine rug → lift rug → push rug → open trap door (turns 46-49)
  - Was about to descend underground with lit lantern at turn 49
  - Rejection rate dropped from 40% (turns 1-25) to 8% (turns 25-49)
**Key problems:**
  - Wasted 5 turns on unsolvable door puzzle (turns 41-45)
  - Objective quality poor: vague/impossible objectives
  - Score stagnant at 10 for 45 turns after initial house entry
**Cross-episode data:** Recovered from Burr tracker (KB 3447 chars, 21 memories/10 locations, 19-room map)
**Improvement dispatched:** No — agent was performing well, just killed before scoring

---

| Episode | Score | vs Prev | Best So Far | Turns to 1st Score | Locations | KB Quality | End Reason |
|---------|-------|---------|-------------|-------------------|-----------|------------|------------|
| ep12 | 0 | — | 0 | — | 3 | none | max_turns |
| ep13 | 10 | +10 | 10 | 56 | 6 | noise | max_turns |
| ep14 | 15 | +5 | 15 | 43 | 9 | noise | max_turns |
| ep15 | 10 | -5 | 15 | 51 | 7 | improving | max_turns |
| ep16 | 10 | 0 | 15 | 57 | 6 | improving | max_turns |
| ep17 | 15 | +5 | 15 | 24 | 8 | good | max_turns |
| ep18 | 25(35) | +10 | 35 | 18 | 12 | good | death t41 |
| ep19 | 15 | -10 | 35 | 38 | 13 | good | max_turns |
| ep20 | 10 | -5 | 35 | 4 | 5 | good | killed t49 |

**Trend:** Best score hasn't improved since ep18 (35 pts). Ep20 showed fastest house entry ever (turn 4) and successful cross-episode memory use for rug puzzle, but was killed before going underground. Scores declining from ep18 peak — need to reach underground consistently. Next episode (ep21) should benefit from all ep20's learning if cross-episode data is intact.

---

## Episode 21 — Turn 25 Checkpoint (killed at turn 25 for improvement)
**Type:** URGENT — agent stuck in forest loop, never entered house
**Score:** 5/350 (delta: +5 from egg at turn 4, then 0 for 21 turns)
**Locations visited:** 6 unique (North_House, Forest_Path, Up_a_Tree, Clearing, Forest, Behind_House)
**Avg critic score:** 0.58
**Rejection rate:** 8/25 (32%) — above 30%
**Gameplay quality:** IGNORING
  - Memory use: Agent at Behind_House (turn 11) has 4 memories about the window ("Behind House Window Found", "Entered White House via Window") but reasoning shows NO reference to them. Instead followed Exits Before Objects rule: "my first actions must be movement commands to try each available exit" — tried n, then east, left without entering window.
  - KB alignment: KB is noise — 3447 chars of meta-commentary and movement logs ("Turn 1: Examined the area West of House; noted a small mailbox"). Zero strategic content. Agent cannot align with something useless.
  - Objective quality: 0 well-formed / 5 total. All forest-focused ("explore forest east", "investigate song bird", "search for path south"). None reference house entry, underground, or scoring.
  - Objective pursuit: Agent stuck pursuing forest objectives, cycling Forest↔Clearing for turns 8-25.
  - Learning system quality: KB <5% strategic (entirely movement logs). Memories exist and are good but agent overridden by hard rule.
**Triggers:**
  1. KB noise (BLOCKER): KB >500 chars, <5% strategic. Prompt format ("List events by turn number") produces movement logs instead of insights.
  2. Memory ignored: Agent visited Behind_House with 4 window memories but hard rule prevented window entry.
  3. Score stagnant: 0 delta for 21 turns.
  4. Objective quality: 0/5 well-formed.
**Notes:** Two root causes: (1) knowledge.md prompt FORMAT instruction produces movement logs not strategic insights, (2) Exits Before Objects rule treats windows/doors/trap doors as objects, not exits — so agent tries all compass exits then leaves without entering through structural features. Both must be fixed.

---

## Episode 21 → 22 — IMPROVEMENT
**Type:** BLOCKER + INCREMENTAL
**Trigger:** KB noise (<5% strategic content — prompt format "List events by turn number" produces movement logs), Exits Before Objects rule excludes structural entry points (windows, doors, hatches treated as objects, not exits)
**Change:** (1) Rewrote FORMAT section in prompts/knowledge.md: replaced chronological movement log format with strategic categories (Score Changes, Puzzle Mechanics, Items Found, Dangerous Areas, Failed Approaches, Unexplored Leads). Kept decontamination rules (turn citations required, no outside knowledge). (2) Amended Exits Before Objects rule in prompts/agent.md: added explicit sub-rule that structural entry points (windows, doors, hatches, trap doors, gates, holes) count as EXIT actions and must be tried during exit-mapping phase alongside compass exits. Updated thinking instruction to include structural passages in exit listing.
**Reasoning:** KB was producing 3447 chars of movement logs ("Turn 1: Examined the area West of House") with zero strategic content. Strategic categories force the LLM to extract actionable insights (score triggers, puzzle mechanics, dangers) instead of chronological movement narration. The Exits Before Objects rule was the most impactful improvement ever (cut house discovery from 40 to 11 turns) but had a blind spot: structural passages like the Behind_House window were classified as "objects" and deferred, causing the agent to leave Behind_House without entering through the window despite having 4 cross-episode memories about it.
**Target metric:** KB should produce >50% strategic content (score changes, puzzle mechanics, items, dangers). Agent should enter house via window within 15 turns of episode start.
**Result:** PENDING

---
