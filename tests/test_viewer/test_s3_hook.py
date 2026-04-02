"""Tests for S3 viewer upload hook."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

from burr.core import State

from zorkburr.state import S, create_initial_state
from zorkburr.viewer.s3_hook import S3ViewerHook


def _make_state(**overrides) -> State:
    """Create a state with sensible defaults for testing."""
    state = create_initial_state("test-ep")
    defaults = {
        S.TURN_COUNT: 1,
        S.SCORE: 10,
        S.MAX_SCORE: 350,
        S.LOCATION_NAME: "West of House",
        S.LOCATION_ID: 180,
        S.ACTION_TO_TAKE: "look",
        S.GAME_RESPONSE: "You are standing in an open field.",
        S.GAME_OVER: False,
    }
    defaults.update(overrides)
    return state.update(**defaults)


def _mock_action(name: str) -> MagicMock:
    """Create a mock Burr action with a given name."""
    action = MagicMock()
    action.name = name
    return action


class TestHookOnlyUploadsAfterRecordResults:
    """Hook should only upload after the record_results action."""

    def test_uploads_after_record_results(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="test-bucket")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={"moved": False, "score_delta": 0},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        assert mock_s3.put_object.call_count >= 1

    def test_skips_upload_for_other_actions(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="test-bucket")
            state = _make_state()
            for action_name in ["generate_action", "evaluate_action", "execute_action",
                                "extract_info", "assemble_context", "record_memory"]:
                hook.post_run_step(
                    state=state,
                    action=_mock_action(action_name),
                    result={},
                    exception=None,
                    app_id="test",
                    partition_key="default",
                    sequence_id=1,
                )
        assert mock_s3.put_object.call_count == 0

    def test_skips_upload_on_exception(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="test-bucket")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result=None,
                exception=RuntimeError("something broke"),
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        assert mock_s3.put_object.call_count == 0


class TestS3Keys:
    """Verify correct S3 key paths and cache control headers."""

    def test_uploads_four_objects_on_middle_turn(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 10})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        # 4 uploads: live state, turn snapshot, episode meta, index (updated every turn)
        assert mock_s3.put_object.call_count == 4

    def test_uploads_four_objects_on_first_turn(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 1})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        # 4 uploads: live state, turn snapshot, episode meta, + index
        assert mock_s3.put_object.call_count == 4

    def test_live_state_key_and_cache(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        calls = mock_s3.put_object.call_args_list
        live_call = [c for c in calls if c.kwargs.get("Key", "") == "live/current_state.json"]
        assert len(live_call) == 1
        assert "no-cache" in live_call[0].kwargs["CacheControl"]

    def test_turn_snapshot_key_and_cache(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 5})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        calls = mock_s3.put_object.call_args_list
        snap_call = [c for c in calls
                     if "episodes/test-ep/turns/turn_5.json" in c.kwargs.get("Key", "")]
        assert len(snap_call) == 1
        assert "immutable" in snap_call[0].kwargs["CacheControl"]

    def test_episode_meta_key(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        calls = mock_s3.put_object.call_args_list
        meta_call = [c for c in calls
                     if "episodes/test-ep/meta.json" in c.kwargs.get("Key", "")]
        assert len(meta_call) == 1

    def test_prefix_applied_to_all_keys(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket", prefix="zorkburr/")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        calls = mock_s3.put_object.call_args_list
        for c in calls:
            assert c.kwargs["Key"].startswith("zorkburr/"), f"Key {c.kwargs['Key']} missing prefix"


class TestEpisodeIndex:
    """Episode index should be updated on first turn and game over."""

    def test_index_updated_on_first_turn(self):
        mock_s3 = MagicMock()
        # Return empty index when first fetched
        mock_s3.get_object.side_effect = mock_s3.exceptions.NoSuchKey = type(
            "NoSuchKey", (Exception,), {}
        )
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 1})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        # Should have an index upload in addition to the 3 regular uploads
        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "episodes/index.json" in keys

    def test_index_updated_on_game_over(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 50, S.GAME_OVER: True, S.GAME_OVER_REASON: "victory"})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "episodes/index.json" in keys

    def test_index_updated_on_middle_turns(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 10, S.GAME_OVER: False})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "episodes/index.json" in keys


class TestErrorHandling:
    """S3 failures should be logged and swallowed, never crash the game."""

    def test_s3_error_does_not_raise(self):
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 is down")
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state()
            # Should not raise
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )


class TestUploadContent:
    """Verify the content of uploads is valid JSON with expected structure."""

    def test_live_state_is_valid_export(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state()
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        live_call = [c for c in mock_s3.put_object.call_args_list
                     if c.kwargs["Key"] == "live/current_state.json"][0]
        body = json.loads(live_call.kwargs["Body"])
        assert "metadata" in body
        assert "turn_data" in body
        assert body["metadata"]["episode_id"] == "test-ep"

    def test_episode_meta_has_expected_fields(self):
        mock_s3 = MagicMock()
        with patch("zorkburr.viewer.s3_hook.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3
            hook = S3ViewerHook(bucket="my-bucket")
            state = _make_state(**{S.TURN_COUNT: 5, S.SCORE: 25})
            hook.post_run_step(
                state=state,
                action=_mock_action("record_results"),
                result={},
                exception=None,
                app_id="test",
                partition_key="default",
                sequence_id=1,
            )
        meta_call = [c for c in mock_s3.put_object.call_args_list
                     if "meta.json" in c.kwargs["Key"]][0]
        meta = json.loads(meta_call.kwargs["Body"])
        assert meta["episode_id"] == "test-ep"
        assert meta["turn_count"] == 5
        assert meta["score"] == 25
        assert "status" in meta
