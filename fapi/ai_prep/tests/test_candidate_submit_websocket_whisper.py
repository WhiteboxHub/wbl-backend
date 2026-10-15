"""Unit & Integration Tests for Candidate Submission with WebSocket Media and Decrypted Candidate Key."""
import os
import shutil
import tempfile
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
from fapi.ai_prep.core.websocket_stream_manager import (
    DEFAULT_SCRATCH_ROOT,
    WebSocketStreamSession,
    _ACTIVE_SESSIONS,
    remove_stream_session,
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
    cand = db_session.query(CandidateORM).filter(CandidateORM.id == 2042).first()
    if not cand:
        cand = CandidateORM(
            id=2042,
            full_name="Alex Tech",
            email="alex2042@example.com",
        )
        db_session.add(cand)
        db_session.commit()

    user = AuthUserORM(
        id=2042,
        uname="alex2042@example.com",
        fullname="Alex Tech",
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


def test_submit_uses_preassembled_websocket_media_and_bypasses_stitching(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    When a WebSocket streaming session finished and left audio.wav or video.webm in scratch,
    submission must detect preassembled media and bypass chunk stitching.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.core.websocket_stream_manager.DEFAULT_SCRATCH_ROOT", tmp_path)

    assessment = crud.create_assessment(
        db_session,
        candidate_id=2042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    # Create pre-assembled audio.wav in scratch root
    scratch_dir = tmp_path / f"assessment_{assessment_id}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    preassembled_wav = scratch_dir / "audio.wav"
    preassembled_wav.write_bytes(b"RIFF44WAVEfmt mock wav audio content")

    mock_audio_result = {
        "spoken_content": {"full_text": "I solved the vector database latency with Milvus indexing.", "word_count": 9, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 15.0, "wpm": 130, "total_audio_duration_seconds": 20.0},
    }

    with patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio, \
         patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks") as mock_stitch, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/2042/assessments/{assessment_id}",
            json={"total_chunks_uploaded": 0, "is_final": True, "client_duration_seconds": 20.0},
        )

        assert resp.status_code == 200
        # Assert stitch was BYPASSED because preassembled media was found
        mock_stitch.assert_not_called()
        # Assert AudioMetricsEngine was called with the preassembled file
        mock_audio.assert_called_once()
        called_path = mock_audio.call_args[0][0]
        assert "audio.wav" in called_path


def test_submit_retrieves_candidate_decrypted_key_for_whisper(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    The backend securely queries candidate's AES-256 key via crud.get_candidate_llm_config
    and invokes AudioMetricsEngine with provider_name='openai' and candidate's decrypted key.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.core.websocket_stream_manager.DEFAULT_SCRATCH_ROOT", tmp_path)

    assessment = crud.create_assessment(
        db_session,
        candidate_id=2042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    scratch_dir = tmp_path / f"assessment_{assessment_id}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    preassembled_wav = scratch_dir / "audio.wav"
    preassembled_wav.write_bytes(b"RIFF44WAVEfmt mock wav audio content")

    mock_llm_cfg = {
        "is_configured": True,
        "api_key": "sk-proj-candidate-encrypted-vault-secret-key-123",
        "provider": "openai",
        "model": "gpt-4o",
    }

    mock_audio_result = {
        "spoken_content": {"full_text": "Candidate technical explanation with OpenAI Whisper.", "word_count": 7, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 10.0, "wpm": 120, "total_audio_duration_seconds": 15.0},
    }

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value=mock_llm_cfg) as mock_cfg, \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/2042/assessments/{assessment_id}",
            json={"total_chunks_uploaded": 0, "is_final": True, "client_duration_seconds": 15.0},
        )

        assert resp.status_code == 200
        mock_cfg.assert_called()
        mock_audio.assert_called_once()
        _, kwargs = mock_audio.call_args
        assert kwargs.get("provider_name") == "openai"
        assert kwargs.get("openai_api_key") == "sk-proj-candidate-encrypted-vault-secret-key-123"


def test_submit_header_and_payload_fallback_override(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    When candidate passes custom X-OpenAI-Key header or payload override, it takes precedence as fallback.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.core.websocket_stream_manager.DEFAULT_SCRATCH_ROOT", tmp_path)

    assessment = crud.create_assessment(
        db_session,
        candidate_id=2042,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": True},
    )
    assessment_id = assessment.id

    scratch_dir = tmp_path / f"assessment_{assessment_id}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    preassembled_video = scratch_dir / "video.webm"
    preassembled_video.write_bytes(b"\x1a\x45\xdf\xa3 mock webm video content")

    mock_audio_result = {
        "spoken_content": {"full_text": "Testing fallback header override for whisper key.", "word_count": 7, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 12.0, "wpm": 125, "total_audio_duration_seconds": 18.0},
    }

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value={"is_configured": False}) as mock_cfg, \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        # Test header override
        resp = submit_test_client.put(
            f"/api/aiprep/candidates/2042/assessments/{assessment_id}",
            json={"total_chunks_uploaded": 0, "is_final": True, "client_duration_seconds": 18.0},
            headers={"X-OpenAI-Key": "sk-proj-override-header-key-999"},
        )

        assert resp.status_code == 200
        mock_audio.assert_called_once()
        _, kwargs = mock_audio.call_args
        assert kwargs.get("provider_name") == "openai"
        assert kwargs.get("openai_api_key") == "sk-proj-override-header-key-999"


def test_submit_payload_body_key_override(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    When candidate passes openai_api_key in PUT body payload, it acts as fallback/override.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.core.websocket_stream_manager.DEFAULT_SCRATCH_ROOT", tmp_path)

    assessment = crud.create_assessment(
        db_session,
        candidate_id=2042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    scratch_dir = tmp_path / f"assessment_{assessment_id}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    preassembled_wav = scratch_dir / "audio.wav"
    preassembled_wav.write_bytes(b"RIFF44WAVEfmt mock wav audio content")

    mock_audio_result = {
        "spoken_content": {"full_text": "Candidate explanation with body key.", "word_count": 5, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 10.0, "wpm": 120, "total_audio_duration_seconds": 15.0},
    }

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value={"is_configured": False}), \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/2042/assessments/{assessment_id}",
            json={
                "total_chunks_uploaded": 0,
                "is_final": True,
                "client_duration_seconds": 15.0,
                "openai_api_key": "sk-proj-override-body-key-456",
            },
        )

        assert resp.status_code == 200
        mock_audio.assert_called_once()
        _, kwargs = mock_audio.call_args
        assert kwargs.get("provider_name") == "openai"
        assert kwargs.get("openai_api_key") == "sk-proj-override-body-key-456"


def test_submit_without_candidate_key_falls_back_to_default_engine(submit_test_client, db_session, tmp_path, monkeypatch):
    """
    When candidate has no key configured and passes no override, AudioMetricsEngine runs with default provider.
    """
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.core.websocket_stream_manager.DEFAULT_SCRATCH_ROOT", tmp_path)

    assessment = crud.create_assessment(
        db_session,
        candidate_id=2042,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        consent={"save_recording": True, "save_transcript": True, "video_analytics": False},
    )
    assessment_id = assessment.id

    scratch_dir = tmp_path / f"assessment_{assessment_id}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    preassembled_wav = scratch_dir / "audio.wav"
    preassembled_wav.write_bytes(b"RIFF44WAVEfmt mock wav audio content")

    mock_audio_result = {
        "spoken_content": {"full_text": "Default local transcription fallback.", "word_count": 4, "segments": []},
        "audio_telemetry": {"speaking_duration_seconds": 8.0, "wpm": 110, "total_audio_duration_seconds": 12.0},
    }

    with patch("fapi.ai_prep.crud.get_candidate_llm_config", return_value={"is_configured": False}), \
         patch("fapi.ai_prep.core.audio_engine.metrics_engine.AudioMetricsEngine.process_audio_file", return_value=mock_audio_result) as mock_audio, \
         patch("fapi.ai_prep.orchestrator.assessment_orchestrator.run_full_evaluation", new_callable=AsyncMock) as mock_eval:

        resp = submit_test_client.put(
            f"/api/aiprep/candidates/2042/assessments/{assessment_id}",
            json={"total_chunks_uploaded": 0, "is_final": True, "client_duration_seconds": 12.0},
        )

        assert resp.status_code == 200
        mock_audio.assert_called_once()
        _, kwargs = mock_audio.call_args
        # Provider should not be forced to openai without key
        assert kwargs.get("provider_name") is None
        assert "openai_api_key" not in kwargs
