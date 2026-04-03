# Prompt Editing Rules

## No Game-Specific Knowledge in Prompts

Prompts teach **reasoning strategies only**. The agent learns game-specific facts (puzzle solutions, item locations, safe paths, walkthrough steps) through gameplay, stored in its memory and knowledge base systems.

Before adding or changing prompt text, ask: **"Would this instruction apply to a different text adventure?"**

- **Yes** — it belongs in a prompt (e.g., "try examining objects before using them", "revisit locations after acquiring new items")
- **No** — it does not belong in a prompt (e.g., "the jeweled egg is in the bird's nest", "use the sword to kill the troll", "go north from the clearing to reach the house")

## What Goes Where

| Content | Belongs in |
|---|---|
| General exploration strategies | Prompts |
| Reasoning heuristics | Prompts |
| Output format instructions | Prompts |
| Puzzle solutions or hints | Nowhere — agent discovers these |
| Item locations or uses | Nowhere — agent discovers these |
| Map knowledge or safe routes | Nowhere — agent discovers these |
| Learned game facts | `MEMORIES_BY_LOCATION` (auto) |
| Strategic summaries | `KNOWLEDGE_BASE` (auto) |
