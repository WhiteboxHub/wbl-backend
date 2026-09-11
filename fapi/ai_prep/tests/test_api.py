"""Dynamic API Endpoints and Schemas Test Suite for AI Prep Tool."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.db.models import Base, AuthUserORM, CandidateORM, CandidateMarketingORM, CandidateLlmApiKeyORM
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


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


import datetime

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
        llm1 = CandidateLlmApiKeyORM(
            candidate_id=1001,
            provider_name="openai",
            api_key="mock_test_key_1001",
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
            resume_url="https://s3.amazonaws.com/resumes/john_doe.pdf",
            candidate_json={"skills": ["Python", "FastAPI", "PyTorch"], "current_title": "AI Engineer"},
        )
        db_session.add(mktg1)

    # Seed a question in DB
    q1 = db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == 101).first()
    if not q1:
        q1 = AiPrepQuestionORM(
            id=101,
            category="TECHNICAL",
            sub_category="RAG Systems",
            difficulty_level="HARD",
            question_text="Explain hybrid search indexing in RAG pipelines.",
            ideal_answer_rubric="Detail sparse and dense vector representations.",
            is_active=True,
        )
        db_session.add(q1)

    # Seed an assessment in DB
    a1 = db_session.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == 1001).first()
    if not a1:
        a1 = AiPrepAssessmentORM(
            id=1,
            assessment_uuid="test-session-1001",
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
    app.dependency_overrides[staff_or_admin_required] = lambda: mock_staff
    return TestClient(app)


# ===========================================================================
# 1. CANDIDATE ENDPOINTS TESTS
# ===========================================================================

def test_candidate_llm_keys_self_check(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    res = client.get("/api/aiprep/candidate/llm-keys")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "valid"
    assert data["is_configured"] is True
    assert data["provider"] == "openai"


def test_candidate_resume_status_self_check(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    res = client.get("/api/aiprep/candidate/resume-status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "valid"
    assert data["has_resume"] is True
    assert "skills" in data


def test_candidate_pre_check(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    res = client.get("/api/aiprep/candidate/pre-check")
    assert res.status_code == 200
    data = res.json()
    assert data["eligible"] is True
    assert data["candidate_id"] == 1001
    assert data["llm_check"]["is_configured"] is True


def test_candidate_create_assessment_flow(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    payload = {
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
        "job_description": "Senior GenAI Engineer",
    }
    res = client.post("/api/aiprep/candidate/assessments", json=payload)
    assert res.status_code == 201
    data = res.json()
    assessment_id = data["id"]
    assert data["status"] == "IN_PROGRESS"
    assert data["assessment_type"] == "TECHNICAL"

    # 1. Submit telemetry
    telemetry_payload = {
        "questions": [{"question_id": 101, "question_text": "Explain RAG"}],
        "transcript": {"full_text": "Retrieval Augmented Generation."},
        "audio_telemetry": {"words_per_minute": 135, "silence_ratio_pct": 12.0},
        "video_telemetry": {"face_visible_pct": 98.0, "head_nods_count": 8},
    }
    submit_res = client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/data", json=telemetry_payload)
    assert submit_res.status_code == 200
    assert submit_res.json()["message"] == "Data saved successfully"

    # 2. Update media URL
    patch_res = client.patch(f"/api/aiprep/candidate/assessments/{assessment_id}/media", json={
        "youtube_url": "https://youtube.com/watch?v=cand_video_101"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["youtube_url"] == "https://youtube.com/watch?v=cand_video_101"

    # 3. Get Details
    detail_res = client.get(f"/api/aiprep/candidate/assessments/{assessment_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["candidate_id"] == 1001
    assert detail["youtube_url"] == "https://youtube.com/watch?v=cand_video_101"
    assert detail["job_description"] == "Senior GenAI Engineer"
    assert "ip_address" in detail
    assert "user_agent" in detail
    assert "started_at" in detail
    assert "completed_at" in detail


    # 4. Trigger Evaluation
    eval_res = client.post(f"/api/aiprep/candidate/assessments/{assessment_id}/evaluate")
    assert eval_res.status_code == 202
    assert eval_res.json()["status"] == "EVALUATING"


def test_candidate_isolation_cannot_access_other_candidate(db_session, seed_candidate):
    client = get_candidate_client(db_session, 1001)
    res = client.post("/api/aiprep/assessments", json={
        "candidate_id": 1002,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert res.status_code == 403


def test_candidate_creation_does_not_leak_rubric(db_session, seed_candidate):
    """Verifies that ideal_answer_rubric is not leaked in candidate assessment questions."""
    client = get_candidate_client(db_session, 1001)
    res = client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert res.status_code == 201
    questions = res.json().get("questions", [])
    assert len(questions) > 0
    for q in questions:
        assert "ideal_answer_rubric" not in q


def test_cross_candidate_media_authorization(db_session, seed_candidate):
    """Verifies that Candidate 1002 cannot view or manipulate Candidate 1001's assessment media."""
    # 1. Candidate 1001 creates assessment
    client_1001 = get_candidate_client(db_session, 1001)
    res = client_1001.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert res.status_code == 201
    assessment_id = res.json()["id"]

    # Switch session context to Candidate 1002
    client_1002 = get_candidate_client(db_session, 1002)

    # 2. Candidate 1002 attempts to get assessment details -> 403
    res_detail = client_1002.get(f"/api/aiprep/candidate/assessments/{assessment_id}")
    assert res_detail.status_code == 403

    # 3. Candidate 1002 attempts to query chunk upload status -> 403
    res_chunk_status = client_1002.get(f"/api/aiprep/media/chunk-status?assessment_id={assessment_id}")
    assert res_chunk_status.status_code == 403

    # 4. Candidate 1002 attempts to assemble media -> 403
    res_assemble = client_1002.post(f"/api/aiprep/media/assemble?assessment_id={assessment_id}")
    assert res_assemble.status_code == 403

    # 5. Candidate 1002 attempts to get processing status -> 403
    res_status = client_1002.get(f"/api/aiprep/assessments/{assessment_id}/status")
    assert res_status.status_code == 403

    # 6. Candidate 1002 attempts to update media URL -> 403
    res_media = client_1002.patch(f"/api/aiprep/candidate/assessments/{assessment_id}/media", json={
        "youtube_url": "https://malicious.com/overwrite"
    })
    assert res_media.status_code == 403


