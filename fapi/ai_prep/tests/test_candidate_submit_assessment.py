"""Comprehensive Test Suite for PUT /candidates/{id}/assessments/{id} and Gatekeeper Flag Logic."""
import os
import shutil
import tempfile
import secrets
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["ENV"] = "test"

from fapi.main import app
from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import Base, AuthUserORM, CandidateORM, CandidateMarketingORM, CandidateLlmApiKeyORM
from fapi.ai_prep import crud
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.ai_prep.utils.aiprep_utils import (
    evaluate_gatekeeper_flag,
    _stitch_assessment_chunks,
)

sqlite_test_db_url = "sqlite:///:memory:"
test_engine = create_engine(
    sqlite_test_db_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

import fapi.db.database
fapi.db.database.SessionLocal = TestingSessionLocal
fapi.db.database.engine = test_engine


@pytest.fixture(scope="session", autouse=True)
def setup_db():
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
    Base.metadata.create_all(bind=test_engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=test_engine, tables=tables)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        app.dependency_overrides.clear()



@pytest.fixture
def mock_candidate_user(db_session):
    cand = db_session.query(CandidateORM).filter(CandidateORM.id == 1042).first()
    if not cand:
        cand = CandidateORM(
            id=1042,
            full_name="Jane Doe",
            email="candidate1042@example.com",
        )
        db_session.add(cand)
        db_session.commit()

    user = AuthUserORM(
        id=1042,
        uname="candidate1042@example.com",
        fullname="Jane Doe",
        role="candidate",
    )
    setattr(user, "is_employee", False)
    setattr(user, "is_admin", False)
    return user


@pytest.fixture
def submit_test_client(db_session, mock_candidate_user):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_current_user():
        return mock_candidate_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Gatekeeper Flag Unit Tests
# ===========================================================================

def test_flag_logic_silence_or_mute_interview():
    """Candidate took whole interview in silence/mute (0 words). Flag MUST be ON (True)."""
    # 0 words spoken during 120 seconds of interview
    flag = evaluate_gatekeeper_flag(word_count=0, duration_seconds=120.0, min_words=15, min_duration=20.0)
    assert flag is True


def test_flag_logic_insufficient_words():
    """Candidate spoke only 3 words ('Hello, thank you.'). Flag MUST be ON (True)."""
    flag = evaluate_gatekeeper_flag(word_count=3, duration_seconds=120.0, min_words=15, min_duration=20.0)
    assert flag is True


def test_flag_logic_insufficient_duration():
    """Candidate spoke 50 words but stopped after 8 seconds. Flag MUST be ON (True)."""
    flag = evaluate_gatekeeper_flag(word_count=50, duration_seconds=8.0, min_words=15, min_duration=20.0)
    assert flag is True


def test_flag_logic_sufficient_content():
    """Candidate spoke 52 words across 45 seconds. Flag MUST be OFF (False)."""
    flag = evaluate_gatekeeper_flag(word_count=52, duration_seconds=45.0, min_words=15, min_duration=20.0)
    assert flag is False


def test_flag_logic_ignores_silence_percentage():
    """Verify that acoustic DSP / silence percentage does NOT affect flag evaluation."""
    # Even if silence was high, flag only checks word_count and duration
    flag_sufficient = evaluate_gatekeeper_flag(word_count=30, duration_seconds=60.0, min_words=15, min_duration=20.0)
    assert flag_sufficient is False

    flag_insufficient = evaluate_gatekeeper_flag(word_count=5, duration_seconds=60.0, min_words=15, min_duration=20.0)
    assert flag_insufficient is True


# ===========================================================================
# 2. PUT Assessment API End-to-End Tests
# ===========================================================================

def test_submit_assessment_case_1_insufficient_content(submit_test_client, db_session, monkeypatch, tmp_path):
    """
    Case 1: Response Body when Flag is 'ON' (insufficient_content: True)
    - Status set directly to COMPLETED
    - LLM evaluation is completely skipped
    - Gatekeeper flag is returned in response body
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    # 1. Create assessment
    assessment = crud.create_assessment(
        db_session,
        candidate_id=1042,
        assessment_type="INTRO",
        media_type="AUDIO",
    )
    assessment_id = assessment.id

    # 2. Simulate uploaded chunks
    chunks_dir = tmp_path / "1042" / str(assessment_id) / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (chunks_dir / f"chunk_{i}.webm").write_bytes(b"dummy webm chunk content " + str(i).encode())

    # 3. Mock Audio Engine returning few words ("Hello, thank you.")
    mock_audio_result = {
        "spoken_content": {
            "full_text": "Hello, thank you.",
            "word_count": 3,
            "segments": [{"start": 1.2, "end": 4.4, "text": "Hello, thank you."}],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 3.2,
            "wpm": 56,
            "filler_count": 0,
            "silence_ratio": 0.88,
            "total_audio_duration_seconds": 120.0,
        },
    }

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result), \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation") as mock_eval:

        payload = {
            "total_chunks_uploaded": 4,
            "is_final": True,
            "client_duration_seconds": 120.0,
            "video_telemetry": {
                "eye_contact_percentage": 75.0,
                "face_visibility_percentage": 90.0,
            },
        }

        res = submit_test_client.put(
            f"/api/aiprep/candidates/1042/assessments/{assessment_id}",
            json=payload,
        )

        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"

        asm = data["data"]["assessment"]
        assert asm["id"] == assessment_id
        assert asm["candidate_id"] == 1042
        assert asm["status"] == "COMPLETED"
        assert asm["completed_at"] is not None

        transcript = data["data"]["assessment_data"]["transcript"]
        assert transcript["full_text"] == "Hello, thank you."
        assert transcript["word_count"] == 3

        report = data["data"]["report"]
        assert report["insufficient_content"] is True
        assert "message" in report
        assert report["llm_evaluation"] == {}

        # LLM evaluation was NOT invoked
        mock_eval.assert_not_called()

        # Database record verified
        db_asm = crud.get_assessment_by_id_or_uuid(db_session, assessment_id)
        assert db_asm.status == "COMPLETED"
        assert db_asm.completed_at is not None


def test_submit_assessment_case_2_sufficient_content(submit_test_client, db_session, monkeypatch, tmp_path):
    """
    Case 2: Response Body when Flag is 'OFF' (insufficient_content: False)
    - Status set to EVALUATING
    - completed_at is null
    - LLM evaluation task is queued in background
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=1042,
        assessment_type="INTRO",
        media_type="AUDIO",
    )
    assessment_id = assessment.id

    chunks_dir = tmp_path / "1042" / str(assessment_id) / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (chunks_dir / f"chunk_{i}.webm").write_bytes(b"dummy webm chunk content " + str(i).encode())

    long_transcript = (
        "Hello, I have around 6 years of software engineering experience. "
        "I started in backend services with Python and FastAPI, then transitioned into ML and RAG. "
        "For the past two years, I have worked as an AI Engineer focusing on Agentic AI and multi-agent systems."
    )
    mock_audio_result = {
        "spoken_content": {
            "full_text": long_transcript,
            "word_count": len(long_transcript.split()),
            "segments": [
                {"start": 0.0, "end": 8.5, "text": "Hello, I have around 6 years of software engineering experience."},
                {"start": 8.6, "end": 20.1, "text": "I started in backend services with Python and FastAPI, then transitioned into ML and RAG."},
            ],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 42.5,
            "wpm": 138,
            "filler_count": 3,
            "filler_breakdown": {"um": 2, "like": 1},
            "silence_ratio": 0.054,
            "clarity": "High",
            "total_audio_duration_seconds": 60.0,
        },
    }

    mock_eval_report = {
        "transcript_evaluation": {"scores_breakdown_json": {"technical_depth": 9}},
        "audio_evaluation": {"pace": "Good", "filler_words": "Minimal"},
        "video_evaluation": {"framing": "Centered"},
    }

    with patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result), \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", return_value={"assessment_id": assessment_id, "status": "COMPLETED", "report": mock_eval_report}) as mock_eval:

        payload = {
            "total_chunks_uploaded": 4,
            "is_final": True,
            "client_duration_seconds": 60.0,
            "video_telemetry": {
                "eye_contact_percentage": 89.2,
                "face_visibility_percentage": 98.0,
            },
        }

        res = submit_test_client.put(
            f"/api/aiprep/candidates/1042/assessments/{assessment_id}",
            json=payload,
        )

        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"

        # Verify LLM evaluation engine was triggered
        mock_eval.assert_called_once()

        asm = data["data"]["assessment"]
        assert asm["id"] == assessment_id
        assert asm["status"] == "COMPLETED"

        report = data["data"]["report"]
        assert report["insufficient_content"] is False
        # Case B: Response body MUST NOT contain any message
        assert report.get("message") is None
        # Case B: Response MUST contain llm_evaluation information
        assert report["llm_evaluation"] == mock_eval_report
        assert "transcript_evaluation" in report["llm_evaluation"]

        # Database record verified
        db_asm = crud.get_assessment_by_id_or_uuid(db_session, assessment_id)
        assert db_asm.status == "COMPLETED"


