from zorkburr.game.jericho_interface import JerichoInterface

def test_start_returns_intro(jericho):
    assert jericho.last_response is not None
    assert "white house" in jericho.last_response.lower()

def test_initial_location(jericho):
    loc_id, loc_name = jericho.get_location()
    assert isinstance(loc_id, int)
    assert loc_id > 0

def test_send_command(jericho):
    response = jericho.send_command("look")
    assert "white house" in response.lower()

def test_get_score(jericho):
    score, max_score = jericho.get_score()
    assert score == 0
    assert max_score > 0

def test_get_inventory(jericho):
    items = jericho.get_inventory()
    assert isinstance(items, list)

def test_deterministic_movement(jericho):
    jericho.send_command("north")
    loc_id, loc_name = jericho.get_location()
    assert isinstance(loc_id, int)

def test_save_restore(jericho):
    saved = jericho.save_state()
    score_before, _ = jericho.get_score()
    jericho.send_command("north")
    jericho.restore_state(saved)
    score_after, _ = jericho.get_score()
    assert score_before == score_after

def test_is_game_over_normal(jericho):
    response = jericho.send_command("look")
    game_over, reason = jericho.is_game_over(response)
    assert game_over is False

def test_get_visible_objects(jericho):
    objects = jericho.get_visible_objects()
    assert isinstance(objects, list)

def test_context_manager():
    with JerichoInterface("roms/zork1.z5") as ji:
        ji.start()
        response = ji.send_command("look")
        assert len(response) > 0
