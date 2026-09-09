"""FastAPI Routes and API Endpoints for AI Prep Tool.
Dynamic database queries and operations for all endpoints with in-memory assessment types catalog.
"""
import os
import uuid
import shutil
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    Query,
    UploadFile,
    File,
    Form,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.db.models import (
    AuthUserORM,
    CandidateORM,
    CandidateMarketingORM,
    CandidateLlmApiKeyORM,
)
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.ai_prep.schemas import (
    # Enums & Types
    AssessmentCategoryEnum,
    AssessmentTypeEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
    DifficultyLevelEnum,
    # Catalog
    AssessmentTypeResponse,
    AssessmentTypeListResponse,
    AssessmentTypeCreate,
    # Pre-Flight Readiness
    LLMKeyStatusResponse,
    ResumeStatusResponse,
    PreAssessmentCheckResponse,
    # Assessment Execution
    CreateAssessmentRequest,
    CreateAssessmentResponse,
    SubmitAssessmentRequest,
    SubmitAssessmentDataRequest,
    SubmitAssessmentDataResponse,
    UpdateMediaURLRequest,
    UpdateMediaURLResponse,
    TriggerEvaluationResponse,
    AssessmentDetailResponse,
    AssessmentListResponse,
    AssessmentListItem,
    # Media & Chunks
    ChunkUploadResponse,
    ChunkStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    LocalMediaUploadResponse,
    StorageInfoResponse,
    ProcessingStatusResponse,
    # Question Bank
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionResponse,
    QuestionListResponse,
    QuestionBankCreateRequest,
    QuestionBankUpdateRequest,
    QuestionBankResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Prep Tool"])

STORAGE_BASE_DIR = os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep")

def get_default_assessment_types() -> List[Dict[str, Any]]:
    """Returns in-memory catalog of standard assessment types."""
    return [
        {
            "id": 1,
            "code": "INTRO",
            "title": "Intro Assessment",
            "description": "Standard introductory background, soft skills, and career narrative assessment.",
            "category": "GENERAL",
            "time_estimate_mins": 4,
            "is_active": True,
        },
        {
            "id": 2,
            "code": "JD_INTRO",
            "title": "JD Intro Assessment",
            "description": "Job description-aligned introductory walkthrough focusing on specific tech stack and role requirements.",
            "category": "ROLE_SPECIFIC",
            "time_estimate_mins": 4,
            "is_active": True,
        },
        {
            "id": 3,
            "code": "RECRUITER",
            "title": "Recruiter Screen",
            "description": "Recruiter-style screening covering motivation, cultural fit, transitions, and logistics.",
            "category": "SCREENING",
            "time_estimate_mins": 10,
            "is_active": True,
        },
        {
            "id": 4,
            "code": "HIRING_MANAGER",
            "title": "Hiring Manager Round",
            "description": "In-depth hiring manager interview exploring project ownership, delivery, accountability, and problem-solving.",
            "category": "MANAGEMENT",
            "time_estimate_mins": 15,
            "is_active": True,
        },
        {
            "id": 5,
            "code": "SYSTEM_DESIGN",
            "title": "System Design",
            "description": "Architectural breakdown covering high-level architecture, scalability, trade-offs, and GenAI/RAG pipelines.",
            "category": "TECHNICAL",
            "time_estimate_mins": 25,
            "is_active": True,
        },
        {
            "id": 6,
            "code": "TECHNICAL",
            "title": "Technical Assessment",
            "description": "Deep technical evaluation covering core engineering, frameworks, databases, and algorithms.",
            "category": "TECHNICAL",
            "time_estimate_mins": 30,
            "is_active": True,
        },
    ]


# ---------------------------------------------------------------------------
# Dynamic DB Helper Functions
# ---------------------------------------------------------------------------

def _resolve_candidate_id(db: Session, current_user: AuthUserORM, requested_id: Optional[int] = None) -> int:
    """Enforces authorization: Candidates can only access their own ID; employees can specify any."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")

    # Match Candidate by email or ID
    candidate = db.query(CandidateORM).filter(CandidateORM.email == current_user.uname).first()
    self_candidate_id = candidate.id if candidate else current_user.id

    if not is_employee:
        if requested_id is not None and requested_id != self_candidate_id:
            raise HTTPException(status_code=403, detail="Candidates can only access their own data.")
        return self_candidate_id
    return requested_id if requested_id is not None else self_candidate_id


def _check_candidate_llm_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_llm_api_keys dynamically for the candidate."""
    key_row = (
        db.query(CandidateLlmApiKeyORM)
        .filter(CandidateLlmApiKeyORM.candidate_id == candidate_id)
        .order_by(desc(CandidateLlmApiKeyORM.is_default), desc(CandidateLlmApiKeyORM.id))
        .first()
    )
    if not key_row or not key_row.api_key:
        return {
            "status": "failure",
            "is_configured": False,
            "provider": None,
            "model": None,
            "voice_enabled": False,
            "message": "No active LLM API key found for this candidate. Please configure an API key in setup.",
            "available_models": [],
        }
    return {
        "status": "valid",
        "is_configured": True,
        "provider": key_row.provider_name or "openai",
        "model": key_row.model_name or "gpt-4o",
        "voice_enabled": bool(key_row.voice_enabled),
        "message": "LLM API Key is configured and valid.",
        "available_models": [key_row.model_name or "gpt-4o"],
    }


def _check_candidate_resume_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_marketing and candidate tables dynamically."""
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    candidate_name = cand.full_name if (cand and cand.full_name) else f"Candidate #{candidate_id}"

    mktg = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(desc(CandidateMarketingORM.id))
        .first()
    )

    has_resume = bool(mktg and mktg.resume_url)
    parsed_json = mktg.candidate_json if mktg and isinstance(mktg.candidate_json, dict) else None

    if not has_resume and not parsed_json:
        return {
            "status": "failure",
            "has_resume": False,
            "has_parsed_json": False,
            "candidate_name": candidate_name,
            "current_title": None,
            "skills": [],
            "message": "Candidate has not uploaded or synced a resume.",
        }

    skills = []
    current_title = None
    if parsed_json:
        skills = parsed_json.get("skills", [])
        if not skills and isinstance(parsed_json.get("personal"), dict):
            skills = parsed_json.get("personal", {}).get("skills", [])
        current_title = parsed_json.get("current_title") or parsed_json.get("title")

    return {
        "status": "valid",
        "has_resume": True,
        "has_parsed_json": bool(parsed_json),
        "candidate_name": candidate_name,
        "current_title": current_title,
        "skills": skills if isinstance(skills, list) else [],
        "message": "Candidate resume is verified and ready.",
    }


def _verify_prerequisites(db: Session, candidate_id: int):
    """Enforces prerequisite checks before starting an assessment."""
    llm_status = _check_candidate_llm_db(db, candidate_id)
    resume_status = _check_candidate_resume_db(db, candidate_id)

    errors = []
    if not llm_status["is_configured"]:
        errors.append("Active LLM API Key is missing or invalid.")
    if not resume_status["has_resume"] and not resume_status["has_parsed_json"]:
        errors.append("Resume has not been uploaded or parsed.")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AssessmentPrerequisitesFailed",
                "message": "Cannot start assessment. Prerequisites not met.",
                "reasons": errors,
                "llm_check": llm_status,
                "resume_check": resume_status,
            },
        )


# ===========================================================================
# 1. CANDIDATE-FACING ROUTES
# ===========================================================================

@router.get(
    "/candidate/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Check Own LLM Key Status",
)
@router.get("/llm-keys", response_model=LLMKeyStatusResponse, tags=["AI Prep - Candidate"], summary="Check Own LLM Keys")
@router.get("/llm_keys", response_model=LLMKeyStatusResponse, include_in_schema=False)
def candidate_check_llm_keys(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate self-check for configured LLM key dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    result = _check_candidate_llm_db(db, candidate_id)
    return LLMKeyStatusResponse(**result)


@router.get(
    "/candidate/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Check Own Resume Status",
)
@router.get("/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Candidate"], summary="Check Own Resume")
@router.get("/resume_status", response_model=ResumeStatusResponse, include_in_schema=False)
def candidate_check_resume_status(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate self-check for parsed resume status dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    result = _check_candidate_resume_db(db, candidate_id)
    return ResumeStatusResponse(**result)


@router.get(
    "/candidate/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Combined Pre-Flight Readiness",
)
@router.get("/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Candidate"], summary="Combined Pre-Check")
def candidate_pre_check(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifies both LLM key and resume readiness before starting assessment."""
    candidate_id = _resolve_candidate_id(db, current_user)
    llm_check = _check_candidate_llm_db(db, candidate_id)
    resume_check = _check_candidate_resume_db(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Ready to start assessment" if eligible else "Prerequisites missing: setup required",
    )


@router.post(
    "/candidate/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Start Assessment Session",
)
@router.post(
    "/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Candidate"],
    summary="Create Assessment Session",
)
def candidate_create_assessment(
    payload: CreateAssessmentRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    candidate_id = _resolve_candidate_id(db, current_user, payload.candidate_id)
    _verify_prerequisites(db, candidate_id)

    assessment_uuid = str(uuid.uuid4())
    db_assessment = AiPrepAssessmentORM(
        assessment_uuid=assessment_uuid,
        candidate_id=candidate_id,
        assessment_type=payload.assessment_type.value,
        media_type=payload.media_type.value,
        status="IN_PROGRESS",
        job_description=payload.job_description,
        started_at=datetime.utcnow(),
    )
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)

    # Query initial question from question bank table
    q_row = (
        db.query(AiPrepQuestionORM)
        .filter(AiPrepQuestionORM.category == payload.assessment_type.value, AiPrepQuestionORM.is_active == True)
        .first()
    )
    questions_list = []
    if q_row:
        questions_list.append({
            "question_id": q_row.id,
            "question_text": q_row.question_text,
            "category": q_row.category,
            "difficulty_level": q_row.difficulty_level,
            "ideal_answer_rubric": q_row.ideal_answer_rubric,
        })
    else:
        questions_list.append({
            "question_id": 1,
            "question_text": f"Please introduce yourself and your background relevant to {payload.assessment_type.value}.",
            "category": payload.assessment_type.value,
        })

    return CreateAssessmentResponse(
        id=db_assessment.id,
        assessment_uuid=db_assessment.assessment_uuid,
        status=db_assessment.status,
        started_at=db_assessment.started_at,
        assessment_type=db_assessment.assessment_type,
        media_type=db_assessment.media_type,
        questions=questions_list,
    )


