"""Dynamic API Endpoints and Schemas Test Suite for AI Prep Tool."""
import os
import secrets

os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["ALGORITHM"] = "HS256"
os.environ["DB_PASSWORD"] = secrets.token_urlsafe(16)
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "wbl_test"
os.environ["ENV"] = "test"
os.environ["UPSTASH_REDIS_REST_URL"] = "https://mock-redis.upstash.io"
os.environ["UPSTASH_REDIS_REST_TOKEN"] = secrets.token_urlsafe(32)

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.utils.permission_gate import get_optional_current_user
from fapi.db.models import Base, AuthUserORM, CandidateORM, CandidateMarketingORM, CandidateLlmApiKeyORM
from fapi.ai_prep import crud
from fapi.ai_prep.core.llm_evaluation.engine import EvalEngine
from fapi.ai_prep.core.scores_engine import ScoresEngine
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)

# In-memory SQLite for isolated test execution
sqlite_test_db_url = "sqlite:///:memory:"
engine = create_engine(
    sqlite_test_db_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

import fapi.db.database
fapi.db.database.SessionLocal = TestingSessionLocal
fapi.db.database.engine = engine



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
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        app.dependency_overrides.clear()




@pytest.fixture
def seed_candidate(db_session):
    cand1 = db_session.query(CandidateORM).filter(CandidateORM.id == 1001).first()
    if not cand1:
        cand1 = CandidateORM(id=1001, email="candidate1001@whitebox.com", full_name="John Doe")
        db_session.add(cand1)

    cand2 = db_session.query(CandidateORM).filter(CandidateORM.id == 1002).first()
    if not cand2:
        cand2 = CandidateORM(id=1002, email="candidate1002@whitebox.com", full_name="Bob Smith")
        db_session.add(cand2)

    llm1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == 1001).first()
    if not llm1:
        test_api_key = secrets.token_urlsafe(16)
        llm1 = CandidateLlmApiKeyORM(
            candidate_id=1001,
            provider_name="openai",
            api_key=test_api_key,
            model_name="gpt-4o",
            voice_enabled=True,
            is_default=True,
            status="active",
        )
        db_session.add(llm1)

    mktg1 = db_session.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == 1001).first()
    if not mktg1:
        mktg1 = CandidateMarketingORM(
            candidate_id=1001,
            start_date=datetime.date(2026, 1, 1),
            resume_url="https://test-storage.example.com/resumes/test_candidate_resume.pdf",
            candidate_json={"skills": ["Python", "FastAPI", "PyTorch"], "current_title": "AI Engineer"},
        )
        db_session.add(mktg1)

    # Seed a question in DB
    q1 = db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == 101).first()
    if not q1:
        q1 = AiPrepQuestionORM(
            id=101,
            category="TECHNICAL",
            subject="AI Engineering",
            concept="RAG & Retrieval",
            scope="BROAD",
            difficulty_level="HARD",
            time_limit_seconds=120,
            question_text="Explain hybrid search indexing in RAG pipelines.",
            is_active=True,
        )
        db_session.add(q1)

    q_intro = db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == 102).first()
    if not q_intro:
        q_intro = AiPrepQuestionORM(
            id=102,
            category="INTRO",
            difficulty_level="EASY",
            time_limit_seconds=120,
            question_text="Tell me about yourself and your background.",
            is_active=True,
        )
        db_session.add(q_intro)

    # Seed an assessment in DB
    a1 = db_session.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == 1001).first()
    if not a1:
        a1 = AiPrepAssessmentORM(
            id=1,
            assessment_uuid="00000000-0000-0000-0000-000000001001",
            candidate_id=1001,
            assessment_type="TECHNICAL",
            status="COMPLETED",
        )
        db_session.add(a1)

    db_session.commit()
    return cand1


def get_candidate_client(db_session, candidate_id: int = 1001):
    mock_user = AuthUserORM(
        id=candidate_id,
        uname=f"candidate{candidate_id}@whitebox.com",
        fullname=f"Candidate {candidate_id}",
        role="candidate",
    )
    setattr(mock_user, "is_employee", False)
    setattr(mock_user, "is_admin", False)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    # Match the app-level permission gate's optional-user resolution to the test user.
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user
    return TestClient(app)


def get_employee_client(db_session, employee_id: int = 50):
    mock_staff = AuthUserORM(
        id=employee_id,
        uname="staff@whitebox.com",
        fullname="Admin Staff",
        role="admin",
    )
    setattr(mock_staff, "is_employee", True)
    setattr(mock_staff, "is_admin", True)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_staff
    # The app-level enforce_access dependency uses get_optional_current_user,
    # which calls get_current_user directly. Override it too so test requests
    # are authenticated consistently without requiring a real JWT.
    app.dependency_overrides[get_optional_current_user] = lambda: mock_staff
    app.dependency_overrides[staff_or_admin_required] = lambda: mock_staff
    return TestClient(app)


