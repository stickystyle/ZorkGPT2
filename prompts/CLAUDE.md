# Prompt Editing Rules

## No Game-Specific Knowledge OR Strategy in Prompts

Prompts teach **reasoning heuristics only** — how to think, not what to do. The agent learns game-specific facts AND game strategies through gameplay, stored in its memory and knowledge base systems.

### The Two-Question Test

Before adding or changing prompt text, ask BOTH questions:

1. **"Would this instruction apply to a different text adventure?"**
   - No → it does not belong in the prompt (game-specific fact)

2. **"Is this telling the agent WHAT to do rather than HOW to think?"**
   - Yes → it does not belong in the prompt (game strategy)

Both must pass. An instruction can be game-agnostic but still be strategy rather than reasoning.

### Examples

| Instruction | Q1: Different game? | Q2: What vs How? | Verdict |
|---|---|---|---|
| "Try examining objects before using them" | Yes | How to think | **OK — reasoning heuristic** |
| "Read all KB entries for a location before acting" | Yes | How to think | **OK — information processing** |
| "Deposit treasures in safe storage before danger" | Yes-ish | What to do | **NO — game strategy** |
| "Take weapons and light sources before descending" | Yes-ish | What to do | **NO — game strategy** |
| "The sword is in the Living Room" | No | What to do | **NO — game fact** |
| "Distinguish hard failures from puzzle feedback" | Yes | How to think | **OK — reasoning heuristic** |

### The Gray Area: Strategy vs Reasoning

The hardest cases are instructions that sound general but encode strategic knowledge the agent should learn from experience:

- **"Bank treasures before risk"** — The agent should learn this by dying with treasures and losing score. The KB/memory system captures this.
- **"Take all essential items before solving puzzles"** — Sounds reasonable, but "essential" implies the agent already knows which items matter. It should learn through experience that skipping items leads to problems.
- **"Use weapons in combat"** — Too obvious to state, and the agent should figure this out from game feedback.

**Rule of thumb:** If the instruction would save the agent from a mistake it hasn't made yet, it's strategy, not reasoning. The agent needs to make mistakes to learn. Prompts should help it *think about* mistakes it has already made (via KB/memories), not prevent mistakes it hasn't encountered.

## What Goes Where

| Content | Belongs in |
|---|---|
| Reasoning heuristics (how to think) | Prompts |
| Output format instructions | Prompts |
| Parser syntax and conventions | Prompts |
| Game strategies (what to do) | Nowhere — agent discovers these via KB |
| Puzzle solutions or hints | Nowhere — agent discovers these |
| Item locations or uses | Nowhere — agent discovers these |
| Map knowledge or safe routes | Nowhere — agent discovers these |
| Learned game facts | `MEMORIES_BY_LOCATION` (auto) |
| Strategic summaries | `KNOWLEDGE_BASE` (auto) |
