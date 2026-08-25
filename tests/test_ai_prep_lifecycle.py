import os
import shutil
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AssessmentTypeEnum,
    AssessmentModeEnum,
    AssessmentStatusEnum,
    AiPrepMediaFileORM,
)
from fapi.ai_prep.services.storage_service import LocalStorageBackend
from fapi.ai_prep.services.media_service import MediaService
from fapi.ai_prep.services.youtube_service import YouTubeQuotaExceededException
from tests.conftest import TestingSessionLocal


@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp(prefix="aiprep_lifecycle_test_storage_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sse_processing_status_streaming(client, db_session, candidate_db_user, candidate_headers):
    candidate = candidate_db_user["candidate"]

    assessment = AiPrepAssessmentORM(
        candidate_id=candidate.id,
        assessment_type=AssessmentTypeEnum.TECHNICAL,
        assessment_mode=AssessmentModeEnum.VIDEO_AUDIO,
        status=AssessmentStatusEnum.COMPLETED,
        attempt_number=1,
    )
    db_session.add(assessment)
    db_session.commit()

    # Request SSE stream
    response = client.get(
        f"/api/ai-prep/assessments/{assessment.id}/processing-status?stream=true",
        headers=candidate_headers
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "event: complete" in response.text
    assert "data: {" in response.text


def test_storage_lifecycle_orphan_chunks_and_90_day_purge(db_session, candidate_db_user, temp_storage_dir):
    candidate = candidate_db_user["candidate"]
    backend = LocalStorageBackend(temp_storage_dir)

    # 1. Create an old completed assessment (100 days old)
    old_date = datetime.utcnow() - timedelta(days=100)
    old_ass = AiPrepAssessmentORM(
        candidate_id=candidate.id,
        assessment_type=AssessmentTypeEnum.TECHNICAL,
        assessment_mode=AssessmentModeEnum.VIDEO_AUDIO,
        status=AssessmentStatusEnum.COMPLETED,
        attempt_number=1,
        created_at=old_date,
        completed_at=old_date,
    )
    db_session.add(old_ass)
    db_session.commit()
    db_session.refresh(old_ass)

    # Put mock audio and chunks in storage
    audio_path = f"ai-prep/{candidate.id}/{old_ass.id}/audio.wav"
    compressed_path = f"ai-prep/{candidate.id}/{old_ass.id}/audio_compressed.opus"
    chunk_path = f"ai-prep/{candidate.id}/{old_ass.id}/chunks/0.webm"

    backend.upload_bytes(audio_path, b"old_raw_audio")
    backend.upload_bytes(compressed_path, b"old_compressed_audio")
    backend.upload_bytes(chunk_path, b"old_chunk")

    media = AiPrepMediaFileORM(
        assessment_id=old_ass.id,
        audio_file_path=audio_path,
        video_file_path="https://www.youtube.com/watch?v=yt_old_123",
        duration_seconds=60,
        file_size_bytes=10000
    )
    db_session.add(media)
    db_session.commit()

    assert backend.file_exists(audio_path) is True
    assert backend.file_exists(chunk_path) is True

    # Run cleanup with 90-day retention
    media_service = MediaService(storage_backend=backend)
    res = media_service.cleanup_expired_media(retention_days=90, orphan_chunk_hours=24, db=db_session)

    assert res["status"] == "success"
    assert res["orphaned_chunks_purged"] >= 1
    assert res["expired_audio_purged"] >= 1

    # Verify expired heavy files were deleted
    assert backend.file_exists(audio_path) is False
    assert backend.file_exists(compressed_path) is False
    assert backend.file_exists(chunk_path) is False


def test_admin_cleanup_expired_endpoint_authorization(client, candidate_headers, admin_headers, temp_storage_dir):
    backend = LocalStorageBackend(temp_storage_dir)

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend):
        # Candidate should be rejected with 403 Forbidden
        cand_resp = client.post("/api/ai-prep/media/cleanup-expired", headers=candidate_headers)
        assert cand_resp.status_code == 403

        # Admin should succeed
        admin_resp = client.post("/api/ai-prep/media/cleanup-expired", headers=admin_headers)
        assert admin_resp.status_code == 200
        assert admin_resp.json()["status"] == "success"


def test_youtube_worker_max_retries_quota_fallback(db_session, candidate_db_user, temp_storage_dir):
    candidate = candidate_db_user["candidate"]
    backend = LocalStorageBackend(temp_storage_dir)

    assessment = AiPrepAssessmentORM(
        candidate_id=candidate.id,
        assessment_type=AssessmentTypeEnum.TECHNICAL,
        assessment_mode=AssessmentModeEnum.VIDEO_AUDIO,
        status=AssessmentStatusEnum.PROCESSING,
        attempt_number=1,
    )
    db_session.add(assessment)
    db_session.commit()

    video_path = f"ai-prep/{candidate.id}/{assessment.id}/full.webm"
    backend.upload_bytes(video_path, b"mock_video_bytes")

    media = AiPrepMediaFileORM(
        assessment_id=assessment.id,
        audio_file_path=f"ai-prep/{candidate.id}/{assessment.id}/audio.wav",
        video_file_path=video_path,
        duration_seconds=60,
        file_size_bytes=1000
    )
    db_session.add(media)
    db_session.commit()

    # Simulate 5th retry with quota exceeded
    with patch("fapi.ai_prep.workers.youtube_worker.get_storage_service", return_value=backend), \
         patch("fapi.ai_prep.workers.youtube_worker.SessionLocal", side_effect=TestingSessionLocal), \
         patch("fapi.ai_prep.workers.youtube_worker.get_youtube_service") as mock_yt_svc:

        mock_yt = MagicMock()
        mock_yt.upload_video.side_effect = YouTubeQuotaExceededException("Daily upload quota exceeded")
        mock_yt_svc.return_value = mock_yt

        # Task runner with retries = 5
        class MockTaskWith5Retries:
            class Request:
                id = "mock-5th-retry"
                retries = 5
            request = Request()
            def retry(self, exc=None, **kwargs):
                raise exc

        from fapi.ai_prep.workers.youtube_worker import upload_video_to_youtube_task
        res = upload_video_to_youtube_task.func(MockTaskWith5Retries(), assessment.id)

        assert res["status"] == "local_fallback"
        # Local video remains available
        assert backend.file_exists(video_path) is True
