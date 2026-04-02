"""Spatial map graph: rooms, connections, confidence tracking."""
from __future__ import annotations
from collections import defaultdict
from typing import Optional

_OPPOSITE_DIRS = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up", "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
}
_DIR_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up", "d": "down", "ne": "northeast", "nw": "northwest",
    "se": "southeast", "sw": "southwest",
    "go north": "north", "go south": "south", "go east": "east",
    "go west": "west", "go up": "up", "go down": "down",
}

def normalize_direction(action_str: str) -> Optional[str]:
    action_str = action_str.lower().strip()
    if action_str in _DIR_ALIASES:
        return _DIR_ALIASES[action_str]
    if action_str in _OPPOSITE_DIRS:
        return action_str
    return None

class MapGraph:
    def __init__(self):
        self.rooms: dict[int, str] = {}
        self.connections: dict[int, dict[str, int]] = defaultdict(dict)
        self.connection_confidence: dict[tuple[int, str], int] = defaultdict(int)
        self.exit_failures: dict[tuple[int, str], int] = defaultdict(int)

    def add_room(self, room_id: int, name: str) -> None:
        self.rooms[room_id] = name

    def has_room(self, room_id: int) -> bool:
        return room_id in self.rooms

    def get_room_name(self, room_id: int) -> str:
        return self.rooms.get(room_id, "Unknown")

    def add_connection(self, from_id: int, direction: str, to_id: int) -> None:
        direction = normalize_direction(direction) or direction
        self.connections[from_id][direction] = to_id
        self.connection_confidence[(from_id, direction)] += 1
        opposite = _OPPOSITE_DIRS.get(direction)
        if opposite:
            self.connections[to_id][opposite] = from_id
            self.connection_confidence[(to_id, opposite)] += 1

    def get_exits(self, room_id: int) -> dict[str, int]:
        return dict(self.connections.get(room_id, {}))

    def track_exit_failure(self, room_id: int, direction: str) -> None:
        direction = normalize_direction(direction) or direction
        self.exit_failures[(room_id, direction)] += 1

    def get_exit_failures(self, room_id: int, direction: str) -> int:
        direction = normalize_direction(direction) or direction
        return self.exit_failures.get((room_id, direction), 0)

    def get_context_for_prompt(self, current_room_id: int) -> str:
        lines = []
        room_name = self.get_room_name(current_room_id)
        lines.append(f"**Current Room:** {room_name}")
        exits = self.get_exits(current_room_id)
        if exits:
            lines.append("**Known Exits from here:**")
            for direction, dest_id in sorted(exits.items()):
                dest_name = self.get_room_name(dest_id)
                conf = self.connection_confidence.get((current_room_id, direction), 0)
                lines.append(f"  {direction} -> {dest_name} (verified {conf}x)")
        else:
            lines.append("**No mapped exits from here yet.**")
        return "\n".join(lines)

    def to_mermaid(self, current_room_id: int | None = None) -> str:
        """Generate a Mermaid flowchart of the known map."""
        if not self.rooms:
            return ""
        lines = ["graph LR"]
        for room_id, name in sorted(self.rooms.items()):
            if room_id == current_room_id:
                lines.append(f'    R{room_id}[["**{name}** ★"]]')
            else:
                lines.append(f'    R{room_id}["{name}"]')
        seen: set[tuple[int, int, str]] = set()
        for from_id, exits in sorted(self.connections.items()):
            for direction, to_id in sorted(exits.items()):
                edge_key = (min(from_id, to_id), max(from_id, to_id), direction)
                reverse_dir = _OPPOSITE_DIRS.get(direction, "")
                reverse_key = (min(from_id, to_id), max(from_id, to_id), reverse_dir)
                if edge_key not in seen and reverse_key not in seen:
                    lines.append(f'    R{from_id} -->|"{direction}"| R{to_id}')
                    seen.add(edge_key)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "rooms": {str(k): v for k, v in self.rooms.items()},
            "connections": {str(k): {d: int(dest) for d, dest in v.items()} for k, v in self.connections.items()},
            "confidence": {f"{k[0]}:{k[1]}": v for k, v in self.connection_confidence.items()},
            "failures": {f"{k[0]}:{k[1]}": v for k, v in self.exit_failures.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> MapGraph:
        mg = cls()
        mg.rooms = {int(k): v for k, v in data.get("rooms", {}).items()}
        for room_str, exits in data.get("connections", {}).items():
            for direction, dest_id in exits.items():
                mg.connections[int(room_str)][direction] = int(dest_id)
        for key, count in data.get("confidence", {}).items():
            room_str, direction = key.split(":", 1)
            mg.connection_confidence[(int(room_str), direction)] = count
        for key, count in data.get("failures", {}).items():
            room_str, direction = key.split(":", 1)
            mg.exit_failures[(int(room_str), direction)] = count
        return mg
