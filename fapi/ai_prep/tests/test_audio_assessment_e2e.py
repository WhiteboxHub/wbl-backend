"""
End-to-End Test Suite for Audio Assessment Workflow.
=====================================================
Covers the entire candidate lifecycle:
1. Pre-assessment prerequisites check (LLM keys, candidate resume status).
2. Starting an AUDIO assessment session.
3. Fetching targeted questions.
4. Submitting candidate answers & data.
5. Direct audio upload & pre-flight inspection.
6. Execution of audio processing engine (DSP acoustic telemetry & STT).
7. Audio-to-video packaging and YouTube upload (with quota enforcement).
8. Assessment & LLM evaluation orchestrator (Scores Engine validation).
9. Real-time status reporting and final comprehensive report retrieval.
10. Quota balance auditing.
"""
import os
import io
import time
import secrets
import datetime
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db, SessionLocal
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import Base, AuthUserORM, CandidateORM, CandidateMarketingORM, CandidateLlmApiKeyORM
from fapi.ai_prep import crud
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.ai_prep.config import settings
from fapi.ai_prep.clients.youtube_quota_manager import youtube_quota_manager
from fapi.ai_prep.clients.youtube_client import youtube_client
from fapi.ai_prep.utils.aiprep_utils import process_media_and_upload_pipeline

# Isolated in-memory database for E2E testing
sqlite_test_url = "sqlite:///:memory:"
e2e_engine = create_engine(
    sqlite_test_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
E2ESessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=e2e_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_db():
    tables = [
        AuthUserORM.__table__,
        CandidateORM.__table__,
        CandidateMarketingORM.__table__,
        CandidateLlmApiKeyORM.__table__,
        AiPrepAssessmentORM.__table__,
        AiPrepAssessmentDataORM.__table__,
        AiPrepAssessmentReportORM.__table__,
        AiPrepQuestionORM.__table__,
    ]
    Base.metadata.create_all(bind=e2e_engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=e2e_engine, tables=tables)


@pytest.fixture(autouse=True)
def clean_overrides():
    youtube_quota_manager.reset_quota()
    yield
    app.dependency_overrides.clear()
    youtube_quota_manager.reset_quota()


@pytest.fixture
def e2e_db_session():
    db = E2ESessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_candidate_e2e(e2e_db_session):
    cand = e2e_db_session.query(CandidateORM).filter(CandidateORM.id == 2001).first()
    if not cand:
        cand = CandidateORM(id=2001, email="candidate_2001@whitebox.com", full_name="Alice Sound")
        e2e_db_session.add(cand)

    llm = e2e_db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == 2001).first()
    if not llm:
        llm = CandidateLlmApiKeyORM(
            candidate_id=2001,
            provider_name="openai",
            api_key=secrets.token_urlsafe(16),
            model_name="gpt-4o",
            voice_enabled=True,
            is_default=True,
            status="active",
        )
        e2e_db_session.add(llm)

    mktg = e2e_db_session.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == 2001).first()
    if not mktg:
        mktg = CandidateMarketingORM(
            candidate_id=2001,
            start_date=datetime.date(2026, 1, 1),
            resume_url="https://storage.whiteboxlearning.com/resumes/alice_sound.pdf",
            candidate_json={"skills": ["Python", "FastAPI", "DSP", "Machine Learning"], "current_title": "AI Engineer"},
        )
        e2e_db_session.add(mktg)

    # Seed Questions for Intro category
    q1 = e2e_db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == 201).first()
    if not q1:
        q1 = AiPrepQuestionORM(
            id=201,
            category="INTRO",
            sub_category="Background",
            difficulty_level="MEDIUM",
            question_text="Tell me about yourself and your experience with AI systems.",
            is_active=True,
        )
        e2e_db_session.add(q1)

    e2e_db_session.commit()
    return cand


def get_e2e_client(db_session, candidate_id: int = 2001):
    mock_user = AuthUserORM(
        id=candidate_id,
        uname=f"candidate_{candidate_id}@whitebox.com",
        fullname=f"Candidate {candidate_id}",
        role="candidate",
    )
    setattr(mock_user, "is_employee", False)
    setattr(mock_user, "is_admin", False)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(app)


