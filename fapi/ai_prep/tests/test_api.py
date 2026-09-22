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
            sub_category="RAG Systems",
            difficulty_level="HARD",
            question_text="Explain hybrid search indexing in RAG pipelines.",
            is_active=True,
        )
        db_session.add(q1)

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


def test_candidate_creation_returns_clean_questions(db_session, seed_candidate):
    """Verifies candidate assessment returns expected question fields."""
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
        assert "question_text" in q
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

    # 4. Get specific question by ID
    get_res = client.get(f"/api/aiprep/questions/{q_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == q_id

    # 5. Delete/deactivate question
    del_res = client.delete(f"/api/aiprep/employee/questions/{q_id}")
    assert del_res.status_code == 200
    assert del_res.json()["id"] == q_id


def test_singular_candidate_route_aliases(db_session, seed_candidate):
    """Verifies singular candidate URL alias support (/employee/candidate/{id}/...)."""
    client = get_employee_client(db_session, 50)
    res_resume = client.get("/api/aiprep/employee/candidate/1001/resume-status")
    assert res_resume.status_code == 200
    assert res_resume.json()["has_resume"] is True

    res_llm = client.get("/api/aiprep/employee/candidate/1001/llm-keys")
    assert res_llm.status_code == 200
    assert res_llm.json()["is_configured"] is True


def test_assessment_data_endpoints(db_session, seed_candidate):
    """Verifies direct GET endpoints for ai_prep_assessment_data."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    # 1. Candidate creates assessment and submits data
    create_res = cand_client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    assert create_res.status_code == 201
    aid = create_res.json()["id"]

    submit_res = cand_client.post(f"/api/aiprep/candidate/assessments/{aid}/data", json={
        "questions": [{"id": 1, "text": "Question 1"}],
        "transcript": {"text": "My answer"},
        "audio_telemetry": {"wpm": 120},
        "video_telemetry": {"face_detected": True},
    })
    assert submit_res.status_code == 200

    # 2. Candidate fetches data directly
    cand_data_res = cand_client.get(f"/api/aiprep/candidate/assessments/{aid}/data")
    assert cand_data_res.status_code == 200
    assert cand_data_res.json()["assessment_id"] == aid
    assert cand_data_res.json()["audio_telemetry"]["wpm"] == 120

    # 3. Employee fetches data directly
    emp_data_res = emp_client.get(f"/api/aiprep/employee/assessments/{aid}/data")
    assert emp_data_res.status_code == 200
    assert emp_data_res.json()["assessment_id"] == aid


def test_media_pipeline_complete_flow(db_session, seed_candidate):
    """Verifies media upload chunk, chunk status, assemble, raw upload, and storage info."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    # 1. Create assessment
    create_res = cand_client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "INTRO",
        "media_type": "VIDEO",
    })
    assert create_res.status_code == 201
    aid = create_res.json()["id"]

    # 2. Upload chunk 1
    chunk_file = ("chunk_0001.webm", b"RIFF....webm_dummy_chunk_content", "video/webm")
    upload_res = cand_client.post(
        "/api/aiprep/media/upload-chunk",
        data={"assessment_id": aid, "chunk_number": 1, "total_chunks": 2},
        files={"file": chunk_file},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == "uploaded"

    # 3. Check chunk status
    status_res = cand_client.get(f"/api/aiprep/media/chunk-status?assessment_id={aid}&total_chunks=2")
    assert status_res.status_code == 200
    assert status_res.json()["uploaded_chunks_count"] >= 1

    # 4. Assemble chunks
    assemble_res = cand_client.post(f"/api/aiprep/media/assemble?assessment_id={aid}")
    assert assemble_res.status_code == 200
    assert assemble_res.json()["status"] == "ASSEMBLING"

    # 5. Raw direct media upload
    raw_file = ("raw_sample.webm", b"raw_single_file_content", "video/webm")
    raw_res = cand_client.post(
        "/api/aiprep/media/upload",
        data={"assessment_id": aid, "media_type": "VIDEO"},
        files={"file": raw_file},
    )
    assert raw_res.status_code == 200
    assert raw_res.json()["success"] is True

    # 6. Storage info
    storage_res = emp_client.get("/api/aiprep/employee/media/storage-info")
    assert storage_res.status_code == 200
    assert "total_bytes" in storage_res.json()


def test_assessment_status_and_streaming(db_session, seed_candidate):
    """Verifies processing status snapshot and SSE event streaming endpoints."""
    cand_client = get_candidate_client(db_session, 1001)

    # 1. Check status snapshot for assessment 1
    snap_res = cand_client.get("/api/aiprep/assessments/1/status")
    assert snap_res.status_code == 200
    assert "progress_percentage" in snap_res.json()
    assert snap_res.json()["status"] == "COMPLETED"

    # 2. SSE streaming
    stream_res = cand_client.get("/api/aiprep/assessments/1/stream")
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")


def test_put_evaluate_and_report_endpoint(db_session, seed_candidate):
    """Verifies PUT evaluate and dedicated GET report endpoints."""
    cand_client = get_candidate_client(db_session, 1001)
    emp_client = get_employee_client(db_session, 50)

    create_res = cand_client.post("/api/aiprep/candidate/assessments", json={
        "candidate_id": 1001,
        "assessment_type": "TECHNICAL",
        "media_type": "VIDEO",
    })
    aid = create_res.json()["id"]

    # PUT evaluate with telemetry
    put_eval_res = cand_client.put(f"/api/aiprep/candidate/assessments/{aid}/evaluate", json={
        "transcript": {"full_text": "System architecture design"},
        "audio_telemetry": {"words_per_minute": 130},
        "video_telemetry": {"face_visible_pct": 95},
    })
    assert put_eval_res.status_code == 202
    assert put_eval_res.json()["status"] == "EVALUATING"

    # Save mock report into DB to test report getter
    rep = AiPrepAssessmentReportORM(
        assessment_id=aid,
        audio_evaluation={"score": 88},
        video_evaluation={"score": 92},
        transcript_evaluation={"score": 85, "overall_score": 88.3},
    )
    db_session.add(rep)
    db_session.commit()

    # Candidate GET report
    cand_rep_res = cand_client.get(f"/api/aiprep/candidate/assessments/{aid}/report")
    assert cand_rep_res.status_code == 200
    assert cand_rep_res.json()["assessment_id"] == aid
    assert cand_rep_res.json()["audio_evaluation"]["score"] == 88

    # Employee GET report
    emp_rep_res = emp_client.get(f"/api/aiprep/employee/assessments/{aid}/report")
    assert emp_rep_res.status_code == 200
    assert emp_rep_res.json()["assessment_id"] == aid


def test_admin_create_custom_assessment_type(db_session):
    """Verifies POST /api/aiprep/employee/assessment-types."""
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
    assert res.status_code == 201
    assert res.json()["code"] == "EXECUTIVE_LEADERSHIP"
    assert res.json()["title"] == "Executive Leadership Round"


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
        "/api/aiprep/candidate/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"}
    )
    assert res_create.status_code == 201
    data = res_create.json()
    aid = data["id"]
    auuid = data["assessment_uuid"]
    assert auuid is not None
    assert len(auuid) > 10

    # 2. Candidate GET assessment details by UUID
    res_detail = cand_client.get(f"/api/aiprep/candidate/assessments/{auuid}")
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == aid
    assert res_detail.json()["assessment_uuid"] == auuid

    # 3. Candidate alias GET /assessments/{auuid}
    res_alias = cand_client.get(f"/api/aiprep/assessments/{auuid}")
    assert res_alias.status_code == 200
    assert res_alias.json()["id"] == aid

    # 4. Candidate POST data by UUID
    data_payload = {
        "questions": [{"id": 1, "question": "Tell me about yourself"}],
        "transcript": {"full_text": "Hello world from candidate"},
        "audio_telemetry": {"wpm": 140},
        "video_telemetry": {"face_visible_pct": 98.5},
    }
    res_data_post = cand_client.post(f"/api/aiprep/candidate/assessments/{auuid}/data", json=data_payload)
    assert res_data_post.status_code == 200

    # 5. Candidate GET data by UUID
    res_data_get = cand_client.get(f"/api/aiprep/candidate/assessments/{auuid}/data")
    assert res_data_get.status_code == 200
    assert res_data_get.json()["assessment_id"] == aid
    assert res_data_get.json()["assessment_uuid"] == auuid
    assert res_data_get.json()["transcript"]["full_text"] == "Hello world from candidate"

    # 6. Candidate PATCH media by UUID
    media_payload = {"youtube_url": "https://media.example.com/uuid_stream"}
    res_media = cand_client.patch(f"/api/aiprep/candidate/assessments/{auuid}/media", json=media_payload)
    assert res_media.status_code == 200
    assert res_media.json()["id"] == aid
    assert res_media.json()["assessment_uuid"] == auuid
    assert res_media.json()["youtube_url"] == "https://media.example.com/uuid_stream"

    # 7. Candidate POST evaluate by UUID
    res_eval_post = cand_client.post(f"/api/aiprep/candidate/assessments/{auuid}/evaluate")
    assert res_eval_post.status_code == 202
    assert res_eval_post.json()["id"] == aid
    assert res_eval_post.json()["status"] == "EVALUATING"

    # 8. Candidate PUT evaluate by UUID
    res_eval_put = cand_client.put(
        f"/api/aiprep/candidate/assessments/{auuid}/evaluate",
        json={"transcript": {"full_text": "Updated transcript"}}
    )
    assert res_eval_put.status_code == 202
    assert res_eval_put.json()["id"] == aid

    # 9. Save mock report with UUID string for report GET check
    rep_obj = crud.save_assessment_report(db_session, auuid, {
        "audio_evaluation": {"score": 90},
        "video_evaluation": {"score": 95},
        "transcript_evaluation": {"score": 92},
        "overall_score": 92.3,
    })
    assert rep_obj.assessment_id == aid

    # 10. Candidate GET report by UUID
    res_rep = cand_client.get(f"/api/aiprep/candidate/assessments/{auuid}/report")
    assert res_rep.status_code == 200
    assert res_rep.json()["assessment_id"] == aid
    assert res_rep.json()["assessment_uuid"] == auuid
    assert res_rep.json()["overall_score"] == 92.3

    # 11. Employee GET assessment detail by UUID
    res_emp_det = emp_client.get(f"/api/aiprep/employee/assessments/{auuid}")
    assert res_emp_det.status_code == 200
    assert res_emp_det.json()["id"] == aid
    assert res_emp_det.json()["assessment_uuid"] == auuid

    # 12. Employee GET assessment data by UUID
    res_emp_dat = emp_client.get(f"/api/aiprep/employee/assessments/{auuid}/data")
    assert res_emp_dat.status_code == 200
    assert res_emp_dat.json()["assessment_id"] == aid
    assert res_emp_dat.json()["assessment_uuid"] == auuid

    # 13. Employee GET assessment report by UUID
    res_emp_rep = emp_client.get(f"/api/aiprep/employee/assessments/{auuid}/report")
    assert res_emp_rep.status_code == 200
    assert res_emp_rep.json()["assessment_id"] == aid
    assert res_emp_rep.json()["assessment_uuid"] == auuid

    # 14. Progress status snapshot by UUID
    res_status = cand_client.get(f"/api/aiprep/assessments/{auuid}/status")
    assert res_status.status_code == 200
    assert res_status.json()["assessment_id"] == aid

    # 15. Non-existent UUID returns 404
    res_404 = cand_client.get("/api/aiprep/candidate/assessments/non-existent-uuid-99999")
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == "Assessment not found"

    # 16. CRUD operations with non-existent UUID raise clean ValueError instead of DB casting error
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
        sub_category=None,
        difficulty_level="EASY",
        question_text="Tell me about yourself and your DB-backed AI background.",
        is_active=True,
    )
    q_jd = AiPrepQuestionORM(
        category="JD_INTRO",
        sub_category=None,
        difficulty_level="EASY",
        question_text="How do your skills match this specific JD?",
        is_active=True,
    )
    db_session.add_all([q_intro, q_jd])
    db_session.commit()

    # 2. Test INTRO assessment creation (DB-backed, 1 question, persisted)
    res_intro = client.post(
        "/api/aiprep/candidate/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
    )
    assert res_intro.status_code == 201
    intro_data = res_intro.json()
    assert len(intro_data["questions"]) == 1
    assert intro_data["questions"][0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    # Verify persisted in ai_prep_assessment_data table
    data_rec = db_session.query(AiPrepAssessmentDataORM).filter(
        AiPrepAssessmentDataORM.assessment_id == intro_data["id"]
    ).first()
    assert data_rec is not None
    assert data_rec.questions[0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    # Verify GET detail returns persisted question via numeric ID & UUID string
    res_intro_det = client.get(f"/api/aiprep/candidate/assessments/{intro_data['id']}")
    assert res_intro_det.status_code == 200
    assert res_intro_det.json()["questions"][0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    res_intro_uuid = client.get(f"/api/aiprep/candidate/assessments/{intro_data['assessment_uuid']}")
    assert res_intro_uuid.status_code == 200
    assert res_intro_uuid.json()["questions"][0]["question_text"] == "Tell me about yourself and your DB-backed AI background."

    # 3. Test JD_INTRO assessment creation (DB-backed, 1 question)
    res_jd = client.post(
        "/api/aiprep/candidate/assessments",
        json={"candidate_id": 1001, "assessment_type": "JD_INTRO", "media_type": "VIDEO"},
    )
    assert res_jd.status_code == 201
    jd_data = res_jd.json()
    assert len(jd_data["questions"]) == 1
    assert jd_data["questions"][0]["question_text"] == "How do your skills match this specific JD?"

    # 4. DB retrieval exception → HTTP 422 with user-facing error message.
    with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment", side_effect=RuntimeError("DB Connection error")):
        res_fail = client.post(
            "/api/aiprep/candidate/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
        assert res_fail.status_code == 422
        assert "could not be loaded" in res_fail.json()["detail"].lower()

    # 5. Empty DB result (no active questions) → HTTP 422 with user-facing error message.
    with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.get_questions_for_assessment", return_value=[]):
        res_empty = client.post(
            "/api/aiprep/candidate/assessments",
            json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "VIDEO"},
        )
        assert res_empty.status_code == 422
        assert "could not be loaded" in res_empty.json()["detail"].lower()


def test_persistence_failure_raises_error(db_session, seed_candidate):
    """Verifies that if save_assessment_data fails, creation raises 500 error instead of silently returning 201."""
    client = get_candidate_client(db_session, 1001)
    with patch("fapi.ai_prep.crud.save_assessment_data", side_effect=RuntimeError("DB Write Error")):
        res = client.post(
            "/api/aiprep/candidate/assessments",
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
            "/api/aiprep/candidate/assessments",
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
            "/api/aiprep/candidate/assessments",
            json={"candidate_id": 1001, "assessment_type": "TECHNICAL", "media_type": "VIDEO"},
        )
    assert res.status_code == 422
    assert "could not be loaded" in res.json()["detail"].lower()


def test_audio_upload_and_streaming_endpoints(db_session, seed_candidate, tmp_path, monkeypatch):
    """Verifies direct audio upload and storage streaming for video and audio."""
    import io
    from fapi.ai_prep.config import settings
    monkeypatch.setenv("AIPREP_LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", str(tmp_path))

    client = get_candidate_client(db_session, 1001)

    # 1. Seed active question
    q_intro = AiPrepQuestionORM(
        category="INTRO",
        sub_category=None,
        difficulty_level="EASY",
        question_text="Tell me about yourself for audio assessment.",
        is_active=True,
    )
    db_session.add(q_intro)
    db_session.commit()

    # 2. Create an assessment
    create_res = client.post(
        "/api/aiprep/candidate/assessments",
        json={"candidate_id": 1001, "assessment_type": "INTRO", "media_type": "AUDIO"},
    )
    assert create_res.status_code == 201
    aid = create_res.json()["id"]

    # 2. Write mock audio file before upload cleanup to test storage streaming
    audio_dir = tmp_path / "1001" / str(aid)
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file = audio_dir / "audio.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 500)

    # Stream audio from server storage
    stream_res = client.get(f"/api/aiprep/assessments/{aid}/audio")
    assert stream_res.status_code == 200
    assert len(stream_res.content) == 504

    # 3. Write mock video file and test video streaming with HTTP 206 range
    video_file = audio_dir / "assembled.webm"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 1000)

    # Full video stream
    v_res = client.get(f"/api/aiprep/assessments/{aid}/video")
    assert v_res.status_code == 200
    assert len(v_res.content) == 1004

    # Range video stream (bytes=0-99)
    range_res = client.get(
        f"/api/aiprep/assessments/{aid}/video",
        headers={"Range": "bytes=0-99"},
    )
    assert range_res.status_code == 206
    assert len(range_res.content) == 100
    assert "bytes 0-99/1004" in range_res.headers.get("Content-Range", "")

    # 4. Upload direct audio recording
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 500)
    upload_res = client.post(
        f"/api/aiprep/assessments/{aid}/audio",
        files={"file": ("recording.wav", fake_audio, "audio/wav")},
        data={"mime_type": "audio/wav"},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["success"] is True
    assert upload_res.json()["assessment_id"] == aid


