"""Burr lifecycle hook that uploads turn state to S3 for the live viewer."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from burr.core import State
from burr.lifecycle import PostRunStepHook

from zorkburr.state import S
from zorkburr.viewer.state_export import export_turn_state

logger = logging.getLogger(__name__)


class S3ViewerHook(PostRunStepHook):
    """Uploads turn state to S3 after each record_results action."""

    def __init__(self, bucket: str, prefix: str = ""):
        self.bucket = bucket
        self.prefix = prefix
        self.s3 = boto3.client("s3")

    def post_run_step(
        self,
        *,
        state: State,
        action: Any,
        result: Optional[Dict[str, Any]],
        exception: Optional[Exception],
        app_id: str,
        partition_key: str,
        sequence_id: int,
        **future_kwargs: Any,
    ) -> None:
        if action.name != "record_results" or exception:
            return

        try:
            self._upload_turn(state)
        except Exception:
            logger.exception("Failed to upload turn state to S3")

    def _upload_turn(self, state: State) -> None:
        episode_id = state[S.EPISODE_ID]
        turn = state[S.TURN_COUNT]
        exported = export_turn_state(state)
        json_bytes = json.dumps(exported).encode()

        # 1. Live state (overwritten each turn)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{self.prefix}live/current_state.json",
            Body=json_bytes,
            ContentType="application/json",
            CacheControl="no-cache, max-age=0",
        )

        # 2. Immutable turn snapshot
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{self.prefix}episodes/{episode_id}/turns/turn_{turn}.json",
            Body=json_bytes,
            ContentType="application/json",
            CacheControl="public, max-age=31536000, immutable",
        )

        # 3. Episode metadata (updated each turn)
        now = datetime.now(timezone.utc).isoformat()
        game_over = state[S.GAME_OVER]
        meta = {
            "episode_id": episode_id,
            "updated_at": now,
            "status": "completed" if game_over else "running",
            "turn_count": turn,
            "score": state[S.SCORE],
            "max_score": state[S.MAX_SCORE],
            "end_reason": state[S.GAME_OVER_REASON] if game_over else None,
        }
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{self.prefix}episodes/{episode_id}/meta.json",
            Body=json.dumps(meta).encode(),
            ContentType="application/json",
            CacheControl="no-cache, max-age=0",
        )

        # 4. Update episode index every turn so scores stay current
        # (episodes that hit max_turns never set game_over, so we
        #  can't rely on only updating at turn 1 and game_over)
        self._update_episode_index(meta, now)

    def _update_episode_index(self, episode_meta: dict, now: str) -> None:
        index_key = f"{self.prefix}episodes/index.json"

        # Try to load existing index
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=index_key)
            index = json.loads(resp["Body"].read())
        except Exception:
            index = {"episodes": [], "current_episode": None}

        # Update or add episode entry
        episodes = index["episodes"]
        existing = [e for e in episodes if e["episode_id"] == episode_meta["episode_id"]]
        entry = {
            "episode_id": episode_meta["episode_id"],
            "started_at": episode_meta.get("started_at", now),
            "status": episode_meta["status"],
            "turn_count": episode_meta["turn_count"],
            "score": episode_meta["score"],
            "end_reason": episode_meta.get("end_reason"),
        }
        if existing:
            idx = episodes.index(existing[0])
            entry["started_at"] = existing[0].get("started_at", now)
            episodes[idx] = entry
        else:
            entry["started_at"] = now
            episodes.insert(0, entry)

        index["current_episode"] = episode_meta["episode_id"]

        self.s3.put_object(
            Bucket=self.bucket,
            Key=index_key,
            Body=json.dumps(index).encode(),
            ContentType="application/json",
            CacheControl="no-cache, max-age=0",
        )