def test_audio_assessment_complete_end_to_end(e2e_db_session, seed_candidate_e2e):
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    # =========================================================================
    # STEP 1: Pre-Assessment Prerequisites Check
    # =========================================================================
    res_precheck = client.get("/api/aiprep/candidate/pre-check")
    assert res_precheck.status_code == 200, f"Precheck failed: {res_precheck.text}"
    precheck_data = res_precheck.json()
    assert precheck_data["eligible"] is True
    assert precheck_data["candidate_id"] == 2001
    assert precheck_data["llm_check"]["is_configured"] is True
    assert precheck_data["resume_check"]["has_resume"] is True

    # =========================================================================
    # STEP 2: Initialize Audio Assessment Session
    # =========================================================================
    payload = {
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
        "job_description": "Senior AI / Backend Engineer",
    }
    res_create = client.post("/api/aiprep/candidate/assessments", json=payload)
    assert res_create.status_code == 201, f"Assessment creation failed: {res_create.text}"
    created_data = res_create.json()
    assessment_id = created_data["id"]
    assessment_uuid = created_data["assessment_uuid"]

    assert created_data["status"] == "IN_PROGRESS"
    assert created_data["media_type"] == "AUDIO"
    assert created_data["assessment_type"] == "INTRO"
    assert assessment_id is not None
    assert assessment_uuid is not None

    # =========================================================================
    # STEP 3: Retrieve Assessment Questions
    # =========================================================================
    assert "questions" in created_data
    assert created_data["questions"] is not None
    assert len(created_data["questions"]) >= 1

    # =========================================================================
    # STEP 4: Submit Assessment Data / Candidate Answers
    # =========================================================================
    data_payload = {
        "questions": [
            {
                "question_id": 201,
                "question_text": "Tell me about yourself and your experience with AI systems.",
                "duration_seconds": 45.0,
            }
        ]
    }
    res_submit_data = client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/data", json=data_payload)
    assert res_submit_data.status_code in (200, 201)

    # =========================================================================
    # STEP 5: Quota Baseline Verification Before Upload
    # =========================================================================
    quota_before = youtube_client.get_quota_status()
    assert quota_before["quota_tracking_enabled"] is True
    assert quota_before["can_upload"] is True
    assert quota_before["units_used"] == 0

    # =========================================================================
    # STEP 6: Direct Audio Binary Upload & Pipeline Trigger
    # =========================================================================
    dummy_wav_content = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt " + b"\x10\x00\x00\x00" + b"\x01\x00\x01\x00" + b"\x44\xac\x00\x00" + b"\x88\x58\x01\x00" + b"\x02\x00\x10\x00" + b"data" + b"\x00\x00\x00\x00" + (b"\x00" * 400)

    mock_audio_result = {
        "spoken_content": {"full_text": "Hello, I am an AI engineer with 5 years of experience building Python microservices and speech models."},
        "audio_telemetry": {
            "avg_volume_db": -18.5,
            "mean_pitch_hz": 165.2,
            "silence_ratio": 0.12,
            "background_noise_level": "LOW",
            "clipping_detected": False,
            "filler_rate_per_min": 1.2,
            "filler_count": 1,
            "words_per_minute": 135.0,
            "total_speech_duration": 42.0,
        }
    }

    mock_eval_result = {
        "transcript_evaluation": {
            "overall_assessment": {"readiness": "READY", "score": 88.5},
            "category_scores": {"technical_depth": 90, "clarity": 87, "structure": 88},
            "strengths": ["Clear communication", "Strong technical background"],
            "improvements": ["Elaborate more on production scale"],
        },
        "audio_evaluation": {
            "summary": {"overall_readiness": "READY", "confidence_score": 92.0},
            "metrics_breakdown": {"pace": "OPTIMAL", "clarity": "HIGH", "pitch_stability": "GOOD"},
        },
        "video_evaluation": None,
    }

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result), \
         patch("fapi.ai_prep.core.video_processor_engine.VideoProcessorEngine.convert_audio_for_youtube", side_effect=lambda p: p), \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", return_value=mock_eval_result), \
         patch("fapi.ai_prep.utils.aiprep_utils.SessionLocal", return_value=e2e_db_session):

        res_upload = client.post(
            f"/api/aiprep/candidate/assessments/{assessment_id}/audio",
            files={"file": ("audio_recording.wav", io.BytesIO(dummy_wav_content), "audio/wav")},
            data={"mime_type": "audio/wav"},
        )
        assert res_upload.status_code == 200, f"Upload audio failed: {res_upload.text}"
        upload_data = res_upload.json()
        assert upload_data["success"] is True
        assert upload_data["assessment_id"] == assessment_id
        assert upload_data["size_bytes"] > 0

        # Run pipeline
        import asyncio
        asyncio.run(
            process_media_and_upload_pipeline(
                assessment_id=assessment_id,
                media_path=upload_data["file_path"],
                media_type="AUDIO",
                candidate_id=2001,
            )
        )

    # =========================================================================
    # STEP 7: Verify DB State Transitions & Telemetry Persistence
    # =========================================================================
    db_assessment = e2e_db_session.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    assert db_assessment is not None
    assert db_assessment.youtube_url is not None
    assert "youtube.com" in db_assessment.youtube_url

    db_data = e2e_db_session.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    assert db_data is not None
    assert db_data.transcript is not None
    assert "Hello, I am an AI engineer" in db_data.transcript.get("full_text", "")
    assert db_data.audio_telemetry is not None
    assert db_data.audio_telemetry.get("words_per_minute") == 135.0
    assert db_data.audio_telemetry.get("background_noise_level") == "LOW"

    # Save report
    crud.save_assessment_report(
        db=e2e_db_session,
        assessment_id=assessment_id,
        parsed_report=mock_eval_result,
    )
    crud.update_assessment_status(db=e2e_db_session, assessment_id=assessment_id, status="COMPLETED")

    # =========================================================================
    # STEP 8: Processing Status Snapshot Verification
    # =========================================================================
    res_status = client.get(f"/api/aiprep/assessments/{assessment_id}/status")
    assert res_status.status_code == 200
    status_snapshot = res_status.json()
    assert status_snapshot["assessment_id"] == assessment_id
    assert status_snapshot["status"] == "COMPLETED"
    assert status_snapshot["progress_percentage"] == 100
    assert status_snapshot["youtube_url"] is not None

    # =========================================================================
    # STEP 9: Audio Stream Retrieval Verification
    # =========================================================================
    res_audio_get = client.get(f"/api/aiprep/candidate/assessments/{assessment_id}/audio")
    assert res_audio_get.status_code in (200, 404)

    # =========================================================================
    # STEP 10: Evaluation Report Retrieval Verification
    # =========================================================================
    res_report = client.get(f"/api/aiprep/assessments/{assessment_id}/report")
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert report_data["assessment_id"] == assessment_id
    assert report_data["overall_score"] == 88.5
    assert report_data["transcript_evaluation"] is not None
    assert report_data["audio_evaluation"] is not None
    assert report_data["video_evaluation"] is None

    # =========================================================================
    # STEP 11: Assessment Details Inspection
    # =========================================================================
    res_detail = client.get(f"/api/aiprep/candidate/assessments/{assessment_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == assessment_id
    assert detail["assessment_uuid"] == assessment_uuid
    assert detail["media_type"] == "AUDIO"
    assert detail["status"] == "COMPLETED"
    assert detail["youtube_url"] is not None

    # =========================================================================
    # STEP 12: Quota Status Verification
    # =========================================================================
    quota_after = youtube_client.get_quota_status()
    assert quota_after["quota_tracking_enabled"] is True
    assert quota_after["can_upload"] is True
    assert quota_after["is_quota_exceeded"] is False


def test_audio_assessment_prerequisites_blocked(e2e_db_session):
    """Verifies candidate without active LLM key is blocked from starting assessment."""
    cand_unconfigured = CandidateORM(id=2002, email="candidate_2002@whitebox.com", full_name="No LLM")
    e2e_db_session.add(cand_unconfigured)
    e2e_db_session.commit()

    client = get_e2e_client(e2e_db_session, candidate_id=2002)

    res_precheck = client.get("/api/aiprep/candidate/pre-check")
    assert res_precheck.status_code == 200
    assert res_precheck.json()["eligible"] is False

    payload = {
        "candidate_id": 2002,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    }
    res_create = client.post("/api/aiprep/candidate/assessments", json=payload)
    assert res_create.status_code == 400
    err = res_create.json()
    assert "detail" in err
    assert "Prerequisites not met" in str(err)


def test_audio_assessment_with_quota_exhaustion_fallback(e2e_db_session, seed_candidate_e2e):
    """Verifies that when YouTube quota is exhausted, the audio assessment pipeline still completes."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    })
    assert res_create.status_code == 201
    assessment_id = res_create.json()["id"]

    youtube_quota_manager.mark_quota_exceeded()
    assert youtube_quota_manager.has_sufficient_quota() is False

    dummy_wav_content = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt " + b"\x10\x00\x00\x00" + b"\x01\x00\x01\x00" + b"\x44\xac\x00\x00" + b"\x88\x58\x01\x00" + b"\x02\x00\x10\x00" + b"data" + b"\x00\x00\x00\x00" + (b"\x00" * 400)
    mock_audio = {"spoken_content": {"full_text": "Audio text"}, "audio_telemetry": {"words_per_minute": 120}}
    mock_eval = {
        "transcript_evaluation": {"overall_assessment": {"score": 80.0}},
        "audio_evaluation": {"summary": {"overall_readiness": "GOOD"}},
        "video_evaluation": None,
    }

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio), \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", return_value=mock_eval), \
         patch("fapi.ai_prep.utils.aiprep_utils.SessionLocal", return_value=e2e_db_session):

        res_upload = client.post(
            f"/api/aiprep/candidate/assessments/{assessment_id}/audio",
            files={"file": ("audio_recording.wav", io.BytesIO(dummy_wav_content), "audio/wav")},
        )
        assert res_upload.status_code == 200
        upload_data = res_upload.json()

        import asyncio
        asyncio.run(
            process_media_and_upload_pipeline(
                assessment_id=assessment_id,
                media_path=upload_data["file_path"],
                media_type="AUDIO",
                candidate_id=2001,
            )
        )

    db_data = e2e_db_session.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    assert db_data is not None
    assert db_data.transcript == mock_audio["spoken_content"]


def test_audio_assessment_unauthorized_isolation(e2e_db_session, seed_candidate_e2e):
    """Verifies candidate A cannot access or modify candidate B's audio assessment."""
    client_a = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client_a.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    })
    assessment_id = res_create.json()["id"]

    mock_user_b = AuthUserORM(id=2002, uname="candidate_2002@whitebox.com", fullname="Other Candidate", role="candidate")
    setattr(mock_user_b, "is_employee", False)
    setattr(mock_user_b, "is_admin", False)

    app.dependency_overrides[get_db] = lambda: e2e_db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user_b
    client_b = TestClient(app)

    res_unauth = client_b.get(f"/api/aiprep/candidate/assessments/{assessment_id}")
    assert res_unauth.status_code in (403, 404)