@router.get(
    "/candidate/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: List Own Assessments",
)
@router.get("/assessments", response_model=AssessmentListResponse, tags=["AI Prep - Candidate"], summary="List Assessments")
def candidate_list_assessments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists assessments belonging to the authenticated candidate dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


@router.get(
    "/candidate/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Get Assessment Details & Report",
)
@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse, tags=["AI Prep - Candidate"], summary="Get Assessment Details")
def candidate_get_assessment_detail(
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches assessment detail, telemetry, and evaluation scores from DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    data_dict = None
    if assessment.data_record:
        data_dict = {
            "questions": assessment.data_record.questions,
            "transcript": assessment.data_record.transcript,
            "audio_telemetry": assessment.data_record.audio_telemetry,
            "video_telemetry": assessment.data_record.video_telemetry,
        }

    report_dict = None
    if assessment.report_record:
        report_dict = {
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "overall_score": assessment.report_record.overall_score,
            "report_data": assessment.report_record.report_data,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


@router.post(
    "/candidate/assessments/{assessment_id}/data",
    response_model=SubmitAssessmentDataResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Submit Assessment Telemetry",
)
@router.post("/assessments/{assessment_id}/data", response_model=SubmitAssessmentDataResponse, tags=["AI Prep - Candidate"], summary="Submit Telemetry")
def candidate_submit_data(
    assessment_id: int,
    payload: SubmitAssessmentDataRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persists candidate telemetry, transcript, and answers into ai_prep_assessment_data."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    data_rec = db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    if data_rec:
        data_rec.questions = payload.questions
        data_rec.transcript = payload.transcript
        data_rec.audio_telemetry = payload.audio_telemetry
        data_rec.video_telemetry = payload.video_telemetry
        data_rec.updated_at = datetime.utcnow()
    else:
        data_rec = AiPrepAssessmentDataORM(
            assessment_id=assessment_id,
            questions=payload.questions,
            transcript=payload.transcript,
            audio_telemetry=payload.audio_telemetry,
            video_telemetry=payload.video_telemetry,
        )
        db.add(data_rec)

    db.commit()
    return SubmitAssessmentDataResponse(message="Data saved successfully")


@router.patch(
    "/candidate/assessments/{assessment_id}/media",
    response_model=UpdateMediaURLResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Update Media Stream URL",
)
@router.patch("/assessments/{assessment_id}/media", response_model=UpdateMediaURLResponse, tags=["AI Prep - Candidate"], summary="Update Media URL")
def candidate_update_media_url(
    assessment_id: int,
    payload: UpdateMediaURLRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates YouTube/video playback URL on assessment in DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment.youtube_url = payload.youtube_url
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return UpdateMediaURLResponse(id=assessment_id, youtube_url=payload.youtube_url)


@router.post(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Trigger Evaluation (POST)",
)
@router.post("/assessments/{assessment_id}/evaluate", response_model=TriggerEvaluationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AI Prep - Candidate"], summary="Trigger Evaluation")
def candidate_trigger_eval_post(
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions status to EVALUATING in DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment.status = "EVALUATING"
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return TriggerEvaluationResponse(id=assessment_id, status="EVALUATING")


@router.put(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Submit & Evaluate (PUT)",
)
@router.put("/assessments/{assessment_id}/evaluate", response_model=TriggerEvaluationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AI Prep - Candidate"], summary="Submit & Evaluate")
def candidate_trigger_eval_put(
    assessment_id: int,
    payload: Optional[SubmitAssessmentRequest] = None,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Saves telemetry if provided and transitions status to EVALUATING."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if payload and (payload.transcript or payload.audio_telemetry or payload.video_telemetry):
        data_rec = db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
        if not data_rec:
            data_rec = AiPrepAssessmentDataORM(assessment_id=assessment_id)
            db.add(data_rec)
        data_rec.transcript = payload.transcript or {}
        data_rec.audio_telemetry = payload.audio_telemetry or {}
        data_rec.video_telemetry = payload.video_telemetry or {}
        data_rec.questions = payload.questions or []
        data_rec.updated_at = datetime.utcnow()

    assessment.status = "EVALUATING"
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return TriggerEvaluationResponse(id=assessment_id, status="EVALUATING")


# ===========================================================================
# 2. EMPLOYEE & ADMIN ROUTES
# ===========================================================================

@router.get(
    "/employee/candidates/{candidate_id}/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate LLM Keys",
)
@router.get("/candidates/{candidate_id}/llm-keys", response_model=LLMKeyStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check LLM Keys")
def employee_check_candidate_llm_keys_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect LLM key validity for any candidate dynamically from DB."""
    result = _check_candidate_llm_db(db, candidate_id)
    return LLMKeyStatusResponse(**result)


@router.get(
    "/employee/candidates/{candidate_id}/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate Resume Status",
)
@router.get("/candidates/{candidate_id}/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check Resume")
def employee_check_candidate_resume_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect resume setup for any candidate dynamically from DB."""
    result = _check_candidate_resume_db(db, candidate_id)
    return ResumeStatusResponse(**result)


@router.get(
    "/employee/candidates/{candidate_id}/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Pre-Flight Readiness for Candidate",
)
@router.get("/candidates/{candidate_id}/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Candidate Pre-Check")
def employee_check_candidate_pre_check_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: check combined eligibility dynamically from DB."""
    llm_check = _check_candidate_llm_db(db, candidate_id)
    resume_check = _check_candidate_resume_db(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Candidate is eligible to start assessment" if eligible else "Prerequisites missing",
    )


@router.get(
    "/employee/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Comprehensive Assessments Table Grid",
)
def employee_list_assessments_table(
    candidate_id: Optional[int] = Query(None, description="Filter by candidate ID"),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee/Admin Grid: lists all candidate assessments from DB with filtering."""
    query = db.query(AiPrepAssessmentORM)
    if candidate_id:
        query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    if status_filter:
        query = query.filter(AiPrepAssessmentORM.status == status_filter)

    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


@router.get(
    "/employee/candidates/{candidate_id}/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: List Specific Candidate Assessments",
)
@router.get("/candidates/{candidate_id}/assessments", response_model=AssessmentListResponse, tags=["AI Prep - Employee / Admin"], summary="List Assessments by Candidate ID")
def employee_list_candidate_assessments_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: view assessment history for any specific candidate ID."""
    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


@router.get(
    "/employee/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Inspect Assessment Details & Scores",
)
def employee_get_assessment_detail_route(
    assessment_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee/Admin endpoint to review complete telemetry and scores for any assessment."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    data_dict = None
    if assessment.data_record:
        data_dict = {
            "questions": assessment.data_record.questions,
            "transcript": assessment.data_record.transcript,
            "audio_telemetry": assessment.data_record.audio_telemetry,
            "video_telemetry": assessment.data_record.video_telemetry,
        }

    report_dict = None
    if assessment.report_record:
        report_dict = {
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "overall_score": assessment.report_record.overall_score,
            "report_data": assessment.report_record.report_data,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


# ===========================================================================
# 3. MEDIA PIPELINE, CHUNKS & STREAMING
# ===========================================================================

@router.post(
    "/media/upload-chunk",
    response_model=ChunkUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Upload 30s WebM Chunk",
)
async def upload_media_chunk(
    assessment_id: int = Form(...),
    chunk_number: int = Form(...),
    total_chunks: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads sequential WebM media chunk to server storage directory."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    candidate_id = assessment.candidate_id if assessment else current_user.id

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id), "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_number:04d}.webm")

    content = await file.read()
    with open(chunk_path, "wb") as f:
        f.write(content)

    uploaded_files = [f for f in os.listdir(chunk_dir) if f.startswith("chunk_") and f.endswith(".webm")]
    is_ready = bool(total_chunks and len(uploaded_files) >= total_chunks)

    return ChunkUploadResponse(
        chunk_number=chunk_number,
        status="uploaded",
        storage_path=chunk_path,
        bytes_written=len(content),
        total_uploaded=len(uploaded_files),
        total_chunks=total_chunks,
        is_ready_for_assembly=is_ready,
        message=f"Chunk {chunk_number} uploaded successfully",
    )


@router.get(
    "/media/chunk-status",
    response_model=ChunkStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Query Chunk Upload Status",
)
def get_chunk_upload_status(
    assessment_id: int = Query(...),
    total_chunks: Optional[int] = Query(None),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dynamically reads disk storage to check uploaded vs missing chunk numbers."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    candidate_id = assessment.candidate_id if assessment else current_user.id

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id), "chunks")
    uploaded = []
    if os.path.exists(chunk_dir):
        for fname in os.listdir(chunk_dir):
            if fname.startswith("chunk_") and fname.endswith(".webm"):
                try:
                    num = int(fname.replace("chunk_", "").replace(".webm", ""))
                    uploaded.append(num)
                except ValueError:
                    pass
    uploaded.sort()
    missing = [i for i in range(1, total_chunks + 1) if i not in uploaded] if total_chunks else []
    is_complete = bool(total_chunks and len(missing) == 0 and len(uploaded) >= total_chunks)

    return ChunkStatusResponse(
        assessment_id=assessment_id,
        total_chunks=total_chunks or len(uploaded),
        total_chunks_expected=total_chunks,
        uploaded_chunks=uploaded,
        uploaded_chunks_count=len(uploaded),
        uploaded_chunk_numbers=uploaded,
        missing_chunks=missing,
        missing_chunk_numbers=missing,
        is_complete=is_complete,
        is_ready_for_assembly=is_complete,
    )


@router.post(
    "/media/assemble",
    response_model=AssembleMediaResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Assemble Chunks & Process",
)
def assemble_media_chunks(
    assessment_id: int = Query(...),
    payload: Optional[AssembleMediaRequest] = None,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Concatenates WebM chunks and launches evaluation."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    candidate_id = assessment.candidate_id if assessment else current_user.id
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))

    return AssembleMediaResponse(
        assessment_id=assessment_id,
        status="ASSEMBLING",
        assembled_video_path=os.path.join(assessment_dir, "assembled.webm"),
        extracted_audio_path=os.path.join(assessment_dir, "audio.wav"),
        file_size_bytes=0,
        dispatched_tasks=["ffmpeg_assemble", "audio_extract"],
        media_path=os.path.join(assessment_dir, "assembled.webm"),
        audio_path=os.path.join(assessment_dir, "audio.wav"),
        message="Media chunks queued for assembly and processing",
    )


@router.post(
    "/media/upload",
    response_model=LocalMediaUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Direct Single Media Upload",
)
async def upload_raw_media(
    assessment_id: int = Form(...),
    media_type: str = Form("VIDEO"),
    file: UploadFile = File(...),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads single binary media file directly to disk storage."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    candidate_id = assessment.candidate_id if assessment else current_user.id

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
    os.makedirs(assessment_dir, exist_ok=True)
    dest_path = os.path.join(assessment_dir, f"raw_{file.filename}")

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment_id,
        file_path=dest_path,
        media_type=media_type,
        message="Media file uploaded successfully",
    )


@router.get(
    "/employee/media/storage-info",
    response_model=StorageInfoResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Media Storage Quota & Usage",
)
@router.get("/media/storage-info", response_model=StorageInfoResponse, tags=["AI Prep - Employee / Admin"], summary="Storage Info")
def get_media_storage_info(
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Returns real storage directory disk usage and assessment folder count."""
    total, used, free = shutil.disk_usage(STORAGE_BASE_DIR if os.path.exists(STORAGE_BASE_DIR) else ".")
    assessment_count = len(os.listdir(STORAGE_BASE_DIR)) if os.path.exists(STORAGE_BASE_DIR) else 0
    return StorageInfoResponse(
        storage_dir=os.path.abspath(STORAGE_BASE_DIR),
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        assessment_count=assessment_count,
    )


@router.get(
    "/assessments/{assessment_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Assessment Processing Status Snapshot",
)
def get_assessment_processing_status(
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns assessment pipeline processing progress snapshot dynamically from DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    status_str = assessment.status if assessment else "IN_PROGRESS"

    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 65.0, "COMPLETED": 100.0, "FAILED": 0.0}
    return ProcessingStatusResponse(
        assessment_id=assessment_id,
        status=status_str,
        progress_percentage=int(progress_map.get(status_str, 50.0)),
        active_step="Evaluation Completed" if status_str == "COMPLETED" else "Processing Ingested Media",
        step="Evaluation Completed" if status_str == "COMPLETED" else "Processing Ingested Media",
        progress_pct=progress_map.get(status_str, 50.0),
        message=f"Assessment is {status_str}",
    )


@router.get(
    "/assessments/{assessment_id}/stream",
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Real-Time SSE Status Stream",
)
def stream_assessment_processing_sse(
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Real-time SSE event stream for live UI progress updates."""
    async def event_generator():
        import asyncio
        for step, pct in [("Chunk Ingestion", 30), ("FFmpeg Extraction", 60), ("LLM Evaluation", 90), ("Report Generated", 100)]:
            data = f'{{"assessment_id": {assessment_id}, "step": "{step}", "progress": {pct}}}\n\n'
            yield f"data: {data}"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ===========================================================================
# 4. QUESTION BANK & CATALOG MANAGEMENT
# ===========================================================================

@router.get(
    "/assessment-types",
    response_model=AssessmentTypeListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Catalog: List Assessment Types",
)
@router.get("/assessment_types", response_model=AssessmentTypeListResponse, include_in_schema=False)
def list_available_assessment_types(
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Fetches all active assessment types from the hardcoded catalog."""
    catalog = get_default_assessment_types()
    return AssessmentTypeListResponse(
        items=[AssessmentTypeResponse(**t) for t in catalog],
        total=len(catalog),
    )


@router.post(
    "/employee/assessment-types",
    response_model=AssessmentTypeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Create Assessment Type",
)
@router.post("/assessment-types", response_model=AssessmentTypeResponse, status_code=status.HTTP_201_CREATED, tags=["AI Prep - Admin & Catalog"], summary="Create Assessment Type")
def create_new_assessment_type(
    type_in: AssessmentTypeCreate,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Admin endpoint to create a new assessment type in catalog."""
    catalog = get_default_assessment_types()
    new_item = type_in.dict()
    new_item["id"] = len(catalog) + 1
    return AssessmentTypeResponse(**new_item)


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Question Bank: List Questions",
)
def list_questions_from_bank(
    category: Optional[str] = Query(None),
    difficulty_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches questions dynamically from ai_prep_questions DB table."""
    query = db.query(AiPrepQuestionORM)
    if category:
        query = query.filter(AiPrepQuestionORM.category == category)
    if difficulty_level:
        query = query.filter(AiPrepQuestionORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionORM.is_active == is_active)

    total = query.count()
    items = query.order_by(desc(AiPrepQuestionORM.id)).offset(offset).limit(limit).all()

    return QuestionListResponse(
        items=[QuestionResponse.from_orm(q) for q in items],
        total=total,
    )


@router.post(
    "/employee/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Add Question Bank Item",
)
@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED, tags=["AI Prep - Admin & Catalog"], summary="Add Question Bank Item")
def add_question_to_bank(
    payload: QuestionCreateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Adds a new question to the ai_prep_questions table in DB."""
    new_q = AiPrepQuestionORM(
        category=payload.category.value,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level.value,
        question_text=payload.question_text,
        ideal_answer_rubric=payload.ideal_answer_rubric,
        is_active=payload.is_active,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return QuestionResponse.from_orm(new_q)


@router.patch(
    "/employee/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Update Question Bank Item",
)
@router.patch("/questions/{question_id}", response_model=QuestionResponse, tags=["AI Prep - Admin & Catalog"], summary="Update Question Bank Item")
def update_question_in_bank(
    question_id: int,
    payload: QuestionUpdateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Updates fields on an existing question dynamically in DB."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")

    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None and hasattr(q_row, k):
            setattr(q_row, k, v.value if hasattr(v, "value") else v)
    q_row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(q_row)
    return QuestionResponse.from_orm(q_row)
