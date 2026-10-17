"""
Technical Assessment Test Suite
Covers the complete Technical Assessment lifecycle:
1. Unit tests: 900s time budget & quota, QA context formatting, rating validator
2. POST /candidates/{id}/assessments (Start Session & Question Selection)
3. PUT /candidates/{id}/assessments/{id} (Submission & LLM Evaluation)
4. GET /candidates/{id}/assessments/{id} (Report Delivery & Technical Evaluation Serializer)
5. End-to-End full lifecycle (POST -> PUT -> GET chained)
"""
import os
import json
import secrets
from datetime import date
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
from fapi.utils.permission_gate import get_optional_current_user
from fapi.db.models import (
    Base,
    AuthUserORM,
    CandidateORM,
    CandidateMarketingORM,
    CandidateLlmApiKeyORM,
)
from fapi.ai_prep import crud
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.ai_prep.core.assessment_engine import AssessmentEngine
from fapi.ai_prep.core.scores_engine import ScoresEngine

# =============================================================================
# SECTION 1: Database Setup & Fixtures
# In-memory SQLite with required tables, test candidate, and question bank seed
# =============================================================================

try:
    from fapi.ai_prep.tests.test_candidate_submit_assessment import test_engine, TestingSessionLocal
except ImportError:
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

import fapi.ai_prep.orchestrator.assessment_orchestrator
fapi.ai_prep.orchestrator.assessment_orchestrator.SessionLocal = TestingSessionLocal
import fapi.ai_prep.utils.aiprep_utils
fapi.ai_prep.utils.aiprep_utils.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_tech_test_db():
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
def test_candidate(db_session):
    cand = db_session.query(CandidateORM).filter(CandidateORM.id == 701).first()
    if not cand:
        cand = CandidateORM(id=701, full_name="Tech Candidate", email="tech.cand@test.com")
        db_session.add(cand)
        db_session.flush()

    llm_key = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == 701).first()
    if not llm_key:
        llm_key = CandidateLlmApiKeyORM(
            candidate_id=701,
            provider_name="openai",
            api_key=secrets.token_urlsafe(16),
            model_name="gpt-4o",
            is_default=True,
            voice_enabled=True,
        )
        db_session.add(llm_key)

    mkt = db_session.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == 701).first()
    if not mkt:
        mkt = CandidateMarketingORM(
            candidate_id=701,
            start_date=date.today(),
            resume_url="https://whitebox-resumes.s3.amazonaws.com/tech_resume.pdf",
            candidate_json={"skills": ["Python", "Docker", "FastAPI", "RAG"]},
        )
        db_session.add(mkt)

    db_session.commit()
    return cand