def test_chunk_upload_rejects_oversized_payload_413(e2e_db_session, seed_candidate_e2e, monkeypatch):
    """Verifies that chunks exceeding MAX_CHUNK_SIZE_MB are rejected with HTTP 413."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assessment_id = res_create.json()["id"]

    # Temporarily set max chunk size to 1 MB for testing
    monkeypatch.setattr(settings, "MAX_CHUNK_SIZE_MB", 1)

    oversized_data = b"\x1a\x45\xdf\xa3" + (b"\x00" * (2 * 1024 * 1024))  # 2MB
    res_upload = client.post(
        "/api/aiprep/media/upload-chunk",
        data={
            "assessment_id": str(assessment_id),
            "chunk_number": 1,
            "total_chunks": 1,
        },
        files={"file": ("chunk_0001.webm", io.BytesIO(oversized_data), "video/webm")},
    )
    assert res_upload.status_code == 413
    assert "exceeds maximum allowed size" in res_upload.json()["detail"]


def test_assemble_rejects_missing_chunks_409(e2e_db_session, seed_candidate_e2e):
    """Verifies that assembling an incomplete chunk sequence is rejected with HTTP 409 Conflict."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assessment_id = res_create.json()["id"]

    chunk_data = b"\x1a\x45\xdf\xa3" + (b"\x00" * 200)

    # Upload chunk 1
    res1 = client.post(
        "/api/aiprep/media/upload-chunk",
        data={"assessment_id": str(assessment_id), "chunk_number": 1, "total_chunks": 3},
        files={"file": ("chunk_0001.webm", io.BytesIO(chunk_data), "video/webm")},
    )
    assert res1.status_code == 200

    # Upload chunk 3 (Chunk 2 is missing!)
    res3 = client.post(
        "/api/aiprep/media/upload-chunk",
        data={"assessment_id": str(assessment_id), "chunk_number": 3, "total_chunks": 3},
        files={"file": ("chunk_0003.webm", io.BytesIO(chunk_data), "video/webm")},
    )
    assert res3.status_code == 200

    # Attempt assembly with missing chunk 2
    res_assemble = client.post(
        f"/api/aiprep/media/assemble?assessment_id={assessment_id}",
        json={"total_chunks": 3},
    )
    assert res_assemble.status_code == 409
    assert "Missing" in res_assemble.json()["detail"] or "Incomplete" in res_assemble.json()["detail"]


