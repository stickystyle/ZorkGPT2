#!/usr/bin/env python3
# ABOUTME: Local dev server for the ZorkBurr viewer that reads real Burr tracking data.
# ABOUTME: Scans ~/.burr/default/ JSONL logs and serves episode/turn JSON to the viewer UI.
"""Local dev server for the ZorkBurr viewer.

Reads actual episode data from Burr's local tracking logs (~/.burr/default/)
and serves it as JSON endpoints matching the S3 viewer schema.

Run from the project root:

    python scripts/serve_viewer_local.py

Then open http://localhost:8001
"""
import http.server
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8001
PROJECT_ROOT = Path(__file__).parent.parent
VIEWER_DIR = PROJECT_ROOT / "viewer"
BURR_DIR = Path.home() / ".burr" / "default"

# Cache for parsed episode data, keyed by app_id
_episode_cache: dict[str, dict] = {}
# Timestamp of last full scan
_last_scan: float = 0.0
# Scan interval in seconds
SCAN_INTERVAL = 10
# Parsed episode index
_episode_index: dict = {"episodes": [], "current_episode": None}
# Turn data cache: {episode_id: {turn_num: viewer_json}}
_turn_data: dict[str, dict[int, dict]] = {}
# Episode metadata cache: {episode_id: meta_dict}
_episode_meta: dict[str, dict] = {}
# Map from episode_id to app_dir (most recent app_dir wins for dupes)
_episode_to_app: dict[str, Path] = {}