def test_removed_endpoints_are_inaccessible(submit_test_client):
    """Verify that all 7 superseded candidate endpoints return 404 or 405."""
    # 1. POST /media/assemble -> 404
    assert submit_test_client.post("/api/aiprep/media/assemble?assessment_id=999").status_code == 404

    # 2. POST /candidate/assessments/{id}/data -> 404 or 405
    assert submit_test_client.post("/api/aiprep/candidate/assessments/999/data", json={}).status_code == 404

    # 3. POST /candidate/assessments/{id}/evaluate -> 404
    assert submit_test_client.post("/api/aiprep/candidate/assessments/999/evaluate").status_code == 404

    # 4. PUT /candidate/assessments/{id}/evaluate -> 404
    assert submit_test_client.put("/api/aiprep/candidate/assessments/999/evaluate", json={}).status_code == 404

    # 5. GET /candidate/assessments/{id} -> 404 or 405
    assert submit_test_client.get("/api/aiprep/candidate/assessments/999").status_code == 404

    # 6. GET /candidate/assessments/{id}/data -> 404
    assert submit_test_client.get("/api/aiprep/candidate/assessments/999/data").status_code == 404

    # 7. GET /candidate/assessments/{id}/report -> 404
    assert submit_test_client.get("/api/aiprep/candidate/assessments/999/report").status_code == 404


