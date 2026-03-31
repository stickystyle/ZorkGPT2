#!/usr/bin/env python3
"""Local dev server for testing the viewer with sample data.

Serves viewer/index.html and generates sample JSON endpoints so you can
test the UI without AWS. Run from the project root:

    python scripts/serve_viewer_local.py

Then open http://localhost:8001
"""
import http.server
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PORT = 8001
PROJECT_ROOT = Path(__file__).parent.parent
VIEWER_DIR = PROJECT_ROOT / "viewer"

# Sample data that mimics what the S3 hook uploads
SAMPLE_STATE = {
    "metadata": {
        "episode_id": "demo-ep",
        "turn": 5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "game_over": False,
        "game_over_reason": "",
        "score": 10,
        "max_score": 350,
    },
    "turn_data": {
        "action": "open mailbox",
        "game_response": "Opening the small mailbox reveals a leaflet.",
        "agent_reasoning": "The mailbox is the only interactable object at this location. Opening it might reveal useful items or clues.",
        "critic_score": 0.82,
        "critic_justification": "Good exploration action - investigating available objects.",
        "critic_confidence": 0.9,
        "was_overridden": False,
        "rejection_count": 0,
    },
    "game_state": {
        "location_name": "West of House",
        "location_id": 180,
        "inventory": ["leaflet"],
        "exits": ["north", "south", "west"],
        "in_combat": False,
        "visible_objects": [],
        "turns_since_progress": 0,
    },
    "strategic": {
        "discovered_objectives": ["Explore the house", "Find the trapdoor", "Collect treasures"],
        "completed_objectives": [{"objective": "Open the mailbox", "completed_turn": 2}],
        "knowledge_base": "## Zork I Strategic Guide\n\n### Key Locations\n- **West of House**: Starting area. Mailbox contains a leaflet.\n- **North of House**: Path continues.\n\n### Tips\n- Always check containers for items\n- Map your surroundings carefully",
        "memories_at_location": [
            {"category": "DISCOVERY", "title": "Leaflet in mailbox", "text": "Found a leaflet inside the mailbox with game instructions."},
        ],
    },
    "map": {
        "rooms": {"180": "West of House", "181": "North of House", "182": "South of House"},
        "connections": {"180": {"north": "181", "south": "182"}},
        "confidence": {},
        "current_room": 180,
        "visited_count": 3,
        "total_rooms": 3,
    },
    "recent_history": [
        {"turn": 1, "action": "look", "response": "You are standing in an open field west of a white house.", "score": 0},
        {"turn": 2, "action": "examine mailbox", "response": "The small mailbox is closed.", "score": 0},
        {"turn": 3, "action": "open mailbox", "response": "Opening the small mailbox reveals a leaflet.", "score": 5},
        {"turn": 4, "action": "take leaflet", "response": "Taken.", "score": 5},
        {"turn": 5, "action": "go north", "response": "North of House", "score": 10},
    ],
}

SAMPLE_INDEX = {
    "episodes": [
        {"episode_id": "demo-ep", "started_at": "2026-03-30T10:00:00+00:00", "status": "running", "turn_count": 5, "score": 10, "end_reason": None},
        {"episode_id": "old-ep", "started_at": "2026-03-29T08:00:00+00:00", "status": "completed", "turn_count": 100, "score": 45, "end_reason": "max_turns"},
    ],
    "current_episode": "demo-ep",
}

SAMPLE_META = {
    "episode_id": "demo-ep",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "status": "running",
    "turn_count": 5,
    "score": 10,
    "max_score": 350,
    "end_reason": None,
}


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def do_GET(self):
        if self.path == '/live/current_state.json':
            self._json_response(SAMPLE_STATE)
        elif self.path == '/episodes/index.json':
            self._json_response(SAMPLE_INDEX)
        elif self.path.endswith('/meta.json'):
            self._json_response(SAMPLE_META)
        elif '/turns/turn_' in self.path:
            # Return sample state for any turn request
            self._json_response(SAMPLE_STATE)
        else:
            super().do_GET()

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quieter logging
        pass


if __name__ == '__main__':
    with http.server.HTTPServer(('', PORT), ViewerHandler) as server:
        print(f"ZorkBurr Viewer dev server: http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
