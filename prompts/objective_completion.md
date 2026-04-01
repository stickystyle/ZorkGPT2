Given the most recent action and response in a text adventure, determine which objectives (if any) have been completed.

STRICT RULES — Only mark an objective as completed if ALL of these are true:
1. The game response contains DIRECT evidence of success (e.g., "Done.", score increase, item acquired, enemy defeated, puzzle solved)
2. The objective's GOAL was actually achieved, not just attempted or abandoned
3. Leaving a room or moving away does NOT count as completing an objective about that room

BAD completions (NEVER mark these as complete):
- "Lower water level" when agent just left the flooded room
- "Defeat the troll" when agent ran away
- "Open the door" when the door is still closed but agent moved elsewhere
- "Find the key" when agent searched but found nothing

GOOD completions (mark these as complete):
- "Defeat the troll" when response says "The troll dies" or similar
- "Open the trap door" when response says "The door opens" or "Done."
- "Get the egg" when response says "Taken."
- Any objective where the score increased as a direct result

When in doubt, do NOT mark as completed. False completions waste the agent's planning capacity.