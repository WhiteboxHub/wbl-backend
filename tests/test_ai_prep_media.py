import os
import shutil
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fapi.db.models import AuthUserORM, CandidateORM
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AssessmentTypeEnum,
    AssessmentModeEnum,
    AssessmentStatusEnum,
    AiPrepQuestionBankORM,
    AiPrepAssessmentQuestionORM,
    QuestionCategoryEnum,
    DifficultyLevelEnum,
    AiPrepConsentORM,
    ConsentTypeEnum,
    AiPrepMediaFileORM,
)
from fapi.ai_prep.services.storage_service import LocalStorageBackend


@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp(prefix="aiprep_test_storage_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def assessment_setup(db_session, candidate_db_user):
    candidate = candidate_db_user["candidate"]

    # 1. Question Bank Seed
    question = AiPrepQuestionBankORM(
        category=QuestionCategoryEnum.TECHNICAL,
        sub_category="RAG Systems",
        difficulty_level=DifficultyLevelEnum.MEDIUM,
        question_text="Explain how dense vector retrieval works in a RAG system.",
        ideal_answer_rubric="Should mention embeddings, cosine similarity, ANN search.",
        is_active=True
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    # 2. Assessment
    assessment = AiPrepAssessmentORM(
        candidate_id=candidate.id,
        assessment_type=AssessmentTypeEnum.TECHNICAL,
        assessment_mode=AssessmentModeEnum.VIDEO_AUDIO,
        status=AssessmentStatusEnum.IN_PROGRESS,
        attempt_number=1,
        started_at=datetime.utcnow()
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)

    # 3. Join Question
    aq = AiPrepAssessmentQuestionORM(
        assessment_id=assessment.id,
        question_id=question.id,
        order_index=1
    )
    db_session.add(aq)

    # 4. Consent
    consent = AiPrepConsentORM(
        candidate_id=candidate.id,
        consent_type=ConsentTypeEnum.VIDEO_ANALYTICS,
        consented=True,
        ip_address="127.0.0.1"
    )
    db_session.add(consent)
    db_session.commit()

    return {
        "candidate": candidate,
        "assessment": assessment,
        "question": question,
    }


def test_local_storage_backend(temp_storage_dir):
    backend = LocalStorageBackend(base_dir=temp_storage_dir)

    # 1. Upload & Read
    stored_path = backend.upload_bytes("test/candidate_1/chunk_0.webm", b"mock_webm_bytes_001")
    assert stored_path == "test/candidate_1/chunk_0.webm"
    assert backend.file_exists(stored_path) is True
    assert backend.read_bytes(stored_path) == b"mock_webm_bytes_001"

    # 2. Signed URL
    url = backend.generate_signed_url(stored_path, ttl_minutes=15)
    assert "local-stream" in url
    assert "test/candidate_1/chunk_0.webm" in url

    # 3. Path Traversal Prevention
    with pytest.raises(ValueError, match="Invalid storage path traversal"):
        backend.upload_bytes("../../../etc/passwd", b"malicious")

    # 4. List Files
    backend.upload_bytes("test/candidate_1/chunk_1.webm", b"mock_webm_bytes_002")
    files = backend.list_files("test/candidate_1")
    assert len(files) == 2

    # 5. Delete Prefix
    deleted = backend.delete_prefix("test/candidate_1")
    assert deleted == 2
    assert backend.file_exists(stored_path) is False


def test_upload_chunk_success(client, candidate_headers, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=LocalStorageBackend(temp_storage_dir)):
        files = {"file": ("chunk_0.webm", b"RIFF....webm_dummy_chunk_content", "video/webm")}
        data = {
            "assessment_id": assessment.id,
            "chunk_number": 0,
            "total_chunks": 3
        }
        response = client.post("/api/ai-prep/media/upload-chunk", data=data, files=files, headers=candidate_headers)

        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["chunk_number"] == 0
        assert f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/0.webm" in resp_json["storage_path"]


def test_upload_chunk_unauthorized_candidate(client, db_session, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]

    from datetime import date
    other_auth = AuthUserORM(
        uname="intruder@test.com",
        passwd="password123",
        status="active",
        role="candidate",
        enddate=date(1990, 1, 1),
    )
    db_session.add(other_auth)
    db_session.commit()

    from tests.conftest import _forge_token
    intruder_token = _forge_token(other_auth.id, other_auth.uname, role="candidate", is_admin=False)
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=LocalStorageBackend(temp_storage_dir)):
        files = {"file": ("chunk_0.webm", b"bytes", "video/webm")}
        data = {"assessment_id": assessment.id, "chunk_number": 0, "total_chunks": 1}
        response = client.post("/api/ai-prep/media/upload-chunk", data=data, files=files, headers=intruder_headers)
        assert response.status_code == 403


def test_upload_chunk_invalid_status(client, candidate_headers, db_session, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    assessment.status = AssessmentStatusEnum.COMPLETED
    db_session.commit()

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=LocalStorageBackend(temp_storage_dir)):
        files = {"file": ("chunk_0.webm", b"bytes", "video/webm")}
        data = {"assessment_id": assessment.id, "chunk_number": 0, "total_chunks": 1}
        response = client.post("/api/ai-prep/media/upload-chunk", data=data, files=files, headers=candidate_headers)
        assert response.status_code == 400
        assert "Cannot upload chunk" in response.json()["detail"]


def test_assemble_media_success(client, candidate_headers, db_session, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    backend = LocalStorageBackend(temp_storage_dir)

    # Pre-upload 2 chunks
    c0 = f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/0.webm"
    c1 = f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/1.webm"
    backend.upload_bytes(c0, b"chunk_0_content")
    backend.upload_bytes(c1, b"chunk_1_content")

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend), \
         patch("fapi.ai_prep.services.youtube_service.get_youtube_service") as mock_yt_svc:
        
        mock_yt = MagicMock()
        mock_yt.is_configured.return_value = False
        mock_yt.upload_video.return_value = "mock_yt_assembled_123"
        mock_yt_svc.return_value = mock_yt

        payload = {"assessment_id": assessment.id, "total_chunks": 2}
        response = client.post("/api/ai-prep/media/assemble", json=payload, headers=candidate_headers)

        assert response.status_code == 202
        resp_data = response.json()
        assert resp_data["status"] == "PROCESSING"
        assert resp_data["assessment_id"] == assessment.id
        assert resp_data["task_id"] is not None

        # Verify DB media record created
        media = db_session.query(AiPrepMediaFileORM).filter(AiPrepMediaFileORM.assessment_id == assessment.id).first()
        assert media is not None
        assert f"ai-prep/{assessment.candidate_id}/{assessment.id}/audio.wav" in media.audio_file_path


def test_assemble_media_missing_chunk(client, candidate_headers, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    backend = LocalStorageBackend(temp_storage_dir)

    # Upload only chunk 0 of 2
    c0 = f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/0.webm"
    backend.upload_bytes(c0, b"chunk_0_content")

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend):
        payload = {"assessment_id": assessment.id, "total_chunks": 2}
        response = client.post("/api/ai-prep/media/assemble", json=payload, headers=candidate_headers)
        assert response.status_code == 400
        assert "Missing required chunks" in response.json()["detail"]


def test_get_processing_status(client, candidate_headers, assessment_setup):
    assessment = assessment_setup["assessment"]
    response = client.get(f"/api/ai-prep/assessments/{assessment.id}/processing-status", headers=candidate_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "IN_PROGRESS"
    assert "steps" in data
    assert "stt" in data["steps"]
    assert "youtube_upload" in data["steps"]


def test_get_media_details(client, candidate_headers, db_session, assessment_setup):
    assessment = assessment_setup["assessment"]

    # Add media record
    media = AiPrepMediaFileORM(
        assessment_id=assessment.id,
        audio_file_path=f"ai-prep/{assessment.candidate_id}/{assessment.id}/audio.wav",
        video_file_path="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        duration_seconds=120,
        file_size_bytes=1024000
    )
    db_session.add(media)
    db_session.commit()

    response = client.get(f"/api/ai-prep/media/{assessment.id}", headers=candidate_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["assessment_id"] == assessment.id
    assert data["is_youtube"] is True
    assert data["youtube_video_id"] == "dQw4w9WgXcQ"
    assert data["video_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_get_chunks_status_and_resumption(client, candidate_headers, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    backend = LocalStorageBackend(temp_storage_dir)

    # Upload chunks 0, 1, and 3 (chunk 2 missing)
    backend.upload_bytes(f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/0.webm", b"c0")
    backend.upload_bytes(f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/1.webm", b"c1")
    backend.upload_bytes(f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/3.webm", b"c3")

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend):
        response = client.get(f"/api/ai-prep/media/{assessment.id}/chunks-status", headers=candidate_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"] == assessment.id
        assert data["uploaded_chunks"] == [0, 1, 3]
        assert data["total_uploaded"] == 3
        assert data["highest_chunk_number"] == 3
        assert data["missing_chunks"] == [2]


def test_assemble_media_missing_chunks_structured_error(client, candidate_headers, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    backend = LocalStorageBackend(temp_storage_dir)

    # Upload only chunks 0 and 2 (chunk 1 missing)
    backend.upload_bytes(f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/0.webm", b"c0")
    backend.upload_bytes(f"ai-prep/{assessment.candidate_id}/{assessment.id}/chunks/2.webm", b"c2")

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend):
        payload = {"assessment_id": assessment.id, "total_chunks": 3}
        response = client.post("/api/ai-prep/media/assemble", json=payload, headers=candidate_headers)
        assert response.status_code == 400
        data = response.json()
        assert "missing_chunks" in data
        assert data["missing_chunks"] == [1]


def test_delete_candidate_media_gdpr_success(client, candidate_headers, db_session, assessment_setup, temp_storage_dir):
    assessment = assessment_setup["assessment"]
    candidate = assessment_setup["candidate"]
    backend = LocalStorageBackend(temp_storage_dir)

    # Setup local files
    backend.upload_bytes(f"ai-prep/{candidate.id}/{assessment.id}/full.webm", b"video")
    backend.upload_bytes(f"ai-prep/{candidate.id}/{assessment.id}/audio.wav", b"audio")
    backend.upload_bytes(f"ai-prep/{candidate.id}/{assessment.id}/chunks/0.webm", b"chunk0")

    # Add media record pointing to YouTube
    media = AiPrepMediaFileORM(
        assessment_id=assessment.id,
        audio_file_path=f"ai-prep/{candidate.id}/{assessment.id}/audio.wav",
        video_file_path="https://www.youtube.com/watch?v=mock_gdpr_yt_123",
        duration_seconds=60,
        file_size_bytes=50000
    )
    db_session.add(media)
    db_session.commit()

    with patch("fapi.ai_prep.services.media_service.get_storage_service", return_value=backend), \
         patch("fapi.ai_prep.services.media_service.get_youtube_service") as mock_yt_svc:

        mock_yt = MagicMock()
        mock_yt.delete_video.return_value = True
        mock_yt_svc.return_value = mock_yt

        response = client.delete(f"/api/ai-prep/media/candidate/{candidate.id}", headers=candidate_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["local_files_deleted"] == 3
        assert data["youtube_videos_deleted"] == 1

        # Verify local files removed
        assert backend.file_exists(f"ai-prep/{candidate.id}/{assessment.id}/full.webm") is False


def test_delete_candidate_media_unauthorized(client, db_session, assessment_setup, temp_storage_dir):
    candidate = assessment_setup["candidate"]

    # Create another candidate attempting unauthorized delete
    from datetime import date
    from tests.conftest import _forge_token

    other_auth = AuthUserORM(
        uname="other_cand@test.com",
        passwd="password123",
        status="active",
        role="candidate",
        enddate=date(1990, 1, 1),
    )
    db_session.add(other_auth)
    db_session.commit()

    other_headers = {"Authorization": f"Bearer {_forge_token(other_auth.id, other_auth.uname, role='candidate', is_admin=False)}"}

    response = client.delete(f"/api/ai-prep/media/candidate/{candidate.id}", headers=other_headers)
    assert response.status_code == 403

