Given the most recent action and response in a text adventure, determine which objectives (if any) have been completed.

Mark an objective as completed when the goal has been ACHIEVED — the agent has done what the objective asks for. Match by intent, not by exact wording.

Types of completion:
- **Action objectives** ("open the door", "take the egg"): completed when the game response confirms the action succeeded (e.g., "Done.", "Taken.", score increase)
- **Exploration objectives** ("examine X", "explore Y", "see where Z leads", "investigate W"): completed when the agent has visited the area or examined the thing. Arriving at a new room via a staircase completes "explore the staircase." Examining an object completes "examine the object."
- **Collection objectives** ("find X", "get Y"): completed when the item is in inventory

Do NOT mark as completed:
- Objectives the agent attempted but FAILED at (e.g., "open door" but door is still closed)
- Objectives where the agent left without achieving the goal (e.g., "defeat troll" but agent ran away)

When in doubt about action/collection objectives, do not mark completed. When in doubt about exploration objectives where the agent clearly visited the place, mark completed.