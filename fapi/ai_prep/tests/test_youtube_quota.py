"""
Unit Tests for YouTube Data API Quota Management, Pre-Flight Inspection, and SSE Streaming
"""
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from fapi.ai_prep.clients.youtube_quota_manager import YouTubeQuotaManager, youtube_quota_manager
from fapi.ai_prep.clients.youtube_client import (
    YouTubeClient,
    YouTubeQuotaExceededError,
    YouTubeUploadError,
)
from fapi.ai_prep.core.video_processor_engine.preflight_checker import inspect_youtube_upload_readiness


@pytest.fixture(autouse=True)
def reset_global_quota():
    """Ensure clean quota manager state before each test."""
    youtube_quota_manager.reset_quota()
    yield
    youtube_quota_manager.reset_quota()


def test_quota_manager_initial_state():
    mgr = YouTubeQuotaManager()
    status = mgr.get_quota_status()
    assert status["quota_tracking_enabled"] is True
    assert status["units_used"] == 0
    assert status["units_remaining"] == status["daily_limit_units"]
    assert status["usage_percentage"] == 0.0
    assert status["successful_uploads_today"] == 0
    assert status["is_quota_exceeded"] is False
    assert status["can_upload"] is True


def test_quota_manager_consumption():
    mgr = YouTubeQuotaManager()
    assert mgr.has_sufficient_quota(1600) is True

    mgr.consume_quota(1600)
    status = mgr.get_quota_status()
    assert status["units_used"] == 1600
    assert status["successful_uploads_today"] == 1
    assert status["units_remaining"] == mgr.daily_limit - 1600
    assert status["can_upload"] is True


def test_reserve_then_commit_usage_count():
    """Verify that reserve(1600) followed by commit(token) results in total usage == 1600, NOT 3200."""
    mgr = YouTubeQuotaManager()
    token = mgr.reserve_quota(1600)
    assert token is not None

    # After reservation, units are counted
    status_reserved = mgr.get_quota_status()
    assert status_reserved["units_used"] == 1600
    assert status_reserved["successful_uploads_today"] == 0

    # Commit must NOT add units again (no double counting)
    mgr.commit_quota(reservation_token=token, cost=1600)
    status_committed = mgr.get_quota_status()
    assert status_committed["units_used"] == 1600
    assert status_committed["successful_uploads_today"] == 1


def test_upload_failure_releases_reservation():
    """Verify that releasing a reservation returns usage back to previous value."""
    mgr = YouTubeQuotaManager()
    token = mgr.reserve_quota(1600)
    assert token is not None
    assert mgr.get_quota_status()["units_used"] == 1600

    # Simulate upload failure -> release
    mgr.release_quota(token, cost=1600)
    status = mgr.get_quota_status()
    assert status["units_used"] == 0
    assert status["successful_uploads_today"] == 0


def test_commit_and_release_idempotency():
    """Verify that calling commit or release multiple times for the same token is idempotent."""
    mgr = YouTubeQuotaManager()

    # 1. Commit idempotency
    token1 = mgr.reserve_quota(1600)
    mgr.commit_quota(reservation_token=token1, cost=1600)
    mgr.commit_quota(reservation_token=token1, cost=1600)  # duplicate call
    status1 = mgr.get_quota_status()
    assert status1["units_used"] == 1600
    assert status1["successful_uploads_today"] == 1

    # 2. Release idempotency
    token2 = mgr.reserve_quota(1600)
    assert mgr.get_quota_status()["units_used"] == 3200
    mgr.release_quota(token2, cost=1600)
    mgr.release_quota(token2, cost=1600)  # duplicate call
    status2 = mgr.get_quota_status()
    assert status2["units_used"] == 1600  # released exactly once, not twice


def test_quota_manager_exhaustion():
    mgr = YouTubeQuotaManager()
    # Consume 6 uploads (6 * 1600 = 9600 units)
    for _ in range(6):
        mgr.consume_quota(1600)

    # 9600 used out of 10000 -> 400 remaining. Next 1600 upload should not fit.
    assert mgr.has_sufficient_quota(1600) is False
    status = mgr.get_quota_status()
    assert status["is_quota_exceeded"] is True
    assert status["can_upload"] is False
    assert status["estimated_uploads_remaining"] == 0


def test_quota_manager_mark_exceeded():
    mgr = YouTubeQuotaManager()
    mgr.mark_quota_exceeded()
    assert mgr.has_sufficient_quota() is False
    status = mgr.get_quota_status()
    assert status["is_quota_exceeded"] is True
    assert status["can_upload"] is False


def test_quota_manager_day_rollover():
    mgr = YouTubeQuotaManager()
    mgr.consume_quota(5000)
    assert mgr.get_quota_status()["units_used"] == 5000

    # Simulate date change to yesterday
    mgr._last_reset_date = "2020-01-01"

    # Querying status or quota check should trigger rollover
    status = mgr.get_quota_status()
    assert status["units_used"] == 0
    assert status["successful_uploads_today"] == 0
    assert status["current_date_pt"] != "2020-01-01"