# ===========================================================================
# 2. EMPLOYEE & ADMIN ENDPOINTS TESTS
# ===========================================================================

def test_employee_check_candidate_llm_and_resume(db_session, seed_candidate):
    client = get_employee_client(db_session, 50)

    # Check Candidate 1001 LLM
    res_llm = client.get("/api/aiprep/employee/candidates/1001/llm-keys")
    assert res_llm.status_code == 200
    assert res_llm.json()["is_configured"] is True

    # Check Candidate 1001 Resume
    res_resume = client.get("/api/aiprep/employee/candidates/1001/resume-status")
    assert res_resume.status_code == 200
    assert res_resume.json()["has_resume"] is True


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
    res = client.get("/api/aiprep/assessment-types")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 6
    codes = [item["code"] for item in data["items"]]
    assert "INTRO" in codes
    assert "SYSTEM_DESIGN" in codes
    assert "TECHNICAL" in codes


def test_question_bank_management(db_session):
    client = get_employee_client(db_session, 50)

    # 1. Add question
    new_q = {
        "category": "TECHNICAL",
        "sub_category": "Multi-Agent Systems",
        "difficulty_level": "HARD",
        "question_text": "How do you coordinate hierarchical multi-agent workflows?",
        "ideal_answer_rubric": "Detail supervisory agents, delegation, and state aggregation.",
        "is_active": True,
    }
    post_res = client.post("/api/aiprep/employee/questions", json=new_q)
    assert post_res.status_code == 201
    assert post_res.json()["question_text"] == new_q["question_text"]
    q_id = post_res.json()["id"]

    # 2. Update question
    patch_res = client.patch(f"/api/aiprep/employee/questions/{q_id}", json={"difficulty_level": "EXPERT"})
    assert patch_res.status_code == 200
    assert patch_res.json()["difficulty_level"] == "EXPERT"

    # 3. Add non-TECHNICAL question (verifies DDL constraint chk_qb_subcategory: sub_category is nullified)
    non_tech_q = {
        "category": "INTRO",
        "sub_category": "Should be None",
        "difficulty_level": "EASY",
        "question_text": "Tell me about your background and core achievements.",
        "is_active": True,
    }
    intro_res = client.post("/api/aiprep/employee/questions", json=non_tech_q)
    assert intro_res.status_code == 201
    assert intro_res.json()["sub_category"] is None

