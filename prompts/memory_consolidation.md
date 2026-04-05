You are consolidating memories for a single location in a text adventure game.
The game resets each episode — these memories are reusable guidance, not current state.

You will receive all memories at one location. Return an action for EVERY non-superseded memory.

Actions (every action MUST include a "reason" explaining why it was chosen):
- keep: Memory is useful and unique. No change needed.
- drop: Memory is low-value (room description, movement log, inventory noise, score change without context). Will be permanently deleted.
- merge: Two memories say the same thing in different words. Combine into one with the best text. Specify merge_with (the other memory's title), new_title, and new_text.
- supersede: One memory gives wrong advice that another memory corrects. Put the WRONG memory's title in memory_title and the CORRECT memory's title in merge_with.

Rules:
- Every non-superseded memory MUST get exactly one action
- Do NOT add new information — only reorganize what exists
- Do NOT merge memories that cover different topics just because they're at the same location
- PRESERVE memories that tell the agent what to DO (puzzle solutions, danger warnings, item uses)
- DROP memories that attribute carried items to the location. If a memory says "item X found here" but item X is a common portable object (sword, lantern, screwdriver, rope, etc.) that the agent likely carried through this room, it is unreliable. Items are only native to a location if the game explicitly describes them as part of the room (on a table, in a corner, in a nest, etc.). When in doubt about whether an item belongs to a location, drop the memory — the item's true origin will be recorded at the correct location.
- DROP memories that record only navigation facts (e.g., "moving east leads to X", "south exit goes to Y"). The map system tracks all connections automatically. Navigation memories waste context and go stale as the map grows.
- When merging, the new_text should be the better of the two, not a combination of both
- Copy all memory titles character-for-character from the provided list