def test_mock_test_upload_does_not_consume_quota():
    """Verify that mock/test uploads do NOT reserve or consume any quota."""
    mgr = YouTubeQuotaManager()
    client = YouTubeClient(quota_manager=mgr)

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 300)
        media_file = tf.name

    try:
        with patch.object(mgr, "reserve_quota", wraps=mgr.reserve_quota) as mock_reserve, \
             patch.object(mgr, "commit_quota", wraps=mgr.commit_quota) as mock_commit:
            res = client.upload_unlisted_media(
                assessment_id=123,
                file_path=media_file,
                media_type="VIDEO",
            )
            assert "youtube_url" in res
            assert mock_reserve.call_count == 0
            assert mock_commit.call_count == 0
            assert mgr.get_quota_status()["units_used"] == 0
            assert mgr.get_quota_status()["successful_uploads_today"] == 0
    finally:
        if os.path.exists(media_file):
            os.remove(media_file)


def test_live_upload_success_exact_reserve_and_commit():
    """Verify that live upload success executes exactly one reserve and one commit, using 1600 units."""
    mgr = YouTubeQuotaManager()
    client = YouTubeClient(quota_manager=mgr)

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 300)
        media_file = tf.name

    try:
        with patch.object(client, "_should_use_mock", return_value=False), \
             patch.object(client, "_upload_live_api", return_value={"video_id": "live123", "youtube_url": "https://youtube.com/watch?v=live123", "status": "unlisted"}), \
             patch.object(mgr, "reserve_quota", wraps=mgr.reserve_quota) as mock_reserve, \
             patch.object(mgr, "commit_quota", wraps=mgr.commit_quota) as mock_commit:
            res = client.upload_unlisted_media(
                assessment_id=456,
                file_path=media_file,
                media_type="VIDEO",
            )
            assert res["video_id"] == "live123"
            assert mock_reserve.call_count == 1
            assert mock_commit.call_count == 1
            status = mgr.get_quota_status()
            assert status["units_used"] == 1600
            assert status["successful_uploads_today"] == 1
    finally:
        if os.path.exists(media_file):
            os.remove(media_file)


def test_youtube_client_quota_rejection():
    # Setup client with isolated quota manager
    mgr = YouTubeQuotaManager()
    client = YouTubeClient(quota_manager=mgr)

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 300)
        media_file = tf.name

    try:
        # Mark quota exceeded
        mgr.mark_quota_exceeded()

        with patch.object(client, "_should_use_mock", return_value=False):
            with pytest.raises(YouTubeQuotaExceededError) as exc_info:
                client.upload_unlisted_media(
                    assessment_id=999,
                    file_path=media_file,
                    media_type="VIDEO",
                )
            assert "quota exceeded" in str(exc_info.value).lower()
    finally:
        if os.path.exists(media_file):
            os.remove(media_file)


def test_preflight_checker_with_quota():
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 600)
        v_path = tf.name

    try:
        # 1. Available quota
        report1 = inspect_youtube_upload_readiness(media_path=v_path, assessment_id=1)
        assert report1["ready_for_upload"] is True
        assert report1["quota_status"]["can_upload"] is True

        # 2. Exceeded quota
        youtube_quota_manager.mark_quota_exceeded()
        report2 = inspect_youtube_upload_readiness(media_path=v_path, assessment_id=1)
        assert report2["ready_for_upload"] is False
        assert "quota is exceeded" in report2["error"]
    finally:
        if os.path.exists(v_path):
            os.remove(v_path)


def test_redis_quota_manager_eval_pipeline():
    """Verify that when Redis is used, Lua eval is called for atomic reserve, commit, release."""
    mgr = YouTubeQuotaManager()
    mock_redis = MagicMock()
    mock_redis.eval.return_value = 1
    mgr._redis_client = mock_redis

    # 1. Reserve
    token = mgr.reserve_quota(1600)
    assert token is not None
    assert mock_redis.eval.called

    # 2. Commit
    mgr.commit_quota(reservation_token=token, cost=1600)
    assert mock_redis.eval.call_count == 2

    # 3. Direct consume
    mgr.consume_quota(1600)
    assert mock_redis.eval.call_count == 3

    # 4. Release
    mgr.release_quota(token, cost=1600)
    assert mock_redis.eval.call_count == 4


@pytest.mark.asyncio
async def test_sse_streaming_generator_short_lived_sessions_and_disconnect():
    """Verify that SSE stream does not hold open long-lived DB sessions and terminates on disconnect."""
    from unittest.mock import AsyncMock
    from fapi.ai_prep.utils.aiprep_utils import stream_assessment_processing_sse_logic
    from fapi.db.models import AuthUserORM

    user = AuthUserORM(id=1, uname="candidate@example.com")
    mock_request = MagicMock()
    # Simulate client disconnect after 2 polls
    mock_request.is_disconnected = AsyncMock(side_effect=[False, False, True])

    with patch("fapi.ai_prep.utils.aiprep_utils.crud.get_assessment_by_id_or_uuid") as mock_get, \
         patch("fapi.ai_prep.utils.aiprep_utils._resolve_candidate_id", return_value=1), \
         patch("fapi.ai_prep.utils.aiprep_utils._fetch_assessment_status_snapshot", return_value=("IN_PROGRESS", None)) as mock_poll:

        mock_assessment = MagicMock()
        mock_assessment.id = 1001
        mock_assessment.candidate_id = 1
        mock_get.return_value = mock_assessment

        streaming_resp = stream_assessment_processing_sse_logic(
            current_user=user,
            assessment_id=1001,
            request=mock_request,
        )

        chunks = []
        async for chunk in streaming_resp.body_iterator:
            chunks.append(chunk)

        # Should yield 2 events and then exit cleanly on disconnect
        assert len(chunks) == 2
        assert mock_poll.call_count == 2