@pytest.fixture
def seed_questions(db_session):
    """Seeds active questions using exact ConceptEnum and SubjectEnum values."""
    if db_session.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.category == "TECHNICAL").count() >= 9:
        return

    sample_questions = [
        # AI Engineering
        {"id": 7001, "category": "TECHNICAL", "subject": "AI Engineering", "concept": "RAG & Retrieval", "difficulty_level": "EASY", "scope": "SPECIFIC", "time_limit_seconds": 60, "question_text": "What is Retrieval-Augmented Generation?", "ground_truth": {"criteria": [{"point": "Combines retrieval with LLM", "required": True}], "technical_keywords": ["retrieval", "vector", "context"], "critical_failures": ["Claims RAG replaces fine-tuning completely"]}},
        {"id": 7002, "category": "TECHNICAL", "subject": "AI Engineering", "concept": "Generative AI & LLMs", "difficulty_level": "MEDIUM", "scope": "SPECIFIC", "time_limit_seconds": 90, "question_text": "How do vector embeddings work?", "ground_truth": {"criteria": [{"point": "Dense numerical vector", "required": True}], "technical_keywords": ["cosine", "dimension"], "critical_failures": []}},
        {"id": 7003, "category": "TECHNICAL", "subject": "AI Engineering", "concept": "Agentic AI & Multi-Agent Systems", "difficulty_level": "MEDIUM", "scope": "BROAD", "time_limit_seconds": 150, "question_text": "Design an autonomous tool-calling agent.", "ground_truth": {"criteria": [{"point": "Tool routing and reflection", "required": True}], "technical_keywords": ["orchestrator", "tool"], "critical_failures": []}},
        {"id": 7004, "category": "TECHNICAL", "subject": "AI Engineering", "concept": "Models & Context Engineering", "difficulty_level": "HARD", "scope": "BROAD", "time_limit_seconds": 210, "question_text": "Compare LoRA and full fine-tuning.", "ground_truth": {"criteria": [{"point": "Low-rank adapter matrices", "required": True}], "technical_keywords": ["LoRA", "rank"], "critical_failures": []}},
        # Software Engineering
        {"id": 7005, "category": "TECHNICAL", "subject": "Software Engineering", "concept": "API Design & Microservices", "difficulty_level": "EASY", "scope": "SPECIFIC", "time_limit_seconds": 60, "question_text": "Explain synchronous vs asynchronous APIs.", "ground_truth": {"criteria": [{"point": "Non-blocking I/O", "required": True}], "technical_keywords": ["async", "event loop"], "critical_failures": []}},
        {"id": 7006, "category": "TECHNICAL", "subject": "Software Engineering", "concept": "Databases & Caching", "difficulty_level": "MEDIUM", "scope": "SPECIFIC", "time_limit_seconds": 90, "question_text": "What are ACID properties in relational DBs?", "ground_truth": {"criteria": [{"point": "Atomicity, Consistency, Isolation, Durability", "required": True}], "technical_keywords": ["transaction", "isolation"], "critical_failures": []}},
        # DevOps and Cloud
        {"id": 7007, "category": "TECHNICAL", "subject": "DevOps and Cloud", "concept": "Containers & Orchestration", "difficulty_level": "EASY", "scope": "SPECIFIC", "time_limit_seconds": 60, "question_text": "What is the difference between an image and container?", "ground_truth": {"criteria": [{"point": "Image is blueprint, container is instance", "required": True}], "technical_keywords": ["runtime", "layer"], "critical_failures": []}},
        {"id": 7008, "category": "TECHNICAL", "subject": "DevOps and Cloud", "concept": "CI/CD & GitOps", "difficulty_level": "MEDIUM", "scope": "SPECIFIC", "time_limit_seconds": 90, "question_text": "Explain a standard CI/CD deployment pipeline.", "ground_truth": {"criteria": [{"point": "Automated build, test, and deploy stages", "required": True}], "technical_keywords": ["pipeline", "artifact"], "critical_failures": []}},
        {"id": 7009, "category": "TECHNICAL", "subject": "DevOps and Cloud", "concept": "Cloud Architecture & Services", "difficulty_level": "HARD", "scope": "SPECIFIC", "time_limit_seconds": 120, "question_text": "Explain cloud load balancing and health checks.", "ground_truth": {"criteria": [{"point": "Traffic distribution on healthy targets", "required": True}], "technical_keywords": ["balancer", "probe"], "critical_failures": []}},
    ]

    for q in sample_questions:
        db_session.add(AiPrepQuestionORM(
            id=q["id"],
            category=q["category"],
            subject=q["subject"],
            concept=q["concept"],
            difficulty_level=q["difficulty_level"],
            scope=q["scope"],
            time_limit_seconds=q["time_limit_seconds"],
            question_text=q["question_text"],
            ground_truth=q["ground_truth"],
            is_active=True,
        ))
    db_session.commit()


@pytest.fixture
def auth_client(test_candidate, db_session):
    user = AuthUserORM(
        id=701,
        uname="tech.cand@test.com",
        fullname="Tech Candidate",
        role="candidate",
    )
    setattr(user, "is_employee", False)
    setattr(user, "is_admin", False)

    def override_get_current_user():
        return user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_optional_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# Mock LLM evaluation response adhering strictly to technical_prompt.py schema
