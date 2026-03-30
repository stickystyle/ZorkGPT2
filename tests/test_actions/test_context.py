from burr.core import State
from zorkburr.actions.context import assemble_context
from zorkburr.state import S

def test_assemble_context_basic():
    state = State({
        S.GAME_RESPONSE: "You are in a forest.",
        S.LOCATION_NAME: "Forest",
        S.INVENTORY: ["lamp", "sword"],
        S.SCORE: 10,
        S.ACTION_HISTORY: [],
        S.EXITS: [],
        S.DISCOVERED_OBJECTIVES: [],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {},
        S.LOCATION_ID: 42,
        S.MAP_DATA: {},
        S.IN_COMBAT: False,
        S.TURN_COUNT: 5,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "forest" in ctx.lower() or "Forest" in ctx
    assert "lamp" in ctx
    assert "Score: 10" in ctx

def test_assemble_context_with_history():
    state = State({
        S.GAME_RESPONSE: "You are in a kitchen.",
        S.LOCATION_NAME: "Kitchen",
        S.INVENTORY: [],
        S.SCORE: 5,
        S.ACTION_HISTORY: [
            {"turn": 1, "action": "look", "response": "You see a house."},
            {"turn": 2, "action": "north", "response": "You are in a kitchen."},
        ],
        S.EXITS: ["north", "south"],
        S.DISCOVERED_OBJECTIVES: ["Find the treasure"],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {},
        S.LOCATION_ID: 10,
        S.MAP_DATA: {},
        S.IN_COMBAT: False,
        S.TURN_COUNT: 3,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "look" in ctx
    assert "north" in ctx.lower()
    assert "Find the treasure" in ctx
