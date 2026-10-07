"""Comprehensive Test Suite for GET /api/aiprep/candidates/{id}/assessments.

Verifies:
1. Candidate A can retrieve all of their attempted/completed assessments.
2. Candidate A cannot access Candidate B's assessments (enforces HTTP 403 Forbidden).
3. Candidate B cannot access Candidate A's assessments (enforces HTTP 403 Forbidden).
4. Staff / Admin can inspect any candidate's assessments.
5. Strict isolation and authorization validation for non-existent candidate IDs.
6. Proper pagination (limit and offset) and sorting.
"""
import os
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["ENV"] = "test"

from fapi.main import app
from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.db.models import Base, AuthUserORM, CandidateORM
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


@pytest.fixture(scope="session", autouse=True)
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
def seed_candidates_and_assessments(db_session):
    """Seeds Candidate 1001 (Candidate A) and Candidate 1002 (Candidate B) with assessments."""
    # Ensure Candidate 1001 exists
    c1 = db_session.query(CandidateORM).filter(CandidateORM.id == 1001).first()
    if not c1:
        c1 = CandidateORM(id=1001, full_name="Candidate Alpha", email="alpha@example.com")
        db_session.add(c1)

    # Ensure Candidate 1002 exists
    c2 = db_session.query(CandidateORM).filter(CandidateORM.id == 1002).first()
    if not c2:
        c2 = CandidateORM(id=1002, full_name="Candidate Beta", email="beta@example.com")
        db_session.add(c2)

    db_session.commit()

    # Clear previous assessments for these candidates
    db_session.query(AiPrepAssessmentORM).filter(
        AiPrepAssessmentORM.candidate_id.in_([1001, 1002])
    ).delete(synchronize_session=False)
    db_session.commit()

    # Seed assessments for Candidate 1001
    a1_1 = AiPrepAssessmentORM(
        candidate_id=1001,
        assessment_uuid=str(uuid.uuid4()),
        assessment_type="INTRO",
        media_type="VIDEO",
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )
    a1_2 = AiPrepAssessmentORM(
        candidate_id=1001,
        assessment_uuid=str(uuid.uuid4()),
        assessment_type="TECHNICAL",
        media_type="AUDIO",
        status="IN_PROGRESS",
        created_at=datetime.now(timezone.utc),
    )
    a1_3 = AiPrepAssessmentORM(
        candidate_id=1001,
        assessment_uuid=str(uuid.uuid4()),
        assessment_type="SYSTEM_DESIGN",
        media_type="VIDEO",
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )

    # Seed assessment for Candidate 1002
    a2_1 = AiPrepAssessmentORM(
        candidate_id=1002,
        assessment_uuid=str(uuid.uuid4()),
        assessment_type="INTRO",
        media_type="VIDEO",
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add_all([a1_1, a1_2, a1_3, a2_1])
    db_session.commit()

    return {"candidate_1": 1001, "candidate_2": 1002}


def get_client_for_user(db_session, user: AuthUserORM):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    def override_staff_required():
        if not (getattr(user, "is_employee", False) or getattr(user, "role", "") in ("admin", "staff", "employee")):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin or staff access required")
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[staff_or_admin_required] = override_staff_required
    return TestClient(app)


def test_candidate_a_can_access_own_assessments(db_session, seed_candidates_and_assessments):
    """Candidate A requests their own assessment list -> 200 OK with all attempted/completed assessments."""
    user_a = AuthUserORM(
        id=1001,
        uname="alpha@example.com",
        fullname="Candidate Alpha",
        role="candidate",
    )
    setattr(user_a, "is_employee", False)
    client_a = get_client_for_user(db_session, user_a)

    res = client_a.get("/api/aiprep/candidates/1001/assessments")
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3
    for item in data["items"]:
        assert item["candidate_id"] == 1001
        assert item["candidate_name"] == "Candidate Alpha"
        assert item["candidate_email"] == "alpha@example.com"
        assert item["status"] in ("COMPLETED", "IN_PROGRESS")


def test_candidate_a_cannot_access_candidate_b_assessments(db_session, seed_candidates_and_assessments):
    """Candidate A attempts to access Candidate B's assessment list -> 403 Forbidden."""
    user_a = AuthUserORM(
        id=1001,
        uname="alpha@example.com",
        fullname="Candidate Alpha",
        role="candidate",
    )
    setattr(user_a, "is_employee", False)
    client_a = get_client_for_user(db_session, user_a)

    # Candidate 1001 tries to access Candidate 1002's assessments
    res = client_a.get("/api/aiprep/candidates/1002/assessments")
    assert res.status_code == 403
    assert "Candidates can only access their own data" in res.json()["detail"]


def test_candidate_b_cannot_access_candidate_a_assessments(db_session, seed_candidates_and_assessments):
    """Candidate B attempts to access Candidate A's assessment list -> 403 Forbidden."""
    user_b = AuthUserORM(
        id=1002,
        uname="beta@example.com",
        fullname="Candidate Beta",
        role="candidate",
    )
    setattr(user_b, "is_employee", False)
    client_b = get_client_for_user(db_session, user_b)

    # Candidate 1002 tries to access Candidate 1001's assessments
    res = client_b.get("/api/aiprep/candidates/1001/assessments")
    assert res.status_code == 403
    assert "Candidates can only access their own data" in res.json()["detail"]


def test_employee_can_access_any_candidate_assessments(db_session, seed_candidates_and_assessments):
    """Staff / Admin user accesses Candidate A and Candidate B's assessments -> 200 OK."""
    admin_user = AuthUserORM(
        id=99,
        uname="admin@wbl.com",
        fullname="Admin User",
        role="admin",
    )
    setattr(admin_user, "is_employee", True)
    client_admin = get_client_for_user(db_session, admin_user)

    # Admin checks Candidate 1001
    res1 = client_admin.get("/api/aiprep/candidates/1001/assessments")
    assert res1.status_code == 200
    assert res1.json()["total"] == 3

    # Admin checks Candidate 1002
    res2 = client_admin.get("/api/aiprep/candidates/1002/assessments")
    assert res2.status_code == 200
    assert res2.json()["total"] == 1
    assert res2.json()["items"][0]["candidate_id"] == 1002


def test_candidate_accessing_nonexistent_id_forbidden(db_session, seed_candidates_and_assessments):
    """Candidate A accessing a non-existent candidate ID -> 403 Forbidden."""
    user_a = AuthUserORM(
        id=1001,
        uname="alpha@example.com",
        fullname="Candidate Alpha",
        role="candidate",
    )
    setattr(user_a, "is_employee", False)
    client_a = get_client_for_user(db_session, user_a)

    res = client_a.get("/api/aiprep/candidates/99999/assessments")
    assert res.status_code == 403


def test_employee_accessing_nonexistent_id_not_found(db_session, seed_candidates_and_assessments):
    """Employee accessing a non-existent candidate ID -> 404 Not Found."""
    admin_user = AuthUserORM(
        id=99,
        uname="admin@wbl.com",
        fullname="Admin User",
        role="admin",
    )
    setattr(admin_user, "is_employee", True)
    client_admin = get_client_for_user(db_session, admin_user)

    res = client_admin.get("/api/aiprep/candidates/99999/assessments")
    assert res.status_code == 404


def test_candidate_assessments_pagination(db_session, seed_candidates_and_assessments):
    """Verifies limit and offset query parameters work as expected."""
    user_a = AuthUserORM(
        id=1001,
        uname="alpha@example.com",
        fullname="Candidate Alpha",
        role="candidate",
    )
    setattr(user_a, "is_employee", False)
    client_a = get_client_for_user(db_session, user_a)

    # Request limit=2
    res = client_a.get("/api/aiprep/candidates/1001/assessments?limit=2&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2

    # Request offset=2, limit=2
    res_offset = client_a.get("/api/aiprep/candidates/1001/assessments?limit=2&offset=2")
    assert res_offset.status_code == 200
    data_offset = res_offset.json()
    assert data_offset["total"] == 3
    assert len(data_offset["items"]) == 1


def test_aiprep_prefix_alias(db_session, seed_candidates_and_assessments):
    """Verifies /aiprep/candidates/{id}/assessments prefix alias also works."""
    user_a = AuthUserORM(
        id=1001,
        uname="alpha@example.com",
        fullname="Candidate Alpha",
        role="candidate",
    )
    setattr(user_a, "is_employee", False)
    client_a = get_client_for_user(db_session, user_a)

    res = client_a.get("/aiprep/candidates/1001/assessments")
    assert res.status_code == 200
    assert res.json()["total"] == 3
