import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AssessmentTypeEnum,
    AssessmentModeEnum,
    AssessmentStatusEnum,
    AiPrepMediaFileORM,
    AiPrepAnalysisRunORM,
    RunTypeEnum,
    RunStatusEnum,
)
from fapi.ai_prep.services.storage_service import LocalStorageBackend
from fapi.ai_prep.services.youtube_service import YouTubeService, YouTubeQuotaExceededException
from fapi.ai_prep.workers.youtube_worker import upload_video_to_youtube_task


@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp(prefix="aiprep_yt_test_storage_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def youtube_assessment_setup(db_session, candidate_db_user, temp_storage_dir):
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
    db_session.refresh(assessment)

    # Create local full.webm and chunks
    video_path = f"ai-prep/{candidate.id}/{assessment.id}/full.webm"
    audio_path = f"ai-prep/{candidate.id}/{assessment.id}/audio.wav"
    chunk_0_path = f"ai-prep/{candidate.id}/{assessment.id}/chunks/0.webm"
    chunk_1_path = f"ai-prep/{candidate.id}/{assessment.id}/chunks/1.webm"

    backend.upload_bytes(video_path, b"mock_full_webm_video_content_bytes")
    backend.upload_bytes(audio_path, b"mock_audio_wav_content_bytes")
    backend.upload_bytes(chunk_0_path, b"chunk_0_bytes")
    backend.upload_bytes(chunk_1_path, b"chunk_1_bytes")

    media = AiPrepMediaFileORM(
        assessment_id=assessment.id,
        audio_file_path=audio_path,
        video_file_path=video_path,
        duration_seconds=60,
        file_size_bytes=102400
    )
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)

    return {
        "candidate": candidate,
        "assessment": assessment,
        "media": media,
        "backend": backend,
        "video_path": video_path,
        "audio_path": audio_path,
        "chunks_prefix": f"ai-prep/{candidate.id}/{assessment.id}/chunks",
    }


def test_youtube_service_mock_mode(temp_storage_dir):
    service = YouTubeService(client_id=None, client_secret=None, refresh_token=None)
    assert service.is_configured() is False

    test_file = os.path.join(temp_storage_dir, "test_video.webm")
    with open(test_file, "wb") as f:
        f.write(b"sample_webm_bytes")

    video_id = service.upload_video(test_file, title="Test", description="Test Desc")
    assert video_id is not None
    assert video_id.startswith("yt_")

    # Delete video mock
    deleted = service.delete_video(video_id)
    assert deleted is True


from tests.conftest import TestingSessionLocal

def test_youtube_worker_successful_upload_and_auto_cleanup(db_session, youtube_assessment_setup):
    setup = youtube_assessment_setup
    assessment = setup["assessment"]
    backend = setup["backend"]
    video_path = setup["video_path"]
    audio_path = setup["audio_path"]

    # Verify files exist before worker runs
    assert backend.file_exists(video_path) is True
    assert backend.file_exists(audio_path) is True
    assert len(backend.list_files(setup["chunks_prefix"])) == 2

    # Run YouTube upload task
    with patch("fapi.ai_prep.workers.youtube_worker.get_storage_service", return_value=backend), \
         patch("fapi.ai_prep.workers.youtube_worker.SessionLocal", side_effect=TestingSessionLocal), \
         patch("fapi.ai_prep.workers.youtube_worker.get_youtube_service") as mock_yt_svc:

        mock_yt = MagicMock()
        mock_yt.is_configured.return_value = False
        mock_yt.upload_video.return_value = "yt_test_success_999"
        mock_yt_svc.return_value = mock_yt

        res = upload_video_to_youtube_task(assessment.id)

        assert res["status"] == "completed"
        assert res["youtube_video_id"] == "yt_test_success_999"
        assert res["youtube_url"] == "https://www.youtube.com/watch?v=yt_test_success_999"

        # Check DB record updated with YouTube URL
        db_session.expire_all()
        media = db_session.query(AiPrepMediaFileORM).filter(AiPrepMediaFileORM.assessment_id == assessment.id).first()
        assert media.video_file_path == "https://www.youtube.com/watch?v=yt_test_success_999"

        # Check analysis run record completed
        run = db_session.query(AiPrepAnalysisRunORM).filter(
            AiPrepAnalysisRunORM.assessment_id == assessment.id,
            AiPrepAnalysisRunORM.run_type == RunTypeEnum.YOUTUBE_UPLOAD
        ).first()
        assert run is not None
        assert run.status == RunStatusEnum.COMPLETED

        # -------------------------------------------------------------
        # Verify Auto-Cleanup: Local video and chunks MUST be deleted
        # -------------------------------------------------------------
        assert backend.file_exists(video_path) is False, "Local full.webm must be auto-deleted after YouTube upload"
        assert len(backend.list_files(setup["chunks_prefix"])) == 0, "Raw chunks must be auto-deleted"
        # Verify lightweight audio.wav is still retained
        assert backend.file_exists(audio_path) is True, "audio.wav must be retained for telemetry"


def test_youtube_worker_quota_exceeded_retry_and_retention(db_session, youtube_assessment_setup):
    setup = youtube_assessment_setup
    assessment = setup["assessment"]
    backend = setup["backend"]
    video_path = setup["video_path"]

    with patch("fapi.ai_prep.workers.youtube_worker.get_storage_service", return_value=backend), \
         patch("fapi.ai_prep.workers.youtube_worker.SessionLocal", side_effect=TestingSessionLocal), \
         patch("fapi.ai_prep.workers.youtube_worker.get_youtube_service") as mock_yt_svc:

        mock_yt = MagicMock()
        mock_yt.upload_video.side_effect = YouTubeQuotaExceededException("Daily upload limit reached")
        mock_yt_svc.return_value = mock_yt

        # Task should raise retry
        with pytest.raises(Exception):
            upload_video_to_youtube_task(assessment.id)

        # In quota exceeded state, local video MUST be retained for fallback!
        assert backend.file_exists(video_path) is True, "Local full.webm must NOT be deleted if YouTube upload failed"

