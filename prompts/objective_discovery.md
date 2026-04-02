You are analyzing a text adventure game session to discover objectives.
Based on the recent gameplay, identify 1-5 actionable objectives the player should pursue.
Objectives should be specific and achievable (e.g., "Open the trapdoor" not "Win the game").

## Rules

### Only reference what the game has SHOWN
Every objective must trace back to something directly observed in game output:
an item described in a room, a response from a command, a score change, an NPC's
words, or a visible feature. **Never infer the existence of items, tools, locations,
or NPCs that have not appeared in the game text.** If you haven't seen it, it
doesn't exist for objective purposes.

### Parser prompts are not evidence
When the game responds with "What do you want to [verb] with?" or similar parser
questions, this means the action requires a tool — but it does NOT tell you which
tool. The correct objective is "find something to [verb] with" — never name a
specific tool unless you have already seen that tool in the game text.

### Prioritize Strategic Knowledge
When the Strategic Knowledge (KB) section is available in the context, prefer
objectives that align with its recommended strategies and priorities. The KB
represents accumulated experience and should guide objective selection.

### Retire stale objectives
If the gameplay history shows that the player has attempted an objective 3 or more
times without making progress (no score change, no new discovery, no state change),
do NOT re-generate that objective. Replace it with a different approach or a new
exploration target.

### Prefer exploration over fixation
If the player has been in the same location for 3+ consecutive turns without
progress, prioritize objectives that involve moving to unexplored areas or
revisiting previously productive locations.

## Output format

For each objective, include:
- **text**: A clear, specific description of what to accomplish
- **location_id**: The numeric location ID where this objective should be pursued (use the current location ID if the objective is here, or 0 if it's a general objective not tied to a specific place)
- **location_name**: The name of that location (or empty string if general)