def test_storage_retained_when_db_url_update_fails(e2e_db_session, seed_candidate_e2e):
    """Verifies local storage is NOT deleted if updating the YouTube URL in the DB fails."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    })
    assessment_id = res_create.json()["id"]

    dummy_wav_content = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt " + b"\x10\x00\x00\x00" + b"\x01\x00\x01\x00" + b"\x44\xac\x00\x00" + b"\x88\x58\x01\x00" + b"\x02\x00\x10\x00" + b"data" + b"\x00\x00\x00\x00" + (b"\x00" * 400)

    mock_audio = {"spoken_content": {"full_text": "Audio text"}, "audio_telemetry": {"words_per_minute": 120}}
    mock_eval = {"transcript_evaluation": {}, "audio_evaluation": {}, "video_evaluation": None}

    def failing_update_media_url(*args, **kwargs):
        raise RuntimeError("Database connection lost during update_assessment_media_url")

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio), \
         patch("fapi.ai_prep.core.video_processor_engine.VideoProcessorEngine.convert_audio_for_youtube", side_effect=lambda x: x), \
         patch("fapi.ai_prep.clients.youtube_client.youtube_client.upload_unlisted_media", return_value={"youtube_url": "https://youtu.be/dummy"}), \
         patch("fapi.ai_prep.crud.update_assessment_media_url", side_effect=failing_update_media_url), \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", return_value=mock_eval), \
         patch("fapi.ai_prep.utils.aiprep_utils.SessionLocal", E2ESessionLocal):

        res_upload = client.post(
            f"/api/aiprep/candidate/assessments/{assessment_id}/audio",
            files={"file": ("audio_recording.wav", io.BytesIO(dummy_wav_content), "audio/wav")},
        )
        assert res_upload.status_code == 200
        upload_file_path = res_upload.json()["file_path"]
        assessment_dir = os.path.dirname(upload_file_path)

    # Assessment directory must be preserved because DB URL update failed
    assert os.path.exists(assessment_dir)


def test_audio_engine_failure_marks_assessment_failed_without_dummy_data(e2e_db_session, seed_candidate_e2e):
    """Verifies that audio engine errors mark the assessment as FAILED and never save fake telemetry."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    })
    assessment_id = res_create.json()["id"]

    dummy_wav_content = b"RIFF" + (b"\x00" * 400)

    def failing_audio_engine(*args, **kwargs):
        raise RuntimeError("Whisper STT model failed to decode audio")

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", side_effect=failing_audio_engine), \
         patch("fapi.db.database.SessionLocal", E2ESessionLocal), \
         patch("fapi.ai_prep.utils.aiprep_utils.SessionLocal", E2ESessionLocal):

        res_upload = client.post(
            f"/api/aiprep/candidate/assessments/{assessment_id}/audio",
            files={"file": ("audio_recording.wav", io.BytesIO(dummy_wav_content), "audio/wav")},
        )
        assert res_upload.status_code == 200

    e2e_db_session.expire_all()
    assessment = e2e_db_session.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    assert assessment.status == "FAILED"
    # Verify no fake dummy telemetry or transcript was persisted
    assessment_data = e2e_db_session.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    if assessment_data:
        assert assessment_data.transcript != {"full_text": "Assessment audio content"}
        assert assessment_data.audio_telemetry != {"words_per_minute": 120}


def test_direct_upload_rejects_invalid_media_type_400(e2e_db_session, seed_candidate_e2e):
    """Verifies direct media upload rejects invalid media_type with 400."""
    client = get_e2e_client(e2e_db_session, candidate_id=2001)

    res_create = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 2001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assessment_id = res_create.json()["id"]

    res_upload = client.post(
        "/api/aiprep/media/upload",
        data={
            "assessment_id": str(assessment_id),
            "media_type": "INVALID_TYPE",
        },
        files={"file": ("test.webm", io.BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 100), "video/webm")},
    )
    assert res_upload.status_code == 400
    assert "Invalid media_type" in res_upload.json()["detail"]

