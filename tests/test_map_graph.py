from zorkburr.game.map_graph import MapGraph

def test_add_room():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    assert mg.has_room(10)
    assert mg.get_room_name(10) == "West of House"

def test_add_connection():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "North of House")
    mg.add_connection(10, "north", 20)
    assert mg.get_exits(10).get("north") == 20

def test_reverse_connection():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "North of House")
    mg.add_connection(10, "north", 20)
    assert "south" in mg.get_exits(20)

def test_track_exit_failure():
    mg = MapGraph()
    mg.add_room(10, "West")
    mg.track_exit_failure(10, "up")
    mg.track_exit_failure(10, "up")
    mg.track_exit_failure(10, "up")
    assert mg.get_exit_failures(10, "up") == 3

def test_serialize_deserialize():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "Forest")
    mg.add_connection(10, "north", 20)
    data = mg.to_dict()
    mg2 = MapGraph.from_dict(data)
    assert mg2.has_room(10)
    assert mg2.get_exits(10)["north"] == 20

def test_get_context_for_prompt():
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "Forest")
    mg.add_connection(10, "north", 20)
    ctx = mg.get_context_for_prompt(10)
    assert "north" in ctx.lower()
    assert "Forest" in ctx
