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
    """add_connection should NOT auto-create a reverse edge (was the old buggy behavior).
    Reverse edges are only added when the agent actually travels in the reverse direction.
    """
    mg = MapGraph()
    mg.add_room(10, "West of House")
    mg.add_room(20, "North of House")
    mg.add_connection(10, "north", 20)
    assert "south" not in mg.get_exits(20)


def test_add_connection_does_not_create_reverse_edge():
    """After add_connection(A, south, B), B should not have a north edge back to A.

    One-way passages (chimney, chasm drops, slide) exist in Zork and need to be
    learned from observed movement. The graph must not assume bidirectionality.
    """
    mg = MapGraph()
    mg.add_room(1, "Cellar")
    mg.add_room(2, "East Chasm")

    mg.add_connection(1, "south", 2)

    # Forward edge exists
    assert mg.connections[1].get("south") == 2
    assert mg.connection_confidence[(1, "south")] == 1

    # Reverse edge does NOT exist
    assert "north" not in mg.connections.get(2, {})
    assert mg.connection_confidence.get((2, "north"), 0) == 0


def test_add_connection_bidirectional_observed():
    """When the agent actually travels both directions, both edges should exist.

    Most Zork passages ARE bidirectional — they just need to be learned from
    observed movement in each direction rather than assumed from the forward move.
    """
    mg = MapGraph()
    mg.add_room(1, "Living Room")
    mg.add_room(2, "Kitchen")

    # Agent walks east from Living Room to Kitchen
    mg.add_connection(1, "east", 2)
    # Agent walks west from Kitchen to Living Room
    mg.add_connection(2, "west", 1)

    assert mg.connections[1].get("east") == 2
    assert mg.connections[2].get("west") == 1
    assert mg.connection_confidence[(1, "east")] == 1
    assert mg.connection_confidence[(2, "west")] == 1


def test_shortest_path_respects_one_way():
    """BFS should not use fabricated reverse edges. A one-way trip from A to B
    means you can't get back from B to A unless the reverse has actually been
    observed.
    """
    mg = MapGraph()
    mg.add_room(1, "Cellar")
    mg.add_room(2, "East Chasm")

    mg.add_connection(1, "south", 2)

    # Forward path works
    assert mg.shortest_path(1, 2) == [("south", 2)]

    # Reverse path is NOT reachable (one-way passage)
    assert mg.shortest_path(2, 1) is None

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