def _state_to_viewer_json(state: dict) -> dict:
    """Convert a Burr state dict into viewer-compatible JSON.

    Mirrors the structure from zorkburr/viewer/state_export.py but works
    with raw dicts from the JSONL logs instead of Burr State objects.
    """
    location_id = state.get("location_id", 0)
    memories_by_loc = state.get("memories_by_location", {})
    memories_here = (
        memories_by_loc.get(str(location_id), [])
        or memories_by_loc.get(location_id, [])
        or []
    )

    map_data = state.get("map_data", {}) or {}
    rooms = map_data.get("rooms", {})
    connections = map_data.get("connections", {})

    str_rooms = {str(k): v for k, v in rooms.items()}
    str_connections = {str(k): v for k, v in connections.items()}

    raw_confidence = map_data.get("confidence", {})
    str_confidence = {}
    for k, v in (raw_confidence or {}).items():
        if isinstance(k, (list, tuple)):
            str_confidence[f"{k[0]}:{k[1]}"] = v
        else:
            str_confidence[str(k)] = v

    action_history = state.get("action_history", [])
    recent = action_history[-50:] if len(action_history) > 50 else list(action_history)

    return {
        "metadata": {
            "episode_id": state.get("episode_id", ""),
            "turn": state.get("turn_count", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "game_over": state.get("game_over", False),
            "game_over_reason": state.get("game_over_reason", ""),
            "score": state.get("score", 0),
            "max_score": state.get("max_score", 350),
        },
        "turn_data": {
            "action": state.get("action_to_take", ""),
            "game_response": state.get("game_response", ""),
            "agent_reasoning": state.get("agent_reasoning", ""),
            "critic_score": state.get("critic_score", 0.0),
            "critic_justification": state.get("critic_justification", ""),
            "critic_confidence": state.get("critic_confidence", 0.0),
            "was_overridden": state.get("was_overridden", False),
            "rejection_count": state.get("rejection_count", 0),
        },
        "game_state": {
            "location_name": state.get("location_name", ""),
            "location_id": location_id,
            "inventory": state.get("inventory", []),
            "exits": state.get("exits", []),
            "in_combat": state.get("in_combat", False),
            "visible_objects": state.get("visible_objects", []),
            "turns_since_progress": state.get("turns_since_progress", 0),
        },
        "strategic": {
            "discovered_objectives": state.get("discovered_objectives", []),
            "completed_objectives": state.get("completed_objectives", []),
            "knowledge_base": state.get("knowledge_base", ""),
            "memories_at_location": memories_here,
        },
        "map": {
            "rooms": str_rooms,
            "connections": str_connections,
            "confidence": str_confidence,
            "current_room": location_id,
            "visited_count": len(state.get("visited_locations", [])),
            "total_rooms": len(str_rooms),
        },
        "recent_history": recent,
    }


def _parse_burr_log(app_dir: Path) -> tuple[str, list[tuple[int, dict, str]]]:
    """Parse a Burr log.jsonl and extract record_results turns.

    Returns (episode_id, [(turn_num, viewer_json, timestamp), ...])
    """
    log_file = app_dir / "log.jsonl"
    if not log_file.exists():
        return "", []

    episode_id = ""
    turns = []
    last_timestamp = ""

    with open(log_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") != "end_entry":
                continue

            state = entry.get("state", {})
            if not episode_id:
                episode_id = state.get("episode_id", "")

            # record_results marks a completed turn
            if entry.get("action") == "record_results":
                turn_num = state.get("turn_count", 0)
                viewer_json = _state_to_viewer_json(state)
                timestamp = entry.get("end_time", "")
                turns.append((turn_num, viewer_json, timestamp))
                last_timestamp = timestamp

    return episode_id, turns


def _scan_episodes():
    """Scan all Burr tracking dirs and rebuild the episode index."""
    global _last_scan, _episode_index, _turn_data, _episode_meta, _episode_to_app

    if not BURR_DIR.exists():
        return

    now = time.time()
    if now - _last_scan < SCAN_INTERVAL:
        return
    _last_scan = now

    episodes_info = {}  # episode_id -> {meta fields}
    new_turn_data: dict[str, dict[int, dict]] = {}
    new_episode_to_app: dict[str, Path] = {}

    for app_dir in sorted(BURR_DIR.iterdir()):
        if not app_dir.is_dir():
            continue

        episode_id, turns = _parse_burr_log(app_dir)
        if not episode_id or not turns:
            continue

        # If we already saw this episode_id, pick the one with more turns
        if episode_id in new_turn_data and len(turns) <= len(new_turn_data[episode_id]):
            continue

        new_episode_to_app[episode_id] = app_dir
        new_turn_data[episode_id] = {}
        for turn_num, viewer_json, timestamp in turns:
            new_turn_data[episode_id][turn_num] = viewer_json

        last_turn_num, last_viewer, last_ts = turns[-1]
        game_over = last_viewer["metadata"].get("game_over", False)

        # Determine status: use log mtime to detect stopped episodes
        if game_over:
            status = "completed"
        else:
            log_mtime = (app_dir / "log.jsonl").stat().st_mtime
            stale_seconds = time.time() - log_mtime
            status = "running" if stale_seconds < 300 else "stopped"

        episodes_info[episode_id] = {
            "episode_id": episode_id,
            "started_at": turns[0][2] if turns else "",
            "status": status,
            "turn_count": last_turn_num,
            "score": last_viewer["metadata"].get("score", 0),
            "end_reason": last_viewer["metadata"].get("game_over_reason", "") or None,
        }

    # Sort episodes naturally: ep01, ep02, ep02b, ep03, ...
    def sort_key(ep_id):
        match = re.match(r"ep(\d+)(.*)", ep_id)
        if match:
            return (int(match.group(1)), match.group(2))
        return (999, ep_id)

    sorted_ids = sorted(episodes_info.keys(), key=sort_key)
    sorted_episodes = [episodes_info[eid] for eid in sorted_ids]

    # Find current (most recently running, or last completed)
    running = [e for e in sorted_episodes if e["status"] == "running"]
    current = running[-1]["episode_id"] if running else (sorted_ids[-1] if sorted_ids else None)

    _episode_index = {
        "episodes": sorted_episodes,
        "current_episode": current,
    }
    _turn_data = new_turn_data
    _episode_to_app = new_episode_to_app

    # Build episode meta
    _episode_meta = {}
    for eid, info in episodes_info.items():
        _episode_meta[eid] = {
            "episode_id": eid,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": info["status"],
            "turn_count": info["turn_count"],
            "score": info["score"],
            "max_score": 350,
            "end_reason": info["end_reason"],
        }


def _get_local_ip() -> str:
    """Return this machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def do_GET(self):
        # Trigger periodic rescan
        _scan_episodes()

        if self.path == "/live/current_state.json":
            self._serve_live_state()
        elif self.path == "/episodes/index.json":
            self._json_response(_episode_index)
        elif self.path.endswith("/meta.json"):
            self._serve_episode_meta()
        elif "/turns/turn_" in self.path:
            self._serve_turn()
        else:
            super().do_GET()

    def _serve_live_state(self):
        current = _episode_index.get("current_episode")
        if not current or current not in _turn_data:
            self._json_response({"error": "no episodes found"}, status=404)
            return
        turns = _turn_data[current]
        if not turns:
            self._json_response({"error": "no turns"}, status=404)
            return
        max_turn = max(turns.keys())
        self._json_response(turns[max_turn])

    def _serve_episode_meta(self):
        # Path: /episodes/{episode_id}/meta.json
        parts = self.path.strip("/").split("/")
        if len(parts) >= 2:
            episode_id = parts[1]
            if episode_id in _episode_meta:
                self._json_response(_episode_meta[episode_id])
                return
        self._json_response({"error": "not found"}, status=404)

    def _serve_turn(self):
        # Path: /episodes/{episode_id}/turns/turn_{N}.json
        parts = self.path.strip("/").split("/")
        if len(parts) >= 4:
            episode_id = parts[1]
            turn_file = parts[3]  # turn_N.json
            match = re.match(r"turn_(\d+)\.json", turn_file)
            if match and episode_id in _turn_data:
                turn_num = int(match.group(1))
                if turn_num in _turn_data[episode_id]:
                    self._json_response(_turn_data[episode_id][turn_num])
                    return
        self._json_response({"error": "not found"}, status=404)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Only log errors
        if args and "404" in str(args[0]):
            super().log_message(format, *args)


if __name__ == "__main__":
    print(f"Scanning Burr tracking data in {BURR_DIR} ...")
    _scan_episodes()
    ep_count = len(_episode_index["episodes"])
    total_turns = sum(len(t) for t in _turn_data.values())
    print(f"Found {ep_count} episodes, {total_turns} total turns")
    for ep in _episode_index["episodes"]:
        print(f"  {ep['episode_id']}: {ep['turn_count']} turns, score {ep['score']}, {ep['status']}")

    with http.server.HTTPServer((HOST, PORT), ViewerHandler) as server:
        local_ip = _get_local_ip()
        print(f"\nZorkBurr Viewer:")
        print(f"  Local:   http://localhost:{PORT}")
        print(f"  Network: http://{local_ip}:{PORT}")
        print(f"Rescans every {SCAN_INTERVAL}s for new data. Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