MOCK_TECHNICAL_LLM_EVALUATION = {
    "technical_evaluation": {
        "overall_assessment": {
            "rating": "GOOD",
            "summary": "Candidate demonstrated solid grasp of RAG workflows and database fundamentals with clear articulation.",
            "top_strengths": [
                "Strong conceptual understanding of vector embeddings and retrieval architectures",
                "Clear distinction between synchronous and asynchronous architectures"
            ],
            "priority_improvements": [
                "Need deeper familiarity with low-level LoRA parameter tuning",
                "Could expand on container security practices"
            ]
        },
        "difficulty_analysis": {
            "easy_questions_performance": "EXCELLENT",
            "medium_questions_performance": "GOOD",
            "hard_questions_performance": "AVERAGE",
            "observation": "Handles foundational concepts with ease; shows minor hesitation when scaling to hard architectural edge cases."
        },
        "subject_evaluations": [
            {
                "subject": "AI Engineering",
                "rating": "GOOD",
                "summary": "Solid core understanding of LLM application patterns.",
                "strengths": ["Vector retrieval", "Context management"],
                "gaps": ["Fine-tuning optimization"]
            },
            {
                "subject": "Software Engineering",
                "rating": "EXCELLENT",
                "summary": "Strong foundational engineering and systems clarity.",
                "strengths": ["Async paradigms", "ACID transactions"],
                "gaps": []
            },
            {
                "subject": "DevOps and Cloud",
                "rating": "GOOD",
                "summary": "Good practical knowledge of containers and deployment.",
                "strengths": ["Docker fundamentals"],
                "gaps": ["Advanced orchestration"]
            }
        ],
        "concept_evaluations": [
            {
                "concept": "RAG & Retrieval",
                "subject": "AI Engineering",
                "rating": "EXCELLENT",
                "observation": "Articulated complete end-to-end pipeline accurately.",
                "gaps": []
            },
            {
                "concept": "Containers & Orchestration",
                "subject": "DevOps and Cloud",
                "rating": "GOOD",
                "observation": "Clear differentiation between images and runtime containers.",
                "gaps": ["Did not mention image scanning"]
            }
        ],
        "question_evaluations": [
            {
                "question_id": 7001,
                "question_text": "What is Retrieval-Augmented Generation?",
                "rating": "EXCELLENT",
                "covered_points": ["Combines retrieval with LLM", "Uses vector database context"],
                "missed_points": [],
                "technical_keywords_used": ["retrieval", "vector", "context"],
                "missing_keywords": [],
                "evidence_quote": "RAG combines vector retrieval with LLM generation to ground the context.",
                "observation": "Thorough, accurate response without hesitation.",
                "study_guidance": None
            },
            {
                "question_id": 7007,
                "question_text": "What is the difference between an image and container?",
                "rating": "GOOD",
                "covered_points": ["Image is blueprint, container is instance"],
                "missed_points": [],
                "technical_keywords_used": ["runtime", "layer"],
                "missing_keywords": [],
                "evidence_quote": "An image is a static snapshot, while a container is a live running instance.",
                "observation": "Solid answer with clear analogies.",
                "study_guidance": None
            }
        ]
    }
}


# =============================================================================
# SECTION 2: Unit Tests — Question Selection, Context Builder, Validator
# =============================================================================

def test_select_technical_timed_questions_budget(seed_questions, db_session):
    """Verifies questions are packed within 900s time budget with subject representation."""
    engine = AssessmentEngine()
    items, _ = crud.list_questions(db_session, category="TECHNICAL", is_active=True)
    dict_questions = [
        {
            "id": q.id,
            "category": q.category,
            "subject": q.subject,
            "concept": q.concept,
            "difficulty_level": q.difficulty_level,
            "scope": q.scope,
            "time_limit_seconds": q.time_limit_seconds,
            "question_text": q.question_text,
            "is_active": q.is_active,
        }
        for q in items
    ]

    selected = engine.select_technical_timed_questions(
        available_questions=dict_questions,
        target_seconds=900,
    )

    assert len(selected) > 0
    total_seconds = sum(q.get("time_limit_seconds", 0) for q in selected)
    assert total_seconds <= 900, f"Total allocated seconds {total_seconds} exceeded 900s budget"

    subjects = {q.get("subject") for q in selected}
    assert "AI Engineering" in subjects
    assert "Software Engineering" in subjects or "DevOps and Cloud" in subjects


