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
        S.TURNS_SINCE_PROGRESS: 0,
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
        S.DISCOVERED_OBJECTIVES: [
            {"text": "Find the treasure", "location_id": 42, "location_name": "Forest"},
        ],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {},
        S.LOCATION_ID: 10,
        S.MAP_DATA: {},
        S.IN_COMBAT: False,
        S.TURN_COUNT: 3,
        S.TURNS_SINCE_PROGRESS: 0,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "look" in ctx
    assert "north" in ctx.lower()
    assert "Find the treasure" in ctx
    assert "R42" in ctx
    assert "Forest" in ctx

def test_assemble_context_with_map_diagram():
    map_data = {
        "rooms": {"10": "Kitchen", "42": "Forest", "20": "Garden"},
        "connections": {
            "10": {"north": 42, "east": 20},
            "42": {"south": 10},
            "20": {"west": 10},
        },
        "confidence": {"10:north": 2, "42:south": 2, "10:east": 1, "20:west": 1},
        "failures": {},
    }
    state = State({
        S.GAME_RESPONSE: "You are in a kitchen.",
        S.LOCATION_NAME: "Kitchen",
        S.INVENTORY: [],
        S.SCORE: 5,
        S.ACTION_HISTORY: [],
        S.EXITS: ["north", "east"],
        S.DISCOVERED_OBJECTIVES: [],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {},
        S.LOCATION_ID: 10,
        S.MAP_DATA: map_data,
        S.IN_COMBAT: False,
        S.TURN_COUNT: 3,
        S.TURNS_SINCE_PROGRESS: 0,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "## CURRENT WORLD MAP" in ctx
    assert "mermaid" in ctx
    assert "graph LR" in ctx
    assert 'R10' in ctx  # current room node
    assert 'R42' in ctx  # connected room node
    assert "Kitchen" in ctx
    assert "★" in ctx  # current room marker

def test_assemble_context_legacy_string_objectives():
    """Backwards compat: plain string objectives still render."""
    state = State({
        S.GAME_RESPONSE: "test",
        S.LOCATION_NAME: "Test",
        S.INVENTORY: [],
        S.SCORE: 0,
        S.ACTION_HISTORY: [],
        S.EXITS: [],
        S.DISCOVERED_OBJECTIVES: ["Legacy string objective"],
        S.KNOWLEDGE_BASE: "",
        S.MEMORIES_BY_LOCATION: {},
        S.LOCATION_ID: 1,
        S.MAP_DATA: {},
        S.IN_COMBAT: False,
        S.TURN_COUNT: 1,
        S.TURNS_SINCE_PROGRESS: 0,
    })
    _, new_state = assemble_context.run(state)
    ctx = new_state[S.FORMATTED_CONTEXT]
    assert "Legacy string objective" in ctx