# ===========================================================================
# 1. CANDIDATE ENDPOINTS TESTS
# ===========================================================================

def test_candidate_llm_keys_self_check(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    # Decommissioned endpoint returns 404
    assert client.get("/api/aiprep/candidate/llm-keys").status_code == 404
    # Readiness precheck validates LLM key configuration
    res = client.get("/api/aiprep/candidates/1001/assessment-readiness-precheck")
    assert res.status_code == 200
    assert res.json()["llm_check"]["is_configured"] is True


def test_candidate_resume_status_self_check(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    # Decommissioned endpoint returns 404
    assert client.get("/api/aiprep/candidate/resume-status").status_code == 404
    # Readiness precheck validates resume presence
    res = client.get("/api/aiprep/candidates/1001/assessment-readiness-precheck")
    assert res.status_code == 200
    assert res.json()["resume_check"]["has_resume"] is True


def test_candidate_assessment_readiness_precheck(db_session, seed_candidate):
    # 1. Candidate 1001 has active LLM key and resume in My Resume -> allowed to proceed
    client = get_candidate_client(db_session, 1001)
    res = client.get("/api/aiprep/candidates/1001/assessment-readiness-precheck")
    assert res.status_code == 200
    data = res.json()
    assert data["eligible"] is True
    assert data["allowed_to_proceed"] is True
    assert data["action_required"] is None
    assert data["candidate_id"] == 1001
    assert data["llm_check"]["is_configured"] is True
    assert data["resume_check"]["has_resume"] is True
    assert "ready" in data["message"].lower()

    # 2. Candidate 1002 has neither LLM key nor resume -> blocked with action_required="both"
    client2 = get_candidate_client(db_session, 1002)
    res2 = client2.get("/api/aiprep/candidates/1002/assessment-readiness-precheck")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["eligible"] is False
    assert data2["allowed_to_proceed"] is False
    assert data2["action_required"] == "both"
    assert data2["candidate_id"] == 1002
    assert data2["llm_check"]["is_configured"] is False
    assert data2["resume_check"]["has_resume"] is False

    # 3. Cross-candidate access forbidden for candidates
    client1 = get_candidate_client(db_session, 1001)
    forbidden_res = client1.get("/api/aiprep/candidates/1002/assessment-readiness-precheck")
    assert forbidden_res.status_code == 403

    # 4. Employee can inspect precheck for any candidate
    emp_client = get_employee_client(db_session, 50)
    emp_res = emp_client.get("/api/aiprep/candidates/1001/assessment-readiness-precheck")
    assert emp_res.status_code == 200
    assert emp_res.json()["eligible"] is True

    # 5. Non-existent candidate returns 404
    not_found_res = emp_client.get("/api/aiprep/candidates/99999/assessment-readiness-precheck")
    assert not_found_res.status_code == 404

    # 6. Verify old precheck endpoints are removed (return 404)
    old_res1 = client.get("/api/aiprep/candidate/pre-check")
    assert old_res1.status_code == 404
    old_res2 = client.get("/api/aiprep/pre-check")
    assert old_res2.status_code == 404
    old_res3 = emp_client.get("/api/aiprep/candidates/1001/pre-check")
    assert old_res3.status_code == 404
    old_res4 = emp_client.get("/api/aiprep/employee/candidates/1001/pre-check")
    assert old_res4.status_code == 404


def test_candidate_create_assessment_flow(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    payload = {
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
        "job_description": "Senior GenAI Engineer",
        "consent": {"recording_consent": True, "ai_evaluation_consent": True},
    }
    res = client.post("/api/aiprep/candidates/1001/assessments", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "success"
    data = body["data"]
    assessment_id = data["assessment_id"]
    assert data["status"] == "IN_PROGRESS"
    assert data["assessment_type"] == "TECHNICAL"

    # 1. Verify old sub-endpoints return 404
    assert client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/data", json={}).status_code == 404
    assert client.patch(f"/api/aiprep/candidate/assessments/{assessment_id}/media", json={}).status_code == 404
    assert client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/evaluate").status_code == 404

    # 2. Get Details via canonical endpoint
    detail_res = client.get(f"/api/aiprep/candidates/1001/assessments/{assessment_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["candidate_id"] == 1001
    assert detail["consent"] == {"recording_consent": True, "ai_evaluation_consent": True}
    assert "started_at" in detail


def test_candidate_isolation_cannot_access_other_candidate(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    res = client.post("/api/aiprep/candidates/1002/assessments", json={
        "candidate_id": 1002,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert res.status_code == 403

    # Decommissioned endpoints return 404
    assert client.post("/api/aiprep/candidate/assessments", json={}).status_code == 404
    assert client.post("/api/aiprep/assessments", json={}).status_code == 404


def test_candidate_creation_returns_clean_questions(db_session, seed_candidate):
    """Verifies candidate assessment returns expected question fields."""
    client = get_candidate_client(db_session, 1001)
    res = client.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "success"
    questions = body["data"].get("questions", [])
    assert len(questions) > 0
    for q in questions:
        assert "question_text" in q
        assert "ideal_answer_rubric" not in q


def test_cross_candidate_media_authorization(db_session, seed_candidate):
    """Verifies that Candidate 1002 cannot view or manipulate Candidate 1001's assessment media."""
    # 1. Candidate 1001 creates assessment
    client_1001 = get_candidate_client(db_session, 1001)
    res = client_1001.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert res.status_code == 201
    assessment_id = res.json()["data"]["assessment_id"]

    # Switch session context to Candidate 1002
    client_1002 = get_candidate_client(db_session, 1002)

    # 2. Candidate 1002 attempts to get Candidate 1001's assessment details -> 403
    res_detail = client_1002.get(f"/api/aiprep/candidates/1001/assessments/{assessment_id}")
    assert res_detail.status_code == 403

    # 3. Candidate 1002 attempts to upload chunks to Candidate 1001's assessment -> 403
    res_chunk = client_1002.post(
        f"/api/aiprep/candidates/1001/assessments/{assessment_id}/media/chunk",
        data={"chunk_index": 0, "is_final": False},
        files={"media_file": ("chunk.webm", b"dummy", "video/webm")},
    )
    assert res_chunk.status_code == 403

    # 4. Candidate 1002 attempts to submit assessment -> 403
    res_submit = client_1002.put(
        f"/api/aiprep/candidates/1001/assessments/{assessment_id}",
        json={"is_final": True},
    )
    assert res_submit.status_code == 403

    # 5. Verify deleted legacy unnamespaced routes return 404
    assert client_1002.get(f"/api/aiprep/media/chunk-status?assessment_id={assessment_id}").status_code == 404
    assert client_1002.post(f"/api/aiprep/media/assemble?assessment_id={assessment_id}").status_code == 404
    assert client_1002.get(f"/api/aiprep/assessments/{assessment_id}/status").status_code == 404
    assert client_1002.patch(f"/api/aiprep/candidate/assessments/{assessment_id}/media").status_code == 404


# ===========================================================================
# 2. EMPLOYEE & ADMIN ENDPOINTS TESTS
# ===========================================================================

def test_employee_check_candidate_llm_and_resume(db_session, seed_candidate):
    client = get_employee_client(db_session, 50)

    # Legacy employee check endpoints are deleted -> 404
    assert client.get("/api/aiprep/employee/candidates/1001/llm-keys").status_code == 404
    assert client.get("/api/aiprep/employee/candidates/1001/resume-status").status_code == 404

    # Staff checks candidate readiness through canonical endpoint
    res_precheck = client.get("/api/aiprep/candidates/1001/assessment-readiness-precheck")
    assert res_precheck.status_code == 200
    data = res_precheck.json()
    assert data["llm_check"]["is_configured"] is True
    assert data["resume_check"]["has_resume"] is True


def test_employee_assessments_table(db_session, seed_candidate):
    client = get_employee_client(db_session, 50)
    res = client.get("/api/aiprep/employee/assessments?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1


# ===========================================================================
# 3. CATALOG & QUESTION BANK TESTS
# ===========================================================================

def test_assessment_types_catalog(db_session):
    client = get_candidate_client(db_session, 1001)
    # Decommissioned endpoint returns 404
    res = client.get("/api/aiprep/assessment-types")
    assert res.status_code == 404


def test_question_bank_management(db_session):
    client = get_employee_client(db_session, 50)

    # Decommissioned employee alias returns 404
    assert client.post("/api/aiprep/employee/questions", json={}).status_code == 404

    # 1. Add question via canonical route
    new_q = {
        "category": "TECHNICAL",
        "subject": "AI Engineering",
        "concept": "Agentic AI & Multi-Agent Systems",
        "scope": "SPECIFIC",
        "difficulty_level": "HARD",
        "question_text": "How do you coordinate hierarchical multi-agent workflows?",
        "is_active": True,
    }
    post_res = client.post("/api/aiprep/questions", json=new_q)
    assert post_res.status_code == 201
    assert post_res.json()["question_text"] == new_q["question_text"]
    q_id = post_res.json()["id"]

    # 2. Update question via canonical route
    patch_res = client.patch(f"/api/aiprep/questions/{q_id}", json={"difficulty_level": "MEDIUM"})
    assert patch_res.status_code == 200
    assert patch_res.json()["difficulty_level"] == "MEDIUM"

    # 3. Add a non-TECHNICAL question and preserve optional taxonomy fields.
    non_tech_q = {
        "category": "HIRING_MANAGER",
        "subject": "AI Engineering",
        "concept": "Generative AI & LLMs",
        "scope": "BROAD",
        "difficulty_level": "EASY",
        "question_text": "How did you collaborate with ML engineers?",
        "is_active": True,
    }
    intro_res = client.post("/api/aiprep/questions", json=non_tech_q)
    assert intro_res.status_code == 201
    intro_data = intro_res.json()
    assert intro_data["subject"] == non_tech_q["subject"]
    assert intro_data["concept"] == non_tech_q["concept"]
    assert intro_data["scope"] == non_tech_q["scope"]

    # 4. Editing taxonomy fields on a non-TECHNICAL question persists to the DB.
    patch_taxonomy = {
        "subject": "Software Engineering",
        "concept": "API Design & Microservices",
        "scope": "SPECIFIC",
    }
    patch_taxonomy_res = client.patch(
        f"/api/aiprep/questions/{intro_data['id']}", json=patch_taxonomy
    )
    assert patch_taxonomy_res.status_code == 200
    assert patch_taxonomy_res.json()["subject"] == patch_taxonomy["subject"]
    assert patch_taxonomy_res.json()["concept"] == patch_taxonomy["concept"]
    assert patch_taxonomy_res.json()["scope"] == patch_taxonomy["scope"]

    # 5. Reject invalid Enum values with 422 Unprocessable Entity
    invalid_q = {
        "category": "TECHNICAL",
        "subject": "Invalid Subject Area",
        "concept": "Not A Real Concept",
        "question_text": "Invalid enum test",
    }
    invalid_res = client.post("/api/aiprep/questions", json=invalid_q)
    assert invalid_res.status_code == 422

    # 6. Reject a TECHNICAL question missing required subject
    missing_subj_q = {
        "category": "TECHNICAL",
        "question_text": "Missing subject test",
    }
    missing_subj_res = client.post("/api/aiprep/questions", json=missing_subj_q)
    assert missing_subj_res.status_code == 422

    # 7. Get specific question by ID
    get_res = client.get(f"/api/aiprep/questions/{q_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == q_id

    # 8. Delete/deactivate question
    del_res = client.delete(f"/api/aiprep/questions/{q_id}")
    assert del_res.status_code == 200
    assert del_res.json()["id"] == q_id


def test_singular_candidate_route_aliases(db_session, seed_candidate):
    """Verifies that removed singular candidate URL aliases return 404."""
    client = get_employee_client(db_session, 50)
    assert client.get("/api/aiprep/employee/candidate/1001/resume-status").status_code == 404
    assert client.get("/api/aiprep/employee/candidate/1001/llm-keys").status_code == 404
    assert client.get("/api/aiprep/employee/candidate/1001/assessments").status_code == 404


def test_assessment_data_endpoints(db_session, seed_candidate):
    """Verifies direct /data endpoints are removed and data is retrieved via canonical assessment endpoint."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    # 1. Candidate creates assessment
    create_res = cand_client.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert create_res.status_code == 201
    aid = create_res.json()["data"]["assessment_id"]

    # 2. Legacy /data endpoints return 404
    assert cand_client.post(f"/api/aiprep/candidate/assessments/{aid}/data").status_code == 404
    assert cand_client.get(f"/api/aiprep/candidate/assessments/{aid}/data").status_code == 404
    assert emp_client.get(f"/api/aiprep/employee/assessments/{aid}/data").status_code == 404

    # 3. Canonical endpoint returns assessment details with questions
    cand_data_res = cand_client.get(f"/api/aiprep/candidates/1001/assessments/{aid}")
    assert cand_data_res.status_code == 200
    assert cand_data_res.json()["id"] == aid


def test_media_pipeline_complete_flow(db_session, seed_candidate):
    """Verifies sequential media chunk upload and that legacy upload/assemble endpoints return 404."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    # 1. Create assessment
    create_res = cand_client.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert create_res.status_code == 201
    aid = create_res.json()["data"]["assessment_id"]

    # 2. Upload chunk 0 via canonical route
    chunk_file = ("chunk_0.webm", b"RIFF....webm_dummy_chunk_content", "video/webm")
    upload_res = cand_client.post(
        f"/api/aiprep/candidates/1001/assessments/{aid}/media/chunk",
        data={"chunk_index": 0, "is_final": False},
        files={"media_file": chunk_file},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == "success"

    # 3. Verify removed legacy media routes return 404
    assert cand_client.get(f"/api/aiprep/media/chunk-status?assessment_id={aid}&total_chunks=2").status_code == 404
    assert cand_client.post(f"/api/aiprep/media/assemble?assessment_id={aid}").status_code == 404
    assert cand_client.post("/api/aiprep/media/upload").status_code == 404
    assert emp_client.get("/api/aiprep/employee/media/storage-info").status_code == 404


def test_assessment_status_and_streaming(db_session, seed_candidate):
    """Verifies that separate status snapshot and unauthenticated SSE endpoints return 404."""
    cand_client = get_candidate_client(db_session, 1001)

    # Decommissioned endpoints return 404
    assert cand_client.get("/api/aiprep/assessments/1/status").status_code == 404
    assert cand_client.get("/api/aiprep/assessments/1/stream").status_code == 404


def test_put_evaluate_and_report_endpoint(db_session, seed_candidate):
    """Verifies report retrieval via canonical GET and that legacy /evaluate and /report endpoints return 404."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    create_res = cand_client.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    aid = create_res.json()["data"]["assessment_id"]

    # Verify deleted evaluate endpoint returns 404
    assert cand_client.put(f"/api/aiprep/candidate/assessments/{aid}/evaluate").status_code == 404
    assert cand_client.get(f"/api/aiprep/candidate/assessments/{aid}/report").status_code == 404
    assert emp_client.get(f"/api/aiprep/employee/assessments/{aid}/report").status_code == 404

    # Save mock report into DB to test canonical detail getter
    rep = AiPrepAssessmentReportORM(
        assessment_id=aid,
        audio_evaluation={"score": 88},
        video_evaluation={"score": 92},
        transcript_evaluation={"score": 85, "overall_score": 88.3},
    )
    db_session.add(rep)
    db_session.commit()

    # Canonical GET endpoint returns details and report
    cand_res = cand_client.get(f"/api/aiprep/candidates/1001/assessments/{aid}")
    assert cand_res.status_code == 200
    assert cand_res.json()["id"] == aid


def test_admin_create_custom_assessment_type(db_session):
    """Verifies POST /api/aiprep/employee/assessment-types returns 404 after decommissioning."""
    emp_client = get_employee_client(db_session, 50)
    new_type_payload = {
        "code": "EXECUTIVE_LEADERSHIP",
        "title": "Executive Leadership Round",
        "description": "C-suite alignment, strategy, and organizational leadership.",
        "category": "MANAGEMENT",
        "time_estimate_mins": 45,
        "is_active": True,
    }
    res = emp_client.post("/api/aiprep/employee/assessment-types", json=new_type_payload)
    assert res.status_code == 404


def test_save_assessment_report_nested_overall_score(db_session):
    """Verifies that save_assessment_report extracts overall_score from nested scores_breakdown_json."""
    ass = AiPrepAssessmentORM(
        candidate_id=10,
        assessment_type="TECHNICAL",
        media_type="VIDEO",
        status="EVALUATING",
    )
    db_session.add(ass)
    db_session.commit()

    # Report with nested scores_breakdown_json (per contract)
    eval_result = {
        "transcript_evaluation": {
            "scores_breakdown_json": {
                "ai_engineering": {"score": 90, "band": "STRONG"},
                "core_engineering": {"score": 85, "band": "STRONG"},
                "non_technical": {"score": 80, "band": "STRONG"},
                "business_acumen": {"score": 75, "band": "DEVELOPING"},
                "overall_score": 82.5,
                "overall_band": "STRONG",
            }
        },
        "audio_evaluation": {"score": 88},
        "video_evaluation": {"score": 92},
    }

    report = crud.save_assessment_report(db_session, ass.id, eval_result)
    assert report.overall_score == 82.5
    assert report.transcript_evaluation.get("overall_score") == 82.5

    # Reload from DB and verify property still returns overall_score
    reloaded = crud.get_assessment_report_by_assessment_id(db_session, ass.id)
    assert reloaded is not None
    assert reloaded.overall_score == 82.5


def test_build_insufficient_audio_evaluation_dynamic_duration():
    """Verifies that build_insufficient_audio_evaluation handles both 0s and positive durations properly."""
    engine = EvalEngine()
    validator = ScoresEngine()

    # 1. Zero-second speech
    zero_eval = engine.build_insufficient_audio_evaluation(0.0)
    errs = []
    validator._validate_audio_payload(zero_eval["audio_evaluation"], errs)
    assert not errs, f"Validation errors on 0s eval: {errs}"
    assert "0 seconds" in zero_eval["audio_evaluation"]["summary"]["confidence_rationale"]
    assert "0 seconds" in zero_eval["audio_evaluation"]["factors"]["pace"]["reliability_note"]

    # 2. Positive speaking duration (e.g. 45.0s)
    forty_five_eval = engine.build_insufficient_audio_evaluation(45.0)
    errs_45 = []
    validator._validate_audio_payload(forty_five_eval["audio_evaluation"], errs_45)
    assert not errs_45, f"Validation errors on 45s eval: {errs_45}"
    assert "45 seconds" in forty_five_eval["audio_evaluation"]["summary"]["confidence_rationale"]
    assert "45 seconds" in forty_five_eval["audio_evaluation"]["factors"]["pace"]["reliability_note"]
    assert "0 seconds" not in forty_five_eval["audio_evaluation"]["summary"]["confidence_rationale"]
    assert forty_five_eval["audio_evaluation"]["recording_environment_context"]["speaking_duration_seconds"] == 45.0


def test_uuid_compatibility_across_all_endpoints(db_session, seed_candidate):
    """Verifies complete UUID compatibility across candidate, employee, media, and status endpoints."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    # 1. Create assessment
    res_create = cand_client.post(
        "/api/aiprep/candidates/1001/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"}
    )
    assert res_create.status_code == 201
    data = res_create.json()["data"]
    aid = data["assessment_id"]
    auuid = data["assessment_uuid"]
    assert auuid is not None
    assert len(auuid) > 10

    # 2. Candidate GET assessment details by UUID via canonical endpoint
    res_detail = cand_client.get(f"/api/aiprep/candidates/1001/assessments/{auuid}")
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == aid
    assert res_detail.json()["assessment_uuid"] == auuid

    # 3. Candidate upload chunk by UUID via canonical endpoint
    chunk_file = ("chunk_0.webm", b"RIFF....dummy_chunk_content", "video/webm")
    res_chunk = cand_client.post(
        f"/api/aiprep/candidates/1001/assessments/{auuid}/media/chunk",
        data={"chunk_index": 0, "is_final": False},
        files={"media_file": chunk_file},
    )
    assert res_chunk.status_code == 200
    assert res_chunk.json()["status"] == "success"

    # 4. Verify removed legacy endpoints return 404
    assert cand_client.get(f"/api/aiprep/candidate/assessments/{auuid}").status_code == 404
    assert cand_client.get(f"/api/aiprep/assessments/{auuid}").status_code == 404
    assert cand_client.post(f"/api/aiprep/candidate/assessments/{auuid}/data").status_code == 404
    assert cand_client.patch(f"/api/aiprep/candidate/assessments/{auuid}/media").status_code == 404
    assert cand_client.post(f"/api/aiprep/candidate/assessments/{auuid}/evaluate").status_code == 404
    assert cand_client.get(f"/api/aiprep/candidate/assessments/{auuid}/report").status_code == 404
    assert cand_client.get(f"/api/aiprep/assessments/{auuid}/status").status_code == 404

    # 5. Non-existent UUID returns 404
    res_404 = cand_client.get("/api/aiprep/candidates/1001/assessments/non-existent-uuid-99999")
    assert res_404.status_code == 404

    # 6. CRUD operations with non-existent UUID raise clean ValueError instead of DB casting error
    with pytest.raises(ValueError, match="not found"):
        crud.save_assessment_data(
            db=db_session,
            assessment_id="non-existent-uuid-99999",
            questions=[],
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )

    with pytest.raises(ValueError, match="not found"):
        crud.save_assessment_report(
            db=db_session,
            assessment_id="non-existent-uuid-99999",
            parsed_report={},
        )


def test_question_loading_persistence_and_fallback_flow(db_session, seed_candidate):
    """Regression test verifying DB question loading, persistence, fallback trigger, and single-question capping."""
    client = get_candidate_client(db_session, 1001)

    # 1. Seed active questions in DB for INTRO and JD_INTRO
    q_intro = AiPrepQuestionORM(
        category="INTRO",
        difficulty_level="EASY",
        question_text="Tell me about yourself and your DB-backed AI background.",
        is_active=True,
    )
    q_jd = AiPrepQuestionORM(
        category="JD_INTRO",
        difficulty_level="EASY",
        question_text="How do your skills match this specific JD?",
        is_active=True,
    )
    db_session.add_all([q_intro, q_jd])
    db_session.commit()

    # 2. Test INTRO assessment creation (DB-backed, 1 question, persisted)
    res_intro = client.post(
        "/api/aiprep/candidates/1001/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
    )
    assert res_intro.status_code == 201
    intro_body = res_intro.json()
    assert intro_body["status"] == "success"
    intro_data = intro_body["data"]
    assert len(intro_data["questions"]) == 1
    assert intro_data["questions"][0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    # Verify persisted in ai_prep_assessment_data table
    data_rec = db_session.query(AiPrepAssessmentDataORM).filter(
        AiPrepAssessmentDataORM.assessment_id == intro_data["assessment_id"]
    ).first()
    assert data_rec is not None
    assert data_rec.questions[0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    # Verify GET detail returns 200 via canonical numeric ID & UUID string
    res_intro_det = client.get(f"/api/aiprep/candidates/1001/assessments/{intro_data['assessment_id']}")
    assert res_intro_det.status_code == 200
    assert res_intro_det.json()["id"] == intro_data["assessment_id"]

    res_intro_uuid = client.get(f"/api/aiprep/candidates/1001/assessments/{intro_data['assessment_uuid']}")
    assert res_intro_uuid.status_code == 200
    assert res_intro_uuid.json()["id"] == intro_data["assessment_id"]
    assert res_intro_uuid.json()["assessment_uuid"] == intro_data["assessment_uuid"]

    # 3. Test JD_INTRO assessment creation (DB-backed, 1 question)
    res_jd = client.post(
        "/api/aiprep/candidates/1001/assessments",
        json={"candidate_id": 1001, "assessment_type": "JD_INTRO", "media_type": "VIDEO"},
    )
    assert res_jd.status_code == 201
    jd_data = res_jd.json()["data"]
    assert len(jd_data["questions"]) == 1
    assert jd_data["questions"][0]["question_text"] == "How do your skills match this specific JD?"

    # 4. DB retrieval exception → HTTP 422 with user-facing error message.
    with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment", side_effect=RuntimeError("DB Connection error")):
        res_fail = client.post(
            "/api/aiprep/candidates/1001/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
        assert res_fail.status_code == 422
        assert "could not be loaded" in res_fail.json()["detail"].lower()

    # 5. Empty DB result (no active questions) → HTTP 422 with user-facing error message.
    with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment", return_value=[]):
        res_empty = client.post(
            "/api/aiprep/candidates/1001/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
        assert res_empty.status_code == 422
        assert "could not be loaded" in res_empty.json()["detail"].lower()


def test_persistence_failure_raises_error(db_session, seed_candidate):
    """Verifies that if save_assessment_data fails, creation raises 500 error instead of silently returning 201."""
    client = get_candidate_client(db_session, 1001)
    with patch("fapi.ai_prep.crud.save_assessment_data", side_effect=RuntimeError("DB Write Error")):
        res = client.post(
            "/api/aiprep/candidates/1001/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
        assert res.status_code == 500
        assert "Failed to persist assessment questions" in res.json()["detail"]


def test_question_load_exception_returns_user_error(db_session, seed_candidate):
    """DB exception during question retrieval returns HTTP 422 with a user-facing error message."""
    client = get_candidate_client(db_session, 1001)
    with patch(
        "fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment",
        side_effect=RuntimeError("Simulated DB failure"),
    ):
        res = client.post(
            "/api/aiprep/candidates/1001/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
    assert res.status_code == 422
    assert "could not be loaded" in res.json()["detail"].lower()


def test_empty_question_bank_returns_user_error(db_session, seed_candidate):
    """Empty question bank result returns HTTP 422 with a user-facing error message."""
    client = get_candidate_client(db_session, 1001)
    with patch(
        "fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment",
        return_value=[],
    ):
        res = client.post(
            "/api/aiprep/candidates/1001/assessments",
            json={"candidate_id": 1001, "assessment_type": "TECHNICAL", "media_type": "VIDEO"},
        )
    assert res.status_code == 422
    assert "could not be loaded" in res.json()["detail"].lower()


def test_audio_upload_and_streaming_endpoints(db_session, seed_candidate, tmp_path, monkeypatch):
    """Verifies that deprecated audio/video direct streaming endpoints return 404."""
    client = get_candidate_client(db_session, 1001)

    # 1. Seed active question
    q_intro = AiPrepQuestionORM(
        category="INTRO",
        difficulty_level="EASY",
        question_text="Tell me about yourself for audio assessment.",
        is_active=True,
    )
    db_session.add(q_intro)
    db_session.commit()

    # 2. Create an assessment
    create_res = client.post(
        "/api/aiprep/candidates/1001/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "AUDIO"},
    )
    assert create_res.status_code == 201
    aid = create_res.json()["data"]["assessment_id"]

    # 3. Decommissioned direct streaming and upload endpoints return 404
    assert client.get(f"/api/aiprep/assessments/{aid}/audio").status_code == 404
    assert client.get(f"/api/aiprep/assessments/{aid}/video").status_code == 404
    assert client.post(f"/api/aiprep/assessments/{aid}/audio").status_code == 404


def test_create_candidate_assessment_exact_specification(db_session):
    """Verifies POST /api/aiprep/candidates/{id}/assessments per user specification."""
    # Seed candidate 1042
    candidate_1042 = CandidateORM(
        id=1042,
        email="candidate1042@whitebox.com",
        full_name="Test Candidate 1042",
        status="active",
    )
    db_session.add(candidate_1042)
    db_session.commit()

    # Seed LLM setup & resume prerequisites for 1042
    llm_key = CandidateLlmApiKeyORM(
        candidate_id=1042,
        provider_name="openai",
        api_key="mock_key1042", #pragma: allowlist secret
        model_name="gpt-4o",
        status="active",
        is_default=True,
    )
    mktg = CandidateMarketingORM(
        candidate_id=1042,
        start_date=datetime.date(2026, 1, 1),
        resume_url="https://storage.whitebox.com/resumes/1042.pdf",
        candidate_json={"skills": ["Python", "FastAPI"], "title": "Software Engineer"},
    )
    # Seed INTRO question
    q_intro = AiPrepQuestionORM(
        category="INTRO",
        difficulty_level="EASY",
        question_text="Please introduce yourself and walk us through your background and experience.",
        is_active=True,
    )
    db_session.add_all([llm_key, mktg, q_intro])
    db_session.commit()

    client = get_candidate_client(db_session, 1042)

    # Request Body
    request_body = {
        "candidate_id": 1042,
        "assessment_type": "INTRO",
        "media_type": "AUDIO",
    }

    res = client.post("/api/aiprep/candidates/1042/assessments", json=request_body)
    assert res.status_code == 201

    body = res.json()
    assert body["status"] == "success"
    data = body["data"]

    assert "assessment_id" in data
    assert isinstance(data["assessment_id"], int)
    assert "assessment_uuid" in data
    assert data["candidate_id"] == 1042
    assert data["assessment_type"] == "INTRO"
    assert data["media_type"] == "AUDIO"
    assert data["status"] == "IN_PROGRESS"
    assert "started_at" in data
    assert "questions" in data
    assert len(data["questions"]) == 1
    assert data["questions"][0]["category"] == "INTRO"
    assert data["questions"][0]["question_text"] == "Please introduce yourself and walk us through your background and experience."
    assert data["questions"][0]["difficulty_level"] == "EASY"


def test_candidate_assessment_chunk_upload_exact_spec(db_session, seed_candidate):
    """
    Verifies POST /api/aiprep/candidates/{id}/assessments/{id}/media/chunk:
    - Multipart form: assessment_uuid, chunk_index, is_final, media_file
    - Response schema: status=success, data with assessment_uuid, chunk_index, bytes_received, saved=True
    - Verification that legacy /media/upload-chunk route is removed.
    """
    client = get_candidate_client(db_session, 1001)

    # Ensure active INTRO question exists in DB
    q_intro = db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.category == "INTRO").first()
    if not q_intro:
        q_intro = AiPrepQuestionORM(
            category="INTRO",
            difficulty_level="EASY",
            question_text="Please introduce yourself and walk us through your background and experience.",
            is_active=True,
        )
        db_session.add(q_intro)
        db_session.commit()

    # 1. Create Assessment
    create_res = client.post("/api/aiprep/candidates/1001/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert create_res.status_code == 201
    assessment_data = create_res.json()["data"]
    aid = assessment_data["assessment_id"]
    auuid = assessment_data["assessment_uuid"]

    # 2. Upload chunk 0 via integer assessment_id
    binary_chunk_data = b"\x1a\x45\xdf\xa3" + (b"\x00" * 2097148)  # Exactly 2097152 bytes (2MB)
    upload_res = client.post(
        f"/api/aiprep/candidates/1001/assessments/{aid}/media/chunk",
        data={
            "assessment_uuid": auuid,
            "chunk_index": 0,
            "is_final": "false",
        },
        files={
            "media_file": ("chunk_0.webm", binary_chunk_data, "video/webm"),
        },
    )
    assert upload_res.status_code == 200
    res_json = upload_res.json()
    assert res_json["status"] == "success"
    assert res_json["data"] == {
        "assessment_uuid": auuid,
        "chunk_index": 0,
        "bytes_received": 2097152,
        "saved": True,
    }

    # 3. Upload chunk 1 via UUID in path
    chunk_1_data = b"\x1a\x45\xdf\xa3" + (b"\x01" * 1020)
    upload_uuid_res = client.post(
        f"/api/aiprep/candidates/1001/assessments/{auuid}/media/chunk",
        data={
            "assessment_uuid": auuid,
            "chunk_index": 1,
            "is_final": "true",
        },
        files={
            "media_file": ("chunk_1.webm", chunk_1_data, "video/webm"),
        },
    )
    assert upload_uuid_res.status_code == 200
    res_uuid_json = upload_uuid_res.json()
    assert res_uuid_json["status"] == "success"
    assert res_uuid_json["data"]["assessment_uuid"] == auuid
    assert res_uuid_json["data"]["chunk_index"] == 1
    assert res_uuid_json["data"]["bytes_received"] == len(chunk_1_data)
    assert res_uuid_json["data"]["saved"] is True

    # 4. Verify old route /media/upload-chunk is removed (404/405)
    old_res = client.post(
        "/api/aiprep/media/upload-chunk",
        data={"assessment_id": aid, "chunk_number": 1},
        files={"file": ("chunk_0001.webm", b"dummy", "video/webm")},
    )
    assert old_res.status_code in (404, 405)