def test_build_qa_context_structured_labels():
    """Verifies build_qa_context formats questions with labels matching Section 1 of technical prompt."""
    engine = AssessmentEngine()
    questions = [
        {
            "id": 101,
            "subject": "AI Engineering",
            "concept": "RAG & Retrieval",
            "difficulty_level": "MEDIUM",
            "scope": "SPECIFIC",
            "question_text": "Explain RAG architecture.",
            "ground_truth": {
                "criteria": [{"point": "Vector store retrieval", "required": True}],
                "technical_keywords": ["embeddings", "vector"],
                "critical_failures": ["Confuses RAG with fine-tuning"],
            },
        }
    ]
    transcript = {"full_text": "RAG retrieves relevant document chunks using vector embeddings."}

    context = engine.build_qa_context(questions=questions, transcript=transcript)

    assert "=== Interview Questions ===" in context
    assert "question_id: 101" in context
    assert "subject: AI Engineering" in context
    assert "concept: RAG & Retrieval" in context
    assert "difficulty_level: MEDIUM" in context
    assert "scope: SPECIFIC" in context
    assert "ground_truth:" in context
    assert "- Vector store retrieval (required)" in context
    assert "technical_keywords: embeddings, vector" in context
    assert "- Confuses RAG with fine-tuning" in context
    assert "=== Candidate Transcript ===" in context


def test_scores_engine_accepts_rating_field():
    """Verifies ScoresEngine validates technical evaluations containing 'rating'."""
    scores_engine = ScoresEngine()
    raw_json = json.dumps(MOCK_TECHNICAL_LLM_EVALUATION)

    result = scores_engine.validate_and_parse(raw_json)

    assert result["is_valid"] is True
    assert len(result["validation_errors"]) == 0
    parsed = result["parsed_report"]
    assert "technical_evaluation" in parsed
    tech_eval = parsed["technical_evaluation"]
    assert tech_eval["overall_assessment"]["rating"] == "GOOD"
    assert len(tech_eval["question_evaluations"]) == 2
    assert tech_eval["question_evaluations"][0]["rating"] == "EXCELLENT"


def test_scores_engine_rejects_numeric_scores():
    """Verifies ScoresEngine rejects evaluation payloads with invalid score format."""
    scores_engine = ScoresEngine()
    invalid_payload = {
        "technical_evaluation": {
            "overall_assessment": {"rating": "GOOD", "summary": "Ok"},
            "subject_evaluations": [],
            "question_evaluations": [
                {"question_id": 1, "rating": "85%"}
            ],
        }
    }
    errors = []
    scores_engine._validate_technical_payload(invalid_payload["technical_evaluation"], errors)
    assert len(errors) > 0


# =============================================================================
# SECTION 3: API Test 1 — POST /candidates/{id}/assessments
# =============================================================================