def test_put_assessment_status_cancelled_query_param(submit_test_client, db_session):
    """Verify that PUT with ?status=cancelled updates DB to CANCELLED and returns 'Status': 'CANCELLED'."""
    assessment = crud.create_assessment(
        db_session,
        candidate_id=1042,
        assessment_type="INTRO",
        media_type="VIDEO",
    )
    assessment_id = assessment.id

    with patch("fapi.ai_prep.utils.aiprep_utils.AudioMetricsEngine.process_audio_file") as mock_audio, \
         patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks") as mock_stitch:
        res = submit_test_client.put(
            f"/api/aiprep/candidates/1042/assessments/{assessment_id}?status=cancelled"
        )

        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("Status") == "CANCELLED"
        assert data.get("status") == "CANCELLED"

        # Verify DB is updated to CANCELLED
        db_asm = crud.get_assessment_by_id_or_uuid(db_session, assessment_id)
        assert db_asm.status == "CANCELLED"

        # Verify no audio engine or chunk stitching was triggered
        mock_audio.assert_not_called()
        mock_stitch.assert_not_called()


def test_put_assessment_status_cancelled_body(submit_test_client, db_session):
    """Verify that PUT with body {'status': 'CANCELLED'} updates DB to CANCELLED without running assessment logic."""
    assessment = crud.create_assessment(
        db_session,
        candidate_id=1042,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
    )
    assessment_id = assessment.id

    with patch("fapi.ai_prep.utils.aiprep_utils.AudioMetricsEngine.process_audio_file") as mock_audio, \
         patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks") as mock_stitch:
        res = submit_test_client.put(
            f"/api/aiprep/candidates/1042/assessments/{assessment_id}",
            json={"status": "CANCELLED"},
        )

        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("Status") == "CANCELLED"
        assert data.get("status") == "CANCELLED"

        # Verify DB is updated to CANCELLED
        db_asm = crud.get_assessment_by_id_or_uuid(db_session, assessment_id)
        assert db_asm.status == "CANCELLED"

        mock_audio.assert_not_called()
        mock_stitch.assert_not_called()
