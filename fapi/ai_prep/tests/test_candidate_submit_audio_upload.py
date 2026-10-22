"""Tests for Step 1: Single Audio Multipart Upload and JSON Backward Compatibility."""
import os
import json
import shutil
from unittest.mock import patch, MagicMock, AsyncMock
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

import fapi.db.database

if getattr(fapi.db.database, "_is_test_engine", False):
    test_engine = fapi.db.database.engine
    TestingSessionLocal = fapi.db.database.SessionLocal
else:
    sqlite_test_db_url = "sqlite:///:memory:"
    test_engine = create_engine(
        sqlite_test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    fapi.db.database.SessionLocal = TestingSessionLocal
    fapi.db.database.engine = test_engine
    fapi.db.database._is_test_engine = True


Base.metadata.create_all(
    bind=test_engine,
    tables=[
        AuthUserORM.__table__,
        CandidateORM.__table__,
        CandidateMarketingORM.__table__,
        CandidateLlmApiKeyORM.__table__,
        AiPrepAssessmentORM.__table__,
        AiPrepAssessmentDataORM.__table__,
        AiPrepAssessmentReportORM.__table__,
        AiPrepQuestionORM.__table__,
    ],
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    yield


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
    cand = db_session.query(CandidateORM).filter(CandidateORM.id == 3042).first()
    if not cand:
        cand = CandidateORM(
            id=3042,
            full_name="Morgan Audio",
            email="morgan3042@example.com",
        )
        db_session.add(cand)
        db_session.commit()

    user = AuthUserORM(
        id=3042,
        uname="morgan3042@example.com",
        fullname="Morgan Audio",
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

    from fapi.utils.permission_gate import enforce_access

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[enforce_access] = lambda: mock_candidate_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_submit_assessment_with_direct_multipart_audio_upload(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    Step 1 Core Requirement:
    Candidate submits assessment via multipart/form-data containing the completed audio file and assessment_data.
    The audio is saved directly to disk, bypassing chunk stitching.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=3042,
        assessment_type="INTRO",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    mock_audio_result = {
        "spoken_content": {
            "full_text": "I have four years of experience building Python microservices with FastAPI.",
            "word_count": 10,
            "segments": [{"start": 0.0, "end": 4.5, "text": "I have four years of experience."}],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 12.0,
            "wpm": 125,
            "filler_count": 0,
            "silence_ratio": 0.1,
            "total_audio_duration_seconds": 15.0,
        },
    }

    raw_audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00mock audio binary content"

    with patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio_engine, \
         patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks") as mock_stitch, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/3042/assessments/{assessment_id}",
            files={"audio": ("intro.webm", raw_audio_bytes, "audio/webm")},
            data={"assessment_data": json.dumps({"is_final": True, "client_duration_seconds": 15.0})},
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == assessment_id
        assert data["media_type"] == "AUDIO"

        # Verify chunk stitching was completely bypassed
        mock_stitch.assert_not_called()

        # Verify AudioMetricsEngine processed the saved audio file
        mock_audio_engine.assert_called_once()
        processed_file_path = mock_audio_engine.call_args[0][0]
        assert processed_file_path.endswith("audio.webm")
        assert os.path.exists(processed_file_path)
        with open(processed_file_path, "rb") as f:
            assert f.read() == raw_audio_bytes


def test_submit_assessment_with_json_payload_backward_compatibility(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    Existing JSON body submissions (e.g., chunk-based clients or legacy requests)
    must continue working without any regression.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=3042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    mock_audio_result = {
        "spoken_content": {"full_text": "Legacy chunk submission test text.", "word_count": 5, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 10.0, "wpm": 120, "total_audio_duration_seconds": 15.0},
    }

    dummy_stitched_file = tmp_path / "stitched.webm"
    dummy_stitched_file.write_bytes(b"dummy stitched media")

    with patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks", return_value=str(dummy_stitched_file)) as mock_stitch, \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio_engine, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/3042/assessments/{assessment_id}",
            json={"total_chunks_uploaded": 3, "is_final": True, "client_duration_seconds": 15.0},
        )

        assert resp.status_code == 200, resp.text
        # In JSON mode without direct audio file, legacy stitching is invoked
        mock_stitch.assert_called_once()
        mock_audio_engine.assert_called_once_with(str(dummy_stitched_file))


def test_submit_assessment_cancelled_via_query_param(submit_test_client, db_session):
    """
    Query parameter status=cancelled must continue working cleanly.
    """
    assessment = crud.create_assessment(
        db_session,
        candidate_id=3042,
        assessment_type="INTRO",
        media_type="AUDIO",
    )
    assessment_id = assessment.id

    resp = submit_test_client.put(
        f"/api/aiprep/candidates/3042/assessments/{assessment_id}?status=cancelled"
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_submit_assessment_resolves_candidate_openai_key(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    Step 2 Core Requirement:
    Candidate with configured OpenAI key in DB triggers AudioMetricsEngine with provider_name='openai'
    and passes openai_api_key down to the audio engine and evaluation pipeline.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=3042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    mock_audio_result = {
        "spoken_content": {"full_text": "Technical answer about distributed tracing with OpenTelemetry.", "word_count": 8, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 10.0, "wpm": 120, "total_audio_duration_seconds": 12.0},
    }

    mock_llm_cfg = {
        "is_configured": True,
        "api_key": "sk-candidate-db-key-999",
        "provider": "openai",
    }

    raw_audio = b"RIFFmockaudioforopenaiwhisper"

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value=mock_llm_cfg), \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio_engine, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/3042/assessments/{assessment_id}",
            files={"audio": ("technical_answer.webm", raw_audio, "audio/webm")},
            data={"assessment_data": json.dumps({"is_final": True, "client_duration_seconds": 12.0})},
        )

        assert resp.status_code == 200, resp.text
        # Assert AudioMetricsEngine was called with provider_name="openai" and candidate's decrypted key
        mock_audio_engine.assert_called_once()
        _, kwargs = mock_audio_engine.call_args
        assert kwargs.get("provider_name") == "openai"
        assert kwargs.get("openai_api_key") == "sk-candidate-db-key-999"


def test_submit_assessment_header_key_fallback(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    Step 2: Candidate supplies x-openai-key header which is passed into audio engine and evaluation pipeline.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    assessment = crud.create_assessment(
        db_session,
        candidate_id=3042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    mock_audio_result = {
        "spoken_content": {"full_text": "Answer evaluated with header key.", "word_count": 5, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 8.0, "wpm": 110, "total_audio_duration_seconds": 10.0},
    }

    raw_audio = b"RIFFmockaudioforheaderkey"

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value={"is_configured": False}), \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio_engine, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/3042/assessments/{assessment_id}",
            files={"audio": ("technical_answer.webm", raw_audio, "audio/webm")},
            data={"assessment_data": json.dumps({"is_final": True, "client_duration_seconds": 10.0})},
            headers={"x-openai-key": "sk-header-provided-key-888"},
        )

        assert resp.status_code == 200, resp.text
        mock_audio_engine.assert_called_once()
        _, kwargs = mock_audio_engine.call_args
        assert kwargs.get("provider_name") == "openai"
        assert kwargs.get("openai_api_key") == "sk-header-provided-key-888"


def test_openai_whisper_provider_transcribe_unit(tmp_path):
    """
    Step 2 Unit Test:
    OpenAIWhisperProvider parses OpenAI verbose_json response correctly with word timestamps.
    """
    from fapi.ai_prep.core.audio_engine.providers import OpenAIWhisperProvider

    dummy_audio = tmp_path / "test.webm"
    dummy_audio.write_bytes(b"dummy audio binary data")

    provider = OpenAIWhisperProvider()

    mock_word1 = MagicMock(word="Hello", start=0.0, end=0.45)
    mock_word2 = MagicMock(word="world", start=0.5, end=0.92)
    mock_resp = MagicMock()
    mock_resp.text = "Hello world"
    mock_resp.duration = 1.2
    mock_resp.words = [mock_word1, mock_word2]

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=mock_client):
        res = provider.transcribe(
            audio_path=str(dummy_audio),
            openai_api_key="sk-test-key",
        )

        assert res["transcript_text"] == "Hello world"
        assert res["duration"] == 1.2
        assert len(res["word_timestamps"]) == 2
        assert res["word_timestamps"][0] == {"word": "Hello", "start": 0.0, "end": 0.45}
        assert res["word_timestamps"][1] == {"word": "world", "start": 0.5, "end": 0.92}
        mock_client.audio.transcriptions.create.assert_called_once()