def test_api_post_start_technical_assessment(auth_client, seed_questions, test_candidate):
    """Tests POST /candidates/{id}/assessments creates session with question metadata."""
    payload = {
        "candidate_id": test_candidate.id,
        "assessment_type": "TECHNICAL",
        "media_type": "AUDIO",
        "consent": {"audio_recording": True},
    }

    response = auth_client.post(f"/api/aiprep/candidates/{test_candidate.id}/assessments", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["assessment_id"] is not None
    assert data["assessment_type"] == "TECHNICAL"
    assert data["status"] == "IN_PROGRESS"

    questions = data["questions"]
    assert len(questions) > 0
    for q in questions:
        assert "id" in q
        assert "question_text" in q
        assert "subject" in q
        assert "concept" in q
        assert "difficulty_level" in q, "Missing difficulty_level on question"
        assert "scope" in q, "Missing scope on question"
        assert "time_limit_seconds" in q


def test_api_post_technical_assessment_deduplicates_mastered_questions(auth_client, seed_questions, test_candidate, db_session):
    """Verifies questions previously marked EXCELLENT are excluded from new session."""
    past_assessment = crud.create_assessment(
        db_session,
        candidate_id=test_candidate.id,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
    )
    crud.update_assessment_status(db_session, past_assessment.id, "COMPLETED")
    crud.save_assessment_report(
        db_session,
        past_assessment.id,
        {"transcript_evaluation": MOCK_TECHNICAL_LLM_EVALUATION},
    )

    payload = {
        "candidate_id": test_candidate.id,
        "assessment_type": "TECHNICAL",
        "media_type": "AUDIO",
    }
    response = auth_client.post(f"/api/aiprep/candidates/{test_candidate.id}/assessments", json=payload)

    assert response.status_code == 201
    new_questions = response.json()["data"]["questions"]
    question_ids = [q["id"] for q in new_questions]

    # Question 7001 was rated EXCELLENT in MOCK_TECHNICAL_LLM_EVALUATION, must be excluded
    assert 7001 not in question_ids, "Mastered question 7001 was re-served!"


# =============================================================================
# SECTION 4: API Test 2 — PUT /candidates/{id}/assessments/{id}
# =============================================================================

@patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks")
@patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file")
@patch("fapi.ai_prep.clients.llm_client.call_llm")
def test_api_put_submit_technical_assessment_sync(
    mock_llm, mock_audio, mock_stitch, auth_client, seed_questions, test_candidate, db_session
):
    """Tests PUT submission completes evaluation and stores technical evaluation report."""
    assessment = crud.create_assessment(
        db_session, candidate_id=test_candidate.id, assessment_type="TECHNICAL", media_type="AUDIO"
    )
    crud.save_assessment_data(
        db_session,
        assessment_id=assessment.id,
        questions=[{"id": 7001, "question_text": "What is RAG?"}],
        transcript={},
        audio_telemetry={},
        video_telemetry={},
    )

    mock_stitch.return_value = "/tmp/fake_stitched.webm"
    mock_audio.return_value = {
        "spoken_content": {
            "full_text": "RAG combines vector retrieval with LLM generation to ground the context. An image is a blueprint while a container is live.",
            "word_count": 22,
            "segments": [{"start": 1.2, "end": 14.4, "text": "RAG answer"}],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 12.0,
            "wpm": 130,
            "filler_count": 0,
            "silence_ratio": 0.05,
            "total_audio_duration_seconds": 15.0,
        },
    }
    mock_llm.return_value = json.dumps(MOCK_TECHNICAL_LLM_EVALUATION)

    submit_url = f"/api/aiprep/candidates/{test_candidate.id}/assessments/{assessment.id}"
    response = auth_client.put(submit_url)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in ("COMPLETED", "EVALUATING")


@patch("fapi.ai_prep.orchestrator.llm_orchestrator.call_llm")
def test_api_put_submit_direct_transcript_without_audio(
    mock_llm, auth_client, seed_questions, test_candidate, db_session
):
    """Verifies that submitting with direct transcript evaluates cleanly without needing audio files."""
    assessment = crud.create_assessment(
        db_session,
        candidate_id=test_candidate.id,
        assessment_type="TECHNICAL",
        media_type="AUDIO",
    )
    crud.save_assessment_data(
        db_session,
        assessment_id=assessment.id,
        questions=[{"id": 7001, "question_text": "What is RAG?", "subject": "AI Engineering", "concept": "RAG & Retrieval", "difficulty_level": "MEDIUM", "scope": "SPECIFIC", "time_limit_seconds": 120}],
        transcript={},
        audio_telemetry={},
        video_telemetry={},
    )
    mock_llm.return_value = json.dumps(MOCK_TECHNICAL_LLM_EVALUATION)

    submit_url = f"/api/aiprep/candidates/{test_candidate.id}/assessments/{assessment.id}"
    response = auth_client.put(
        submit_url,
        json={"transcript": "RAG architecture combines dense vector embeddings with LLM generation.", "is_final": True},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in ("COMPLETED", "EVALUATING")



# =============================================================================
# SECTION 5: API Test 3 — GET /candidates/{id}/assessments/{id}
# =============================================================================

def test_api_get_technical_assessment_report_serializer(auth_client, test_candidate, db_session):
    """Tests GET /candidates/{id}/assessments/{id} returns serialized technical report."""
    assessment = crud.create_assessment(
        db_session, candidate_id=test_candidate.id, assessment_type="TECHNICAL", media_type="AUDIO"
    )
    crud.update_assessment_status(db_session, assessment.id, "COMPLETED")
    crud.save_assessment_data(
        db_session,
        assessment_id=assessment.id,
        questions=[{"id": 7001, "question_text": "What is RAG?"}],
        transcript={"full_text": "My answer on RAG"},
        audio_telemetry={},
        video_telemetry={},
    )
    crud.save_assessment_report(
        db_session,
        assessment.id,
        {"transcript_evaluation": MOCK_TECHNICAL_LLM_EVALUATION},
    )

    get_url = f"/api/aiprep/candidates/{test_candidate.id}/assessments/{assessment.id}"
    response = auth_client.get(get_url)

    assert response.status_code == 200, response.text
    body = response.json()
    eval_dict = body["data"]["assessment_eval"]

    assert "technical_evaluation" in eval_dict
    assert eval_dict["technical_evaluation"] is not None

    tech_eval = eval_dict["technical_evaluation"]
    assert tech_eval["overall_assessment"]["rating"] == "GOOD"
    assert eval_dict["readiness"] == "GOOD"
    assert eval_dict["summary"] is not None
    assert eval_dict["strongest_signal"] is not None
    assert eval_dict["biggest_gap"] is not None

    assert len(tech_eval["question_evaluations"]) == 2
    assert len(tech_eval["subject_evaluations"]) == 3
    assert "difficulty_analysis" in tech_eval


# =============================================================================
# SECTION 6: End-to-End Chained Lifecycle Test
# =============================================================================

@patch("fapi.ai_prep.utils.aiprep_utils._stitch_assessment_chunks")
@patch("fapi.ai_prep.core.audio_engine.AudioMetricsEngine.process_audio_file")
@patch("fapi.ai_prep.orchestrator.llm_orchestrator.call_llm")
def test_e2e_technical_assessment_full_flow(
    mock_llm, mock_audio, mock_stitch, auth_client, seed_questions, test_candidate
):
    """Executes unbroken POST -> PUT -> GET lifecycle for Technical Assessment."""
    # Step 1: POST Start Assessment
    start_res = auth_client.post(
        f"/api/aiprep/candidates/{test_candidate.id}/assessments",
        json={"candidate_id": test_candidate.id, "assessment_type": "TECHNICAL", "media_type": "AUDIO"},
    )
    assert start_res.status_code == 201
    assessment_id = start_res.json()["data"]["assessment_id"]
    assigned_questions = start_res.json()["data"]["questions"]
    assert len(assigned_questions) > 0

    # Step 2: PUT Submit Assessment
    mock_stitch.return_value = "/tmp/mock.webm"
    mock_audio.return_value = {
        "spoken_content": {
            "full_text": "Sample candidate transcript answering assigned technical questions thoroughly with sufficient detail.",
            "word_count": 13,
            "segments": [{"start": 0.5, "end": 10.0, "text": "Transcript content"}],
        },
        "audio_telemetry": {
            "speaking_duration_seconds": 8.0,
            "wpm": 120,
            "filler_count": 0,
            "silence_ratio": 0.1,
            "total_audio_duration_seconds": 10.0,
        },
    }
    mock_llm.return_value = json.dumps(MOCK_TECHNICAL_LLM_EVALUATION)

    submit_res = auth_client.put(f"/api/aiprep/candidates/{test_candidate.id}/assessments/{assessment_id}")
    assert submit_res.status_code == 200

    # Ensure evaluation completed by running background pipeline
    from fapi.ai_prep.utils.aiprep_utils import _background_evaluation_pipeline
    import asyncio
    asyncio.run(
        _background_evaluation_pipeline(
            assessment_id=assessment_id,
            in_memory_transcript_text=mock_audio.return_value["spoken_content"]["full_text"],
            in_memory_audio_telemetry=mock_audio.return_value["audio_telemetry"],
            in_memory_video_telemetry={},
        )
    )

    # Step 3: GET Evaluation Report
    report_res = auth_client.get(f"/api/aiprep/candidates/{test_candidate.id}/assessments/{assessment_id}")
    assert report_res.status_code == 200
    report_data = report_res.json()["data"]["assessment_eval"]

    assert report_data["technical_evaluation"] is not None
    assert report_data["readiness"] == "GOOD"
    assert report_data["technical_evaluation"]["overall_assessment"]["rating"] == "GOOD"


# =============================================================================
# SECTION 6: LLM Client Exponential Backoff Retry Tests
# =============================================================================

def test_llm_client_retries_transient_429_and_succeeds(monkeypatch):
    """Verifies that transient 429 rate limit is retried and succeeds on attempt 2."""
    import asyncio
    from fapi.ai_prep.clients.llm_client import _execute_http_post
    import urllib.error
    import io

    attempts = 0

    class MockHTTPResponse:
        def __init__(self):
            self.headers = {"content-type": "application/json"}
        def read(self):
            return b'{"choices": [{"message": {"content": "success"}}]}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            fp = io.BytesIO(b'{"error": "rate limit"}')
            raise urllib.error.HTTPError(
                url="https://api.openai.com",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=fp,
            )
        return MockHTTPResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    async def _run():
        return await _execute_http_post(
            url="https://api.openai.com/v1/chat/completions",
            headers={},
            payload={"model": "gpt-4o"},
            timeout_seconds=5.0,
            provider="openai",
            max_retries=3,
            retry_delays=[0.01, 0.01],
        )

    res, _ = asyncio.run(_run())
    assert attempts == 2
    assert res["choices"][0]["message"]["content"] == "success"


def test_llm_client_does_not_retry_auth_error_401(monkeypatch):
    """Verifies that 401 authentication error fails immediately on attempt 1 without retrying."""
    import asyncio
    from fapi.ai_prep.clients.llm_client import _execute_http_post, LLMAuthenticationError
    import urllib.error
    import io

    attempts = 0

    def mock_urlopen(req, timeout):
        nonlocal attempts
        attempts += 1
        fp = io.BytesIO(b'{"error": "invalid api key"}')
        raise urllib.error.HTTPError(
            url="https://api.openai.com",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=fp,
        )

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    async def _run():
        await _execute_http_post(
            url="https://api.openai.com/v1/chat/completions",
            headers={},
            payload={"model": "gpt-4o"},
            timeout_seconds=5.0,
            provider="openai",
            max_retries=3,
            retry_delays=[0.01, 0.01],
        )

    with pytest.raises(LLMAuthenticationError):
        asyncio.run(_run())

    assert attempts == 1


# =============================================================================
# SECTION 8: DP Subset-Sum Exact Fit & Strict 900s Hard Cap Tests
# =============================================================================

def test_find_exact_fit_dp_finds_four_question_combo():
    """Verifies DP exact fit finds combinations of 4+ questions (which O(n^3) couldn't)."""
    engine = AssessmentEngine()
    pool = [
        {"id": 1, "time_limit_seconds": 60, "question_text": "Q1"},
        {"id": 2, "time_limit_seconds": 60, "question_text": "Q2"},
        {"id": 3, "time_limit_seconds": 60, "question_text": "Q3"},
        {"id": 4, "time_limit_seconds": 60, "question_text": "Q4"},
        {"id": 5, "time_limit_seconds": 90, "question_text": "Q5"},
    ]
    # Target 240 can only be formed by 60 + 60 + 60 + 60 (4 questions)
    match = engine._find_exact_fit(pool, target_sum=240)
    assert match is not None
    assert len(match) == 4
    assert sum(engine.get_question_time_limit(q) for q in match) == 240


def test_find_exact_fit_dp_performance_large_pool():
    """Verifies DP subset-sum algorithm scales efficiently (< 100ms) on a 1,000-question pool."""
    import time
    engine = AssessmentEngine()
    # Generate 1,000 questions with varying times
    pool = [
        {"id": i, "time_limit_seconds": 60 + (i % 5) * 30, "question_text": f"Q{i}"}
        for i in range(1, 1001)
    ]
    start_time = time.perf_counter()
    match = engine._find_exact_fit(pool, target_sum=330)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 0.1, f"DP exact fit took {elapsed:.4f}s, expected < 0.1s"
    assert match is not None
    assert sum(engine.get_question_time_limit(q) for q in match) == 330


def test_technical_timed_selection_strict_900s_hard_cap():
    """Verifies that subject quotas strictly enforce budget and never exceed 900 seconds."""
    engine = AssessmentEngine()
    # Create large pool with heavy broad questions
    pool = []
    qid = 1
    for subj in ["AI Engineering", "Software Engineering", "DevOps and Cloud"]:
        for _ in range(20):
            pool.append({
                "id": qid,
                "subject": subj,
                "concept": f"Concept_{qid}",
                "difficulty_level": "HARD",
                "scope": "BROAD",
                "time_limit_seconds": 210,
                "question_text": f"Broad architectural question {qid}",
            })
            qid += 1
            pool.append({
                "id": qid,
                "subject": subj,
                "concept": f"Concept_{qid}",
                "difficulty_level": "EASY",
                "scope": "SPECIFIC",
                "time_limit_seconds": 60,
                "question_text": f"Specific question {qid}",
            })
            qid += 1

    selected = engine.select_technical_timed_questions(
        available_questions=pool,
        target_seconds=900,
    )

    total_time = sum(q.get("time_limit_seconds") or engine.get_question_time_limit(q) for q in selected)
    assert total_time <= 900, f"Assessment exceeded 900s budget: got {total_time}s"




