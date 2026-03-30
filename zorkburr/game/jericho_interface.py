"""Clean wrapper around Jericho FrotzEnv for Z-machine interaction."""
from __future__ import annotations
import logging
from typing import Optional
import jericho

logger = logging.getLogger(__name__)

class JerichoInterface:
    def __init__(self, game_file: str):
        self.game_file = game_file
        self.env: Optional[jericho.FrotzEnv] = None
        self.last_response: str = ""

    def start(self) -> str:
        self.env = jericho.FrotzEnv(self.game_file)
        intro, _ = self.env.reset()
        self.last_response = intro
        verbose_response, _, _, _ = self.env.step("verbose")
        return intro

    def send_command(self, command: str) -> str:
        assert self.env is not None, "Call start() first"
        response, _, _, _ = self.env.step(command)
        self.last_response = response
        return response

    def get_location(self) -> tuple[int, str]:
        assert self.env is not None
        player = self.env.get_player_object()
        parent_id = player.parent if player else None
        if parent_id:
            world_objects = self.env.get_world_objects()
            parent_obj = next((o for o in world_objects if o.num == parent_id), None)
            if parent_obj:
                return parent_obj.num, parent_obj.name
        return 0, "Unknown"

    def get_score(self) -> tuple[int, int]:
        assert self.env is not None
        score = self.env.get_score()
        # Jericho 3.3+ get_score() returns a single int; max score from bindings
        if isinstance(score, tuple):
            return score
        try:
            max_score = self.env.get_max_score()
        except AttributeError:
            # Derive max score from step info if available
            max_score = 350  # Zork 1 max score
        return score, max_score

    def get_inventory(self) -> list[str]:
        assert self.env is not None
        player = self.env.get_player_object()
        if not player or not player.child:
            return []
        world_objects = self.env.get_world_objects()
        obj_by_num = {o.num: o for o in world_objects}
        items = []
        child_id = player.child
        while child_id:
            child_obj = obj_by_num.get(child_id)
            if not child_obj:
                break
            items.append(child_obj.name)
            child_id = child_obj.sibling
        return items

    def get_visible_objects(self) -> list[dict]:
        assert self.env is not None
        loc_id, _ = self.get_location()
        result = []
        world_objects = self.env.get_world_objects()
        obj_by_num = {o.num: o for o in world_objects}
        for obj in world_objects:
            if obj.parent and obj.parent == loc_id and obj.name != "cretin":
                result.append({"name": obj.name, "num": obj.num})
                child_id = obj.child
                while child_id:
                    child_obj = obj_by_num.get(child_id)
                    if not child_obj:
                        break
                    result.append({"name": child_obj.name, "num": child_obj.num})
                    child_id = child_obj.sibling
        return result

    def save_state(self) -> tuple:
        assert self.env is not None
        return self.env.get_state()

    def restore_state(self, state: tuple) -> None:
        assert self.env is not None
        self.env.set_state(state)

    def is_game_over(self, response: str) -> tuple[bool, str]:
        assert self.env is not None
        if self.env.game_over():
            if self.env.victory():
                return True, "victory"
            return True, "death"
        return False, ""

    def close(self) -> None:
        if self.env is not None:
            self.env.close()
            self.env = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
