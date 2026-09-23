"""
Unit Tests for YouTube Data API Quota Management & Pre-Flight Inspection
"""
import os
import tempfile
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


def test_redis_quota_manager_direct_consume():
    """Verify that when Redis is used, direct consumption charges units and uploads atomically."""
    from unittest.mock import MagicMock
    mgr = YouTubeQuotaManager()
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mgr._redis_client = mock_redis

    # Direct commit without prior reservation
    mgr.commit_quota(reservation_token=None, cost=1600)

    assert mock_redis.pipeline.called
    assert mock_pipe.incrby.call_count == 2  # 1 for uploads, 1 for units
    assert mock_pipe.execute.called
