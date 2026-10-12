"""Tests for SSE Streaming on GET /api/aiprep/candidates/{id}/assessments/{assessment_id}?stream=true"""
import os
import pytest
from unittest.mock import patch
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
)

from fapi.ai_prep.tests.test_candidate_submit_assessment import test_engine, TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_sse_db():
    tables = [
        AuthUserORM.__table__,
        CandidateORM.__table__,
        AiPrepAssessmentORM.__table__,
        AiPrepAssessmentDataORM.__table__,
        AiPrepAssessmentReportORM.__table__,
    ]
    Base.metadata.create_all(bind=test_engine, tables=tables)
    yield


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_candidate_user(db_session):
    cand = db_session.query(CandidateORM).filter(CandidateORM.id == 501).first()
    if not cand:
        cand = CandidateORM(
            id=501,
            full_name="Candidate One",
            email="candidate100@test.com",
        )
        db_session.add(cand)
        db_session.commit()

    user = AuthUserORM(
        id=501,
        uname="candidate100@test.com",
        fullname="Candidate One",
        role="candidate",
    )
    setattr(user, "is_employee", False)
    setattr(user, "is_admin", False)
    return user


@pytest.fixture
def test_client(mock_candidate_user):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return mock_candidate_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_get_assessment_detail_regular_json(test_client, db_session):
    """GET without stream=true returns standard application/json CandidateAssessmentUnifiedResponse."""
    asm = crud.create_assessment(
        db_session,
        candidate_id=501,
        assessment_type="INTRO",
        media_type="VIDEO",
    )

    res = test_client.get(f"/api/aiprep/candidates/501/assessments/{asm.id}")
    assert res.status_code == 200
    assert "application/json" in res.headers.get("content-type", "")
    data = res.json()
    assert data["id"] == asm.id
    assert "data" in data


def test_put_submit_assessment_sse_streaming_headers(test_client, db_session):
    """PUT with stream=true returns text/event-stream with no-buffering headers."""
    asm = crud.create_assessment(
        db_session,
        candidate_id=501,
        assessment_type="INTRO",
        media_type="VIDEO",
    )
    crud.update_assessment_status(db_session, asm.id, "IN_PROGRESS")

    res = test_client.put(
        f"/api/aiprep/candidates/501/assessments/{asm.id}?stream=true",
        json={"total_chunks_uploaded": 0, "is_final": True},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert res.headers.get("cache-control") == "no-cache"
    assert res.headers.get("x-accel-buffering") == "no"


def test_put_submit_assessment_sse_forbidden_other_candidate(test_client, db_session):
    """Attempting to stream-submit another candidate's assessment returns 403 Forbidden."""
    other_asm = crud.create_assessment(
        db_session,
        candidate_id=999,  # Belongs to candidate 999, not 501
        assessment_type="INTRO",
        media_type="VIDEO",
    )

    res = test_client.put(
        f"/api/aiprep/candidates/501/assessments/{other_asm.id}?stream=true",
        json={"total_chunks_uploaded": 0, "is_final": True},
    )
    assert res.status_code == 403


def test_put_submit_assessment_direct_sse_streaming(test_client, db_session):
    """Verifies single API call PUT submission streaming directly over the response."""
    asm = crud.create_assessment(
        db_session,
        candidate_id=501,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
    )
    crud.update_assessment_status(db_session, asm.id, "IN_PROGRESS")

    payload = {
        "total_chunks_uploaded": 1,
        "is_final": True,
        "client_duration_seconds": 15.0,
    }

    with patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks", return_value="assembled.wav"), \
         patch("fapi.ai_prep.utils.aiprep_utils.AudioMetricsEngine.process_audio_file") as mock_audio, \
         patch("fapi.ai_prep.utils.aiprep_utils.evaluate_gatekeeper_flag", return_value=True):
        mock_audio.return_value = {
            "spoken_content": {"full_text": "Sample answer", "word_count": 2, "segments": []},
            "audio_telemetry": {"speaking_duration_seconds": 5.0, "wpm": 24, "silence_ratio": 0.5},
        }

        res = test_client.put(
            f"/api/aiprep/candidates/501/assessments/{asm.id}?stream=true",
            json=payload,
        )

        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")

        content = "".join(list(res.iter_text()))
        assert "data: " in content
        assert '"status": "PROCESSING"' in content
        assert '"status": "COMPLETED"' in content
        assert '"progress": 100' in content
        assert '"step"' not in content

