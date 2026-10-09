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


def test_get_assessment_detail_sse_streaming(test_client, db_session):
    """GET with stream=true returns text/event-stream with no-buffering headers."""
    asm = crud.create_assessment(
        db_session,
        candidate_id=501,
        assessment_type="INTRO",
        media_type="VIDEO",
    )
    crud.update_assessment_status(db_session, asm.id, "COMPLETED")

    res = test_client.get(f"/api/aiprep/candidates/501/assessments/{asm.id}?stream=true")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert res.headers.get("cache-control") == "no-cache"
    assert res.headers.get("x-accel-buffering") == "no"

    # Verify event stream payload contains expected event structure
    chunks = list(res.iter_text())
    content = "".join(chunks) or res.text
    assert "data: " in content
    assert '"status": "COMPLETED"' in content
    assert '"progress": 100' in content


def test_get_assessment_detail_sse_forbidden_other_candidate(test_client, db_session):
    """Attempting to stream another candidate's assessment returns 403 Forbidden."""
    other_asm = crud.create_assessment(
        db_session,
        candidate_id=999,  # Belongs to candidate 999, not 501
        assessment_type="INTRO",
        media_type="VIDEO",
    )

    res = test_client.get(f"/api/aiprep/candidates/501/assessments/{other_asm.id}?stream=true")
    assert res.status_code == 403


def test_stream_manager_push_events_delivered_to_sse(test_client, db_session):
    """Verifies strict push-based streaming emits pipeline events without polling."""
    from fapi.ai_prep.utils.stream_manager import stream_manager

    asm = crud.create_assessment(
        db_session,
        candidate_id=501,
        assessment_type="INTRO",
        media_type="VIDEO",
    )
    crud.update_assessment_status(db_session, asm.id, "EVALUATING")

    stream_manager.publish_progress(
        asm.id,
        status="EVALUATING",
        step="Analyzing Candidate Performance with AI",
        progress=65,
    )

    stream_manager.publish_progress(
        asm.id,
        status="COMPLETED",
        step="Report Generated",
        progress=100,
    )

    res = test_client.get(f"/api/aiprep/candidates/501/assessments/{asm.id}?stream=true")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    content = "".join(list(res.iter_text()))
    assert "data: " in content
    assert '"status": "COMPLETED"' in content
    assert '"progress": 100' in content
    assert '"step": "Report Generated"' in content
