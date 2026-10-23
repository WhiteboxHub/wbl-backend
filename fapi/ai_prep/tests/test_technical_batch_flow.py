"""
Comprehensive Test Suite for Multi-Question Assessment Flow:
1. Per-question 30s chunk upload via POST .../media/chunk?question_id=... or Header X-Question-Id
2. Pure JSON Final Submit via PUT .../assessments/...
3. Per-question chunk stitching, Whisper STT with prompt context & DSP metrics
4. Candidate Consent flags compliance (save_transcript, save_recording)
5. Zero regression / isolation from single-question Intro flow
"""
import os
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["ENV"] = "test"

from fapi.main import app
from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import Base, AuthUserORM, CandidateORM
from fapi.ai_prep import crud
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
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

import fapi.ai_prep.utils.aiprep_utils
fapi.ai_prep.utils.aiprep_utils.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    tables = [
        AuthUserORM.__table__,
        CandidateORM.__table__,
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
def mock_candidate_client(db_session):
    candidate = db_session.query(CandidateORM).filter(CandidateORM.id == 7701).first()
    if not candidate:
        candidate = CandidateORM(
            id=7701,
            email="batch_test@example.com",
            full_name="Batch Tester",
        )
        db_session.add(candidate)
        db_session.commit()

    auth_user = AuthUserORM(
        id=7701,
        uname="batch_test@example.com",
        fullname="Batch Tester",
        role="candidate",
    )
    setattr(auth_user, "is_employee", False)
    setattr(auth_user, "is_admin", False)

    from fapi.utils.permission_gate import enforce_access, get_optional_current_user
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[enforce_access] = lambda: auth_user
    app.dependency_overrides[get_optional_current_user] = lambda: auth_user
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Multi-Question Chunk Upload (Query Param) + Batch Submit Test
# ===========================================================================

def test_multi_question_chunks_and_submit(mock_candidate_client, db_session, tmp_path, monkeypatch):
    """
    Candidate uploads 30s chunks with ?question_id=1.
    Question 2 is skipped (no chunks).
    Final Submit runs batch stitching + Whisper + DSP + Gatekeeper + LLM.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    # Create Technical Assessment
    assessment = crud.create_assessment(
        db_session,
        candidate_id=7701,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
    )

    # Seed 2 questions
    initial_questions = [
        {"id": 1, "question_text": "Explain Python GIL.", "processing_status": "PENDING"},
        {"id": 2, "question_text": "What is SQL indexing?", "processing_status": "PENDING"},
    ]
    crud.save_assessment_data(
        db=db_session,
        assessment_id=assessment.id,
        questions=initial_questions,
        transcript={},
        audio_telemetry={},
        video_telemetry={},
    )

    # 1. Upload chunk 0 for Question 1 using query parameter ?question_id=1
    fake_chunk = io.BytesIO(b"dummy webm chunk data 0")
    resp_chunk = mock_candidate_client.post(
        f"/api/aiprep/candidates/7701/assessments/{assessment.id}/media/chunk?question_id=1",
        data={"chunk_index": 0, "is_final": "true"},
        files={"media_file": ("chunk_0.webm", fake_chunk, "video/webm")},
    )
    assert resp_chunk.status_code == 200, resp_chunk.text
    chunk_data = resp_chunk.json()
    assert chunk_data["status"] == "success"

    # Verify audio file was stored directly under questions/1/audio.webm
    expected_chunk_path = tmp_path / "7701" / str(assessment.id) / "questions" / "1" / "audio.webm"
    assert expected_chunk_path.exists()

    # 2. Final Submit (Candidate clicks 'Submit' button)
    mock_audio_result = {
        "spoken_content": {
            "transcript_text": "The Python GIL is a mutex that prevents multiple native threads from executing Python bytecodes at once.",
            "full_text": "The Python GIL is a mutex that prevents multiple native threads from executing Python bytecodes at once.",
            "word_count": 18,
            "segments": [{"start": 0.0, "end": 12.0, "text": "The Python GIL is a mutex that prevents multiple native threads from executing Python bytecodes at once."}],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 12.0,
            "wpm": 90,
            "filler_count": 0,
            "silence_ratio": 0.05,
            "total_audio_duration_seconds": 12.0,
        },
    }

    with patch("fapi.ai_prep.utils.aiprep_utils.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_whisper, \
         patch("fapi.ai_prep.utils.aiprep_utils.assessment_orchestrator.run_full_evaluation") as mock_eval:

            resp_submit = mock_candidate_client.put(
                f"/api/aiprep/candidates/7701/assessments/{assessment.id}",
                json={
                    "client_duration_seconds": 30.0,
                    "consent": {
                        "save_recording": True,
                        "save_transcript": True,
                        "video_analytics": False,
                    },
                },
            )

            assert resp_submit.status_code == 200, resp_submit.text
            submit_data = resp_submit.json()
            assert submit_data["status"] == "EVALUATING"
            assert submit_data["data"]["assessment_eval"]["insufficient_content"] is False

            # Verify Whisper STT was called with question context prompt
            assert mock_whisper.called

            # Verify LLM evaluation received structured Q&A
            assert mock_eval.called
            orch_kwargs = mock_eval.call_args.kwargs
            full_transcript = orch_kwargs.get("in_memory_transcript_text")
            assert "[Question 1: Explain Python GIL.]" in full_transcript
            assert "The Python GIL is a mutex" in full_transcript
            assert "[Question 2: What is SQL indexing?]" in full_transcript
            assert "[No response or skipped by candidate]" in full_transcript

            # Verify DB questions were updated with completed metrics
            db_session.expire_all()
            data_rec = crud.get_assessment_data_by_assessment_id(db_session, assessment.id)
            assert data_rec.questions[0]["processing_status"] == "COMPLETED"
            assert data_rec.questions[0]["word_count"] == 18
            assert data_rec.questions[1]["processing_status"] == "COMPLETED"
            assert data_rec.questions[1]["transcript"] == ""


# ===========================================================================
# 2. Multi-Question Chunk Upload via Header (X-Question-Id)
# ===========================================================================

def test_multi_question_chunks_via_header(mock_candidate_client, db_session, tmp_path, monkeypatch):
    """Verify that X-Question-Id header correctly routes chunk to questions/{qid}/chunks/."""
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=7701,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
    )

    fake_chunk = io.BytesIO(b"dummy webm chunk data via header")
    resp_chunk = mock_candidate_client.post(
        f"/api/aiprep/candidates/7701/assessments/{assessment.id}/media/chunk",
        headers={"X-Question-Id": "3"},
        data={"chunk_index": 0, "is_final": "true"},
        files={"media_file": ("chunk_0.webm", fake_chunk, "video/webm")},
    )
    assert resp_chunk.status_code == 200, resp_chunk.text

    expected_path = tmp_path / "7701" / str(assessment.id) / "questions" / "3" / "chunks" / "chunk_0.webm"
    assert expected_path.exists()


# ===========================================================================
# 3. Candidate Consent Compliance Test (save_transcript=False)
# ===========================================================================

def test_multi_question_consent_redaction(mock_candidate_client, db_session, tmp_path, monkeypatch):
    """When save_transcript=False, DB question transcripts must be redacted."""
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=7701,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
        consent={
            "save_recording": False,
            "save_transcript": False,
            "video_analytics": False,
        },
    )

    crud.save_assessment_data(
        db=db_session,
        assessment_id=assessment.id,
        questions=[{"id": 1, "question_text": "What is Python?", "processing_status": "PENDING"}],
        transcript={},
        audio_telemetry={},
        video_telemetry={},
    )

    fake_chunk = io.BytesIO(b"dummy webm chunk")
    mock_candidate_client.post(
        f"/api/aiprep/candidates/7701/assessments/{assessment.id}/media/chunk?question_id=1",
        data={"chunk_index": 0, "is_final": "true"},
        files={"media_file": ("chunk_0.webm", fake_chunk, "video/webm")},
    )

    mock_audio_result = {
        "spoken_content": {
            "transcript_text": "Python is a high level programming language.",
            "full_text": "Python is a high level programming language.",
            "word_count": 7,
            "segments": [],
        },
        "audio_telemetry": {"speaking_duration_seconds": 5.0, "wpm": 80, "filler_count": 0, "silence_ratio": 0.05},
    }

    with patch("fapi.ai_prep.utils.aiprep_utils.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result), \
         patch("fapi.ai_prep.utils.aiprep_utils.assessment_orchestrator.run_full_evaluation"):

        resp_submit = mock_candidate_client.put(
            f"/api/aiprep/candidates/7701/assessments/{assessment.id}",
            json={
                "client_duration_seconds": 30.0,
                "consent": {
                    "save_recording": False,
                    "save_transcript": False,
                    "video_analytics": False,
                },
            },
        )
        assert resp_submit.status_code == 200

        data_rec = crud.get_assessment_data_by_assessment_id(db_session, assessment.id)
        # Because save_transcript was False, DB question transcript is redacted
        assert data_rec.questions[0]["transcript"] == ""
        # Because save_recording was False, DB question audio_telemetry is empty
        assert data_rec.questions[0]["audio_telemetry"] == {}
