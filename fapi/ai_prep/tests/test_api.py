"""Comprehensive Test Suite for AI Prep Tool - Candidate vs Employee AuthN/AuthZ and Execution."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db
from fapi.db.models import Base, AuthUserORM, CandidateORM, CandidateMarketingORM, CandidateLlmApiKeyORM
from fapi.ai_prep.models import (
    AiPrepAssessmentTypeORM,
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.utils.auth_dependencies import get_current_user

# Isolated SQLite in-memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_data(db_session):
    # Candidate 1 (User 1001)
    cand1 = db_session.query(CandidateORM).filter(CandidateORM.id == 1001).first()
    if not cand1:
        cand1 = CandidateORM(id=1001, email="candidate1@test.com", fname="Candidate", lname="One")
        db_session.add(cand1)

    llm1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == 1001).first()
    if not llm1:
        llm1 = CandidateLlmApiKeyORM(
            candidate_id=1001,
            provider_name="openai",
            api_key="sk-test-mock-key-1001",
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
            start_date="2026-01-01",
            resume_url="https://s3.amazonaws.com/resumes/cand1.pdf",
            candidate_json={"skills": ["Python", "PyTorch"], "current_title": "AI Engineer"},
        )
        db_session.add(mktg1)

    # Candidate 2 (User 1002) - Unconfigured without LLM key
    cand2 = db_session.query(CandidateORM).filter(CandidateORM.id == 1002).first()
    if not cand2:
        cand2 = CandidateORM(id=1002, email="candidate2@test.com", fname="Candidate", lname="Two")
        db_session.add(cand2)

    db_session.commit()
    return {"cand1": cand1, "cand2": cand2}


def get_test_client_for_user(user_obj, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


# ===========================================================================
# 1. CANDIDATE ISOLATION & AUTHORIZATION TESTS
# ===========================================================================

def test_candidate_self_access_success(db_session, seed_data):
    candidate_user = AuthUserORM(id=1001, uname="candidate1@test.com", role="candidate")
    client = get_test_client_for_user(candidate_user, db_session)

    # Check LLM key (Self)
    res = client.get("/api/aiprep/candidate/llm-keys")
    assert res.status_code == 200
    assert res.json()["status"] == "valid"
    assert res.json()["is_configured"] is True

    # Check Resume (Self)
    res_resume = client.get("/api/aiprep/candidate/resume-status")
    assert res_resume.status_code == 200
    assert res_resume.json()["has_resume"] is True

    # Pre-check (Self)
    res_pre = client.get("/api/aiprep/candidate/pre-check")
    assert res_pre.status_code == 200
    assert res_pre.json()["eligible"] is True


def test_candidate_tamper_other_candidate_forbidden(db_session, seed_data):
    # Logged in as Candidate 1 (1001), trying to query Candidate 2 (1002)
    candidate_user = AuthUserORM(id=1001, uname="candidate1@test.com", role="candidate")
    client = get_test_client_for_user(candidate_user, db_session)

    # Candidate 1 cannot check Candidate 2's LLM keys
    res = client.get("/api/aiprep/candidates/1002/llm-keys")
    assert res.status_code == 403

    # Candidate 1 cannot check Candidate 2's resume
    res_resume = client.get("/api/aiprep/candidates/1002/resume-status")
    assert res_resume.status_code == 403

    # Candidate 1 cannot start assessment for Candidate 2
    res_create = client.post("/api/aiprep/assessments", json={
        "candidate_id": 1002,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert res_create.status_code == 403


# ===========================================================================
# 2. CANDIDATE ASSESSMENT EXECUTION FLOW
# ===========================================================================

def test_candidate_full_assessment_flow(db_session, seed_data):
    candidate_user = AuthUserORM(id=1001, uname="candidate1@test.com", role="candidate")
    client = get_test_client_for_user(candidate_user, db_session)

    # Step 1: Create Assessment
    create_res = client.post("/api/aiprep/candidate/assessments", json={
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
        "job_description": "LLM Engineer",
    })
    assert create_res.status_code == 201
    assessment_data = create_res.json()
    assessment_id = assessment_data["id"]
    assert assessment_data["status"] == "IN_PROGRESS"

    # Step 2: Submit Telemetry
    submit_res = client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/data", json={
        "questions": [{"question_id": 1, "question_text": "Explain RAG systems"}],
        "transcript": {"full_text": "RAG enhances LLM responses with retrieved documents.", "segments": []},
        "audio_telemetry": {"words_per_minute": 138, "silence_ratio_pct": 11.5},
        "video_telemetry": {"face_visible_pct": 97.0, "head_nods_count": 10},
    })
    assert submit_res.status_code == 200

    # Step 3: Update Media URL
    media_res = client.patch(f"/api/aiprep/candidate/assessments/{assessment_id}/media", json={
        "youtube_url": "https://youtube.com/watch?v=cand1_video",
    })
    assert media_res.status_code == 200
    assert media_res.json()["youtube_url"] == "https://youtube.com/watch?v=cand1_video"

    # Step 4: Get Processing Status
    status_res = client.get(f"/api/aiprep/assessments/{assessment_id}/status")
    assert status_res.status_code == 200

    # Step 5: Trigger Evaluation
    eval_res = client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/evaluate")
    assert eval_res.status_code == 202
    assert eval_res.json()["status"] == "EVALUATING"


# ===========================================================================
# 3. EMPLOYEE & ADMIN WORKFLOW TESTS
# ===========================================================================

def test_employee_can_inspect_any_candidate(db_session, seed_data):
    employee_user = AuthUserORM(id=50, uname="staff@whitebox.com", role="admin", is_admin=True, is_employee=True)
    client = get_test_client_for_user(employee_user, db_session)

    # Employee checks candidate 1 LLM keys
    res1 = client.get("/api/aiprep/employee/candidates/1001/llm-keys")
    assert res1.status_code == 200
    assert res1.json()["is_configured"] is True

    # Employee checks candidate 2 LLM keys (which is unconfigured)
    res2 = client.get("/api/aiprep/employee/candidates/1002/llm-keys")
    assert res2.status_code == 200
    assert res2.json()["is_configured"] is False

    # Employee checks candidate 1 resume
    res_mktg = client.get("/api/aiprep/employee/candidates/1001/resume-status")
    assert res_mktg.status_code == 200
    assert res_mktg.json()["has_resume"] is True

    # Employee queries comprehensive assessments table
    table_res = client.get("/api/aiprep/employee/assessments?limit=10")
    assert table_res.status_code == 200
    assert "items" in table_res.json()


def test_admin_assessment_types_and_question_bank(db_session):
    admin_user = AuthUserORM(id=1, uname="admin", role="admin", is_admin=True, is_employee=True)
    client = get_test_client_for_user(admin_user, db_session)

    # List catalog
    cat_res = client.get("/api/aiprep/assessment-types")
    assert cat_res.status_code == 200
    assert cat_res.json()["total"] >= 6

    # Create question in question bank
    q_res = client.post("/api/aiprep/employee/questions", json={
        "category": "TECHNICAL",
        "sub_category": "Agentic Frameworks",
        "difficulty_level": "HARD",
        "question_text": "Describe the architecture of autonomous multi-agent systems.",
        "ideal_answer_rubric": "Detail message buses, tool execution guards, and memory systems.",
        "is_active": True,
    })
    assert q_res.status_code == 201
    q_id = q_res.json()["id"]

    # Update question
    patch_res = client.patch(f"/api/aiprep/employee/questions/{q_id}", json={
        "difficulty_level": "EXPERT",
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["difficulty_level"] == "EXPERT"


# ===========================================================================
# 4. MEDIA INGESTION & CHUNK UPLOADER TESTS
# ===========================================================================

def test_media_chunk_upload_and_status(db_session, seed_data):
    candidate_user = AuthUserORM(id=1001, uname="candidate1@test.com", role="candidate")
    client = get_test_client_for_user(candidate_user, db_session)

    # Create assessment session first
    create_res = client.post("/api/aiprep/candidate/assessments", json={
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assessment_id = create_res.json()["id"]

    # Upload chunk 1
    chunk_bytes = b"RIFFfake_webm_binary_data_chunk_001"
    upload_res = client.post(
        "/api/aiprep/media/upload-chunk",
        data={"assessment_id": assessment_id, "chunk_number": 1, "total_chunks": 2},
        files={"file": ("chunk_0001.webm", chunk_bytes, "video/webm")},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["success"] is True
    assert upload_res.json()["chunk_number"] == 1

    # Query chunk status
    status_res = client.get(f"/api/aiprep/media/chunk-status?assessment_id={assessment_id}&total_chunks=2")
    assert status_res.status_code == 200
    data = status_res.json()
    assert 1 in data["uploaded_chunks"]
    assert 2 in data["missing_chunks"]
    assert data["is_complete"] is False
