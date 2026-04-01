You are reviewing a gameplay log from a text adventure. Summarize what happened.

STRICT RULES:
1. ONLY describe events that appear in the gameplay log below. Every claim must describe the specific action and location where it happened.
2. NEVER add knowledge from outside the log. You likely know this game — ignore that knowledge entirely.
3. BAD examples (NEVER write these): "In this game, the key is usually found...", "The nest contains...", "You need to go to X to find Y", "The standard solution is..."
4. GOOD examples: "Took egg from bird's nest in tree (score +5)", "Entered house via kitchen window (score +10)", "Dark staircase below Kitchen requires light source — got 'too dark' without lantern"
5. Do NOT include turn numbers — they are meaningless across episodes. Describe WHAT happened and WHERE, not WHEN.

FORMAT: Organize into these strategic categories (skip empty categories):

PRIORITY ORDERING: The agent only sees the first ~2000 characters of this summary. Order sections by strategic value:
1. Score Changes (directly actionable — the agent needs to know what earns points)
2. Puzzle Mechanics Discovered (unlocks progress)
3. Dangerous Areas (prevents death/lost turns)
4. Failed Approaches (prevents wasted turns)
5. Items Found (supports puzzle solving)
6. Unexplored Leads (lowest priority — exploration is the default behavior)

Within each section, put the most important entries first.

**Score Changes:** Each score increase/decrease with location and triggering action.
**Puzzle Mechanics Discovered:** Interactions that revealed how something works (e.g., "pushing rug in Living Room revealed trap door").
**Items Found:** Item name and location found. Note if taken or left behind.
**Dangerous Areas:** Locations/actions that caused death or damage.
**Failed Approaches:** Actions attempted 2+ times that consistently failed, so the agent can avoid repeating them.
**Unexplored Leads:** Exits seen but not taken, locked doors, dark passages — with location.

Do NOT speculate about what the agent should do next or where items might be. Only record what actually happened in the log.