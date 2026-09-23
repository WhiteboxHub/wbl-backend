"""Business logic and utility functions for AI Prep Tool.
Follows WBL Backend code architecture standards separating routing and logic.
"""
import os
import uuid
import json
import shutil
import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, status, BackgroundTasks, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from fapi.db.database import SessionLocal
from fapi.ai_prep import crud
from fapi.ai_prep.config import settings
from fapi.ai_prep.orchestrator import assessment_orchestrator, llm_orchestrator

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
    AssessmentTypeResponse,
    AssessmentTypeListResponse,
    AssessmentTypeCreate,
    LLMKeyStatusResponse,
    ResumeStatusResponse,
    PreAssessmentCheckResponse,
    CreateAssessmentRequest,
    CreateAssessmentResponse,
    SubmitAssessmentRequest,
    SubmitAssessmentDataRequest,
    SubmitAssessmentDataResponse,
    UpdateMediaURLRequest,
    UpdateMediaURLResponse,
    TriggerEvaluationResponse,
    AssessmentDetailResponse,
    AssessmentDataResponse,
    AssessmentReportResponse,
    AssessmentListResponse,
    AssessmentListItem,
    ChunkUploadResponse,
    ChunkStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    LocalMediaUploadResponse,
    StorageInfoResponse,
    ProcessingStatusResponse,
    AudioUploadResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionResponse,
    QuestionListResponse,
)

logger = logging.getLogger(__name__)

STORAGE_BASE_DIR = os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep")


# ---------------------------------------------------------------------------
# In-Memory Assessment Types Catalog
# ---------------------------------------------------------------------------

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
# Dynamic DB & Authorization Helpers
# ---------------------------------------------------------------------------

def _resolve_candidate_id(db: Session, current_user: AuthUserORM, requested_id: Optional[int] = None) -> int:
    """Enforces authorization: Candidates can only access their own ID; employees can specify any."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")

    # Match Candidate by email or ID
    candidate = db.query(CandidateORM).filter(CandidateORM.email == current_user.uname).first()
    if not candidate:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == current_user.id).first()
    if not candidate and not is_employee:
        raise HTTPException(status_code=404, detail="Candidate record not found.")

    self_candidate_id = candidate.id if candidate else current_user.id

    if not is_employee:
        if requested_id is not None and requested_id != self_candidate_id:
            raise HTTPException(status_code=403, detail="Candidates can only access their own data.")
        return self_candidate_id
    return requested_id if requested_id is not None else self_candidate_id


def _check_candidate_llm_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_llm_api_keys dynamically for the candidate via crud."""
    return crud.check_candidate_llm_key(db, candidate_id)


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
    parsed_json = None
    if mktg and mktg.candidate_json:
        if isinstance(mktg.candidate_json, dict):
            parsed_json = mktg.candidate_json
        elif isinstance(mktg.candidate_json, str):
            try:
                parsed_json = json.loads(mktg.candidate_json)
            except Exception:
                parsed_json = None

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

    current_title: Optional[str] = None
    if parsed_json:
        raw_title = parsed_json.get("current_title") or parsed_json.get("title")
        current_title = str(raw_title).strip() if raw_title else None

    return {
        "status": "valid",
        "has_resume": True,
        "has_parsed_json": bool(parsed_json),
        "candidate_name": candidate_name,
        "current_title": current_title,
        "skills": [],
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


# ---------------------------------------------------------------------------
# 1. Candidate Business Logic Functions
# ---------------------------------------------------------------------------

def candidate_check_llm_keys_logic(db: Session, current_user: AuthUserORM) -> LLMKeyStatusResponse:
    """Candidate self-check for configured LLM key dynamically from DB."""
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
        result = _check_candidate_llm_db(db, candidate_id)
        return LLMKeyStatusResponse(**result)
    except HTTPException as e:
        if e.status_code == 404:
            return LLMKeyStatusResponse(
                status="failure",
                is_configured=False,
                provider=None,
                model=None,
                voice_enabled=False,
                message="Candidate profile record not found. Please configure an API key in setup.",
                available_models=[],
            )
        raise


def candidate_check_resume_status_logic(db: Session, current_user: AuthUserORM) -> ResumeStatusResponse:
    """Candidate self-check for parsed resume status dynamically from DB."""
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
        result = _check_candidate_resume_db(db, candidate_id)
        return ResumeStatusResponse(**result)
    except HTTPException as e:
        if e.status_code == 404:
            cand_name = getattr(current_user, "fullname", None) or getattr(current_user, "uname", "Candidate")
            return ResumeStatusResponse(
                status="failure",
                has_resume=False,
                has_parsed_json=False,
                candidate_name=cand_name,
                current_title=None,
                skills=[],
                message="Candidate profile record not found. Please complete profile setup.",
            )
        raise


def candidate_pre_check_logic(db: Session, current_user: AuthUserORM) -> PreAssessmentCheckResponse:
    """Verifies both LLM key and resume readiness before starting assessment."""
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
    except HTTPException as e:
        if e.status_code == 404:
            cand_name = getattr(current_user, "fullname", None) or getattr(current_user, "uname", "Candidate")
            return PreAssessmentCheckResponse(
                eligible=False,
                candidate_id=getattr(current_user, "id", 0),
                llm_check=LLMKeyStatusResponse(
                    status="failure",
                    is_configured=False,
                    message="Candidate profile record not found.",
                ),
                resume_check=ResumeStatusResponse(
                    status="failure",
                    has_resume=False,
                    has_parsed_json=False,
                    candidate_name=cand_name,
                    message="Candidate profile record not found. Please complete profile setup.",
                ),
                message="Prerequisites missing: setup required",
            )
        raise
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




def candidate_create_assessment_logic(
    db: Session,
    current_user: AuthUserORM,
    payload: CreateAssessmentRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CreateAssessmentResponse:
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    candidate_id = _resolve_candidate_id(db, current_user, payload.candidate_id)
    _verify_prerequisites(db, candidate_id)

    assessment_type_str = (
        payload.assessment_type.value
        if hasattr(payload.assessment_type, "value")
        else str(payload.assessment_type)
    ).upper().strip()

    # Step 1: Retrieve the question BEFORE creating the assessment row.
    # If no active question exists for this type the function must fail here
    # without creating any database record.
    try:
        questions_list = assessment_orchestrator.get_questions_for_assessment(
            db=db,
            assessment_type=assessment_type_str,
        )
    except Exception as exc:
        logger.error(
            "Question bank retrieval failed for type '%s': %s",
            assessment_type_str, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question could not be loaded. Please try again or contact support.",
        )

    if not questions_list:
        logger.warning(
            "No active questions found in the question bank for type '%s'.",
            assessment_type_str,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question could not be loaded. Please try again or contact support.",
        )

    # Step 2: Question confirmed — now create the assessment record.
    db_assessment = crud.create_assessment(
        db=db,
        candidate_id=candidate_id,
        assessment_type=assessment_type_str,
        media_type=payload.media_type.value if hasattr(payload.media_type, "value") else str(payload.media_type),
        job_description=payload.job_description,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Step 3: Persist the selected question snapshot into ai_prep_assessment_data.
    try:
        crud.save_assessment_data(
            db=db,
            assessment_id=db_assessment.id,
            questions=questions_list,
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist assessment questions into assessment_data: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist assessment questions",
        )

    return CreateAssessmentResponse(
        id=db_assessment.id,
        assessment_uuid=db_assessment.assessment_uuid,
        status=db_assessment.status,
        started_at=db_assessment.started_at,
        assessment_type=db_assessment.assessment_type,
        media_type=db_assessment.media_type,
        job_description=db_assessment.job_description,
        youtube_url=db_assessment.youtube_url,
        questions=questions_list,
    )


def candidate_list_assessments_logic(
    db: Session,
    current_user: AuthUserORM,
    limit: int = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Lists assessments belonging to the authenticated candidate dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first() if candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=a.report_record.overall_score if a.report_record else None,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def candidate_get_assessment_detail_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentDetailResponse:
    """Fetches assessment detail, telemetry, and evaluation scores from DB."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    cand = db.query(CandidateORM).filter(CandidateORM.id == assessment.candidate_id).first() if assessment.candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    data_dict = None
    questions_val = None
    if assessment.data_record:
        questions_val = assessment.data_record.questions
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
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        score=report_dict.get("overall_score") if report_dict else None,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        ip_address=assessment.ip_address,
        user_agent=assessment.user_agent,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        questions=questions_val,
        data=data_dict,
        report=report_dict,
    )


def candidate_get_assessment_data_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentDataResponse:
    """Fetches submitted telemetry and questions data for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if not assessment.data_record:
        raise HTTPException(status_code=404, detail="No telemetry or submitted data found for this assessment")
    return AssessmentDataResponse(
        id=assessment.data_record.id,
        assessment_id=assessment.data_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        questions=assessment.data_record.questions,
        transcript=assessment.data_record.transcript,
        audio_telemetry=assessment.data_record.audio_telemetry,
        video_telemetry=assessment.data_record.video_telemetry,
        created_at=assessment.data_record.created_at,
        updated_at=assessment.data_record.updated_at,
    )


def candidate_get_assessment_report_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentReportResponse:
    """Fetches generated evaluation report for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if not assessment.report_record:
        raise HTTPException(status_code=404, detail="Report not generated yet for this assessment")
    return AssessmentReportResponse(
        id=assessment.report_record.id,
        assessment_id=assessment.report_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        audio_evaluation=assessment.report_record.audio_evaluation,
        video_evaluation=assessment.report_record.video_evaluation,
        transcript_evaluation=assessment.report_record.transcript_evaluation,
        overall_score=assessment.report_record.overall_score,
        report_data=assessment.report_record.report_data,
        created_at=assessment.report_record.created_at,
        updated_at=assessment.report_record.updated_at,
    )


async def _run_evaluation_background(assessment_id: int, candidate_id: int) -> None:
    """Background task to run full LLM evaluation pipeline and persist report."""
    try:
        with SessionLocal() as db:
            assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
            if not assessment:
                logger.error("[LLMOrchestrator Worker] Assessment %s not found", str(assessment_id))
                return

            internal_id = assessment.id
            data_rec = crud.get_assessment_data_by_assessment_id(db, internal_id)
            transcript_data = (data_rec.transcript if data_rec else {}) or {}
            transcript_text = ""
            if isinstance(transcript_data, dict):
                transcript_text = (
                    transcript_data.get("full_text")
                    or transcript_data.get("transcript_text")
                    or transcript_data.get("text")
                    or transcript_data.get("transcript")
                    or ""
                )
                if not transcript_text and "segments" in transcript_data:
                    segments = transcript_data.get("segments") or []
                    if isinstance(segments, list):
                        seg_texts = [
                            str(seg.get("text") or "") if isinstance(seg, dict) else str(seg or "")
                            for seg in segments
                        ]
                        transcript_text = " ".join(t.strip() for t in seg_texts if t.strip())
            elif isinstance(transcript_data, str):
                transcript_text = transcript_data

            audio_telemetry = (data_rec.audio_telemetry if data_rec else {}) or {}
            video_telemetry = (data_rec.video_telemetry if data_rec else {}) or {}
            resume_json = crud.get_candidate_resume_json(db, candidate_id)

            llm_config = crud.get_candidate_llm_config(db, candidate_id)
            if not llm_config or not isinstance(llm_config, dict) or not llm_config.get("is_configured"):
                logger.error(
                    "[LLMOrchestrator Worker] Candidate %d has no valid LLM API key configured.",
                    candidate_id,
                )
                crud.update_assessment_status(db, internal_id, "FAILED")
                return

            assessment_type_str = (
                assessment.assessment_type.value
                if hasattr(assessment.assessment_type, "value")
                else str(assessment.assessment_type)
            )

            eval_result = await llm_orchestrator.run_evaluation(
                candidate_id=candidate_id,
                assessment_type=assessment_type_str,
                transcript_text=transcript_text,
                audio_telemetry=audio_telemetry,
                video_telemetry=video_telemetry,
                resume_json=resume_json,
                llm_config=llm_config,
            )

            crud.save_assessment_report(db, internal_id, eval_result)
            crud.update_assessment_status(db, internal_id, "COMPLETED")
            logger.info(
                "[LLMOrchestrator Worker] Assessment %d successfully evaluated and report saved.",
                internal_id,
            )
    except Exception as exc:
        logger.exception(
            "[LLMOrchestrator Worker] Assessment %s evaluation failed: %s",
            str(assessment_id),
            exc,
        )
        try:
            with SessionLocal() as err_db:
                crud.update_assessment_status(err_db, assessment_id, "FAILED")
        except Exception as status_err:
            logger.warning(
                "[LLMOrchestrator Worker] Failed to update assessment %s status to FAILED: %s",
                str(assessment_id),
                status_err,
            )


def candidate_submit_data_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: SubmitAssessmentDataRequest,
) -> SubmitAssessmentDataResponse:
    """Persists candidate telemetry, transcript, and answers into ai_prep_assessment_data via crud."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    crud.save_assessment_data(
        db=db,
        assessment_id=assessment.id,
        questions=payload.questions or [],
        transcript=payload.transcript or {},
        audio_telemetry=payload.audio_telemetry or {},
        video_telemetry=payload.video_telemetry or {},
    )
    return SubmitAssessmentDataResponse(message="Data saved successfully")


def candidate_update_media_url_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: UpdateMediaURLRequest,
) -> UpdateMediaURLResponse:
    """Updates YouTube/video playback URL on assessment in DB via crud."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    crud.update_assessment_media_url(db, assessment.id, payload.youtube_url)
    return UpdateMediaURLResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, youtube_url=payload.youtube_url)


def candidate_trigger_eval_post_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Transitions status to EVALUATING in DB and queues background LLM evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    crud.update_assessment_status(db, assessment.id, "EVALUATING")

    if background_tasks:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


def candidate_trigger_eval_put_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: Optional[SubmitAssessmentRequest] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Saves telemetry if provided, transitions status to EVALUATING, and queues background LLM evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if payload and (payload.transcript or payload.audio_telemetry or payload.video_telemetry):
        crud.save_assessment_data(
            db=db,
            assessment_id=assessment.id,
            questions=payload.questions or [],
            transcript=payload.transcript or {},
            audio_telemetry=payload.audio_telemetry or {},
            video_telemetry=payload.video_telemetry or {},
        )

    crud.update_assessment_status(db, assessment.id, "EVALUATING")

    if background_tasks:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


# ---------------------------------------------------------------------------
# 2. Employee & Admin Business Logic Functions
# ---------------------------------------------------------------------------

def employee_check_candidate_llm_keys_logic(db: Session, candidate_id: int) -> LLMKeyStatusResponse:
    """Employee inspects LLM key validity for any candidate dynamically from DB."""
    result = _check_candidate_llm_db(db, candidate_id)
    return LLMKeyStatusResponse(**result)


def employee_check_candidate_resume_logic(db: Session, candidate_id: int) -> ResumeStatusResponse:
    """Employee inspects resume setup for any candidate dynamically from DB."""
    result = _check_candidate_resume_db(db, candidate_id)
    return ResumeStatusResponse(**result)


def employee_check_candidate_pre_check_logic(db: Session, candidate_id: int) -> PreAssessmentCheckResponse:
    """Employee checks combined eligibility dynamically from DB."""
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


def employee_list_assessments_table_logic(
    db: Session,
    candidate_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Employee/Admin Grid: lists all candidate assessments from DB with filtering."""
    query = db.query(AiPrepAssessmentORM)
    if candidate_id:
        query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    if status_filter:
        query = query.filter(AiPrepAssessmentORM.status == status_filter)

    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    candidate_ids = {a.candidate_id for a in items if a.candidate_id is not None}
    cand_map = {}
    if candidate_ids:
        candidates = db.query(CandidateORM).filter(CandidateORM.id.in_(candidate_ids)).all()
        cand_map = {c.id: c for c in candidates}

    result_items = []
    for a in items:
        cand = cand_map.get(a.candidate_id)
        candidate_name = cand.full_name if (cand and cand.full_name) else None
        candidate_email = cand.email if (cand and cand.email) else None
        score = a.report_record.overall_score if a.report_record else None

        result_items.append(
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=score,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
        )

    return AssessmentListResponse(
        items=result_items,
        total=total,
    )


def employee_list_candidate_assessments_logic(db: Session, candidate_id: int) -> AssessmentListResponse:
    """Employee view of assessment history for any specific candidate ID."""
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first() if candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=a.report_record.overall_score if a.report_record else None,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def employee_get_assessment_detail_logic(db: Session, assessment_id: Union[int, str]) -> AssessmentDetailResponse:
    """Employee/Admin review of complete telemetry and scores for any assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    cand = db.query(CandidateORM).filter(CandidateORM.id == assessment.candidate_id).first() if assessment.candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

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
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        score=report_dict.get("overall_score") if report_dict else None,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        ip_address=assessment.ip_address,
        user_agent=assessment.user_agent,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


def employee_get_assessment_data_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentDataResponse:
    """Employee view of submitted telemetry and questions data."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.data_record:
        raise HTTPException(status_code=404, detail="No telemetry or submitted data found for this assessment")
    return AssessmentDataResponse(
        id=assessment.data_record.id,
        assessment_id=assessment.data_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        questions=assessment.data_record.questions,
        transcript=assessment.data_record.transcript,
        audio_telemetry=assessment.data_record.audio_telemetry,
        video_telemetry=assessment.data_record.video_telemetry,
        created_at=assessment.data_record.created_at,
        updated_at=assessment.data_record.updated_at,
    )


def employee_get_assessment_report_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentReportResponse:
    """Employee view of evaluation report."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.report_record:
        raise HTTPException(status_code=404, detail="Report not generated yet for this assessment")
    return AssessmentReportResponse(
        id=assessment.report_record.id,
        assessment_id=assessment.report_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        audio_evaluation=assessment.report_record.audio_evaluation,
        video_evaluation=assessment.report_record.video_evaluation,
        transcript_evaluation=assessment.report_record.transcript_evaluation,
        overall_score=assessment.report_record.overall_score,
        report_data=assessment.report_record.report_data,
        created_at=assessment.report_record.created_at,
        updated_at=assessment.report_record.updated_at,
    )



# ---------------------------------------------------------------------------
# 3. Media Pipeline, Chunks & Streaming Logic
# ---------------------------------------------------------------------------

async def upload_media_chunk_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    chunk_number: int,
    total_chunks: Optional[int],
    file: Union[UploadFile, bytes],
) -> ChunkUploadResponse:
    """Uploads sequential WebM media chunk to server storage directory using streaming with strict size limits."""
    if chunk_number < 1:
        raise HTTPException(status_code=400, detail="chunk_number must be >= 1")
    if total_chunks is not None and total_chunks < 1:
        raise HTTPException(status_code=400, detail="total_chunks must be >= 1")

    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id), "chunks")
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_number:04d}.webm")

    max_chunk_size_bytes = int(getattr(settings, "MAX_CHUNK_SIZE_MB", 50)) * 1024 * 1024
    total_written = 0

    try:
        os.makedirs(chunk_dir, exist_ok=True)
        with open(chunk_path, "wb") as f:
            if isinstance(file, bytes):
                total_written = len(file)
                if total_written > max_chunk_size_bytes:
                    f.close()
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                    )
                f.write(file)
            else:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_chunk_size_bytes:
                        f.close()
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                        )
                    f.write(chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write media chunk to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write media chunk to server storage",
        )

    uploaded = []
    if os.path.exists(chunk_dir):
        try:
            for fname in os.listdir(chunk_dir):
                if fname.startswith("chunk_") and fname.endswith(".webm"):
                    try:
                        num = int(fname.replace("chunk_", "").replace(".webm", ""))
                        uploaded.append(num)
                    except ValueError:
                        pass
        except (PermissionError, OSError):
            pass

    uploaded.sort()
    is_ready = bool(total_chunks and len(uploaded) >= total_chunks)

    return ChunkUploadResponse(
        chunk_number=chunk_number,
        status="uploaded",
        storage_path=chunk_path,
        bytes_written=total_written,
        total_uploaded=len(uploaded),
        total_chunks=total_chunks,
        is_ready_for_assembly=is_ready,
        message=f"Chunk {chunk_number} uploaded successfully",
    )


def get_chunk_upload_status_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    total_chunks: Optional[int] = None,
) -> ChunkStatusResponse:
    """Dynamically reads disk storage to check uploaded vs missing chunk numbers."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id), "chunks")
    uploaded = []
    if os.path.exists(chunk_dir):
        try:
            for fname in os.listdir(chunk_dir):
                if fname.startswith("chunk_") and fname.endswith(".webm"):
                    try:
                        num = int(fname.replace("chunk_", "").replace(".webm", ""))
                        uploaded.append(num)
                    except ValueError:
                        pass
        except (PermissionError, OSError):
            pass

    uploaded.sort()
    missing = [i for i in range(1, total_chunks + 1) if i not in uploaded] if total_chunks else []
    is_complete = bool(total_chunks and len(missing) == 0 and len(uploaded) >= total_chunks)

    return ChunkStatusResponse(
        assessment_id=assessment.id,
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


async def _process_youtube_upload_and_cleanup(
    assessment_id: int,
    media_path: str,
    media_type: str,
    candidate_id: Optional[int],
) -> Optional[str]:
    """
    Background helper to package media, upload to YouTube as Unlisted, persist URL to DB,
    and safely purge local scratch storage once persistence is confirmed.
    """
    youtube_url = None
    youtube_upload_file = media_path

    # 1. Conversion for YouTube if audio
    if media_type.upper() in {"AUDIO", "AUDIO_ONLY"}:
        try:
            from fapi.ai_prep.core.video_processor_engine import VideoProcessorEngine
            youtube_upload_file = await asyncio.to_thread(
                VideoProcessorEngine.convert_audio_for_youtube,
                media_path,
            )
        except Exception as conv_err:
            logger.warning("Audio-to-video conversion failed for assessment %s: %s", assessment_id, conv_err)
            return None

    # 2. Upload to YouTube
    try:
        from fapi.ai_prep.clients.youtube_client import youtube_client, YouTubeQuotaExceededError
        upload_res = await asyncio.to_thread(
            youtube_client.upload_unlisted_media,
            assessment_id=assessment_id,
            file_path=youtube_upload_file,
            media_type=media_type,
        )
        youtube_url = upload_res.get("youtube_url")
        logger.info("Assessment %s successfully uploaded to YouTube: %s", assessment_id, youtube_url)
    except Exception as yt_err:
        logger.warning("YouTube upload error for assessment %s: %s", assessment_id, yt_err)

    # 3. Persist youtube_url to DB
    youtube_persisted = False
    if youtube_url:
        try:
            with SessionLocal() as db:
                crud.update_assessment_media_url(db, assessment_id, youtube_url)
                youtube_persisted = True
                logger.info("Updated youtube_url in DB for assessment %s", assessment_id)
        except Exception as db_url_err:
            logger.error("DB update youtube_url error for assessment %s: %s", assessment_id, db_url_err)

    # 4. Storage Cleanup: ONLY once uploaded to YouTube and verified persisted in DB
    try:
        from fapi.ai_prep.config import settings
        should_cleanup = getattr(settings, "CLEANUP_STORAGE_AFTER_UPLOAD", True)
        if youtube_persisted and should_cleanup and candidate_id:
            assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
            if os.path.exists(assessment_dir):
                logger.info("Purging server storage for assessment %s at %s following verified YouTube DB update", assessment_id, assessment_dir)
                shutil.rmtree(assessment_dir, ignore_errors=True)
        elif not youtube_persisted:
            logger.info("Retaining local storage for assessment %s (YouTube URL not persisted in DB)", assessment_id)
    except Exception as clean_err:
        logger.warning("Storage cleanup note for assessment %s: %s", assessment_id, clean_err)

    return youtube_url


async def process_media_and_upload_pipeline(
    assessment_id: int,
    media_path: str,
    media_type: str = "VIDEO",
    candidate_id: Optional[int] = None,
):
    """
    Unified Background Pipeline:
    1. Runs Audio Engine on media_path (works with both audio and video containers).
    2. Saves real transcript + audio/video telemetry to database and updates status to EVALUATING.
    3. If media_type == "AUDIO", converts audio to video format for YouTube ingestion.
    4. Uploads to YouTube as Unlisted using youtube_client.
    5. Persists youtube_url into ai_prep_assessment table.
    6. Storage Cleanup: Once youtube_url is verified and persisted in DB, cleans up local storage.
    7. Triggers LLM evaluation orchestrator.
    If any critical failure occurs, transitions assessment status to 'FAILED'.
    """
    logger.info("Starting media processing & YouTube upload pipeline for assessment %s (type: %s)...", assessment_id, media_type)
    try:
        # 1. Run Audio Engine (STT + Acoustic DSP)
        from fapi.ai_prep.core.audio_engine import AudioMetricsEngine
        try:
            result = await asyncio.to_thread(AudioMetricsEngine.process_audio_file, media_path)
            spoken_content = result.get("spoken_content")
            audio_telemetry = result.get("audio_telemetry")
            if not spoken_content or not audio_telemetry:
                raise ValueError("Audio Engine returned incomplete transcription or telemetry")
        except Exception as err:
            logger.error("Audio Engine execution failed for assessment %s: %s", assessment_id, err, exc_info=True)
            with SessionLocal() as err_db:
                crud.update_assessment_status(err_db, assessment_id, "FAILED")
            return

        # 2. Save Telemetry into DB & Transition Status to EVALUATING
        with SessionLocal() as db:
            assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
            if assessment:
                existing_data = crud.get_assessment_data_by_assessment_id(db, assessment.id)
                existing_questions = existing_data.questions if existing_data and existing_data.questions else []
                crud.save_assessment_data(
                    db=db,
                    assessment_id=assessment.id,
                    questions=existing_questions,
                    transcript=spoken_content,
                    audio_telemetry=audio_telemetry,
                    video_telemetry={"is_video_mode": media_type.upper() == "VIDEO"},
                )
                crud.update_assessment_status(db, assessment.id, "EVALUATING")
                if not candidate_id:
                    candidate_id = assessment.candidate_id
            else:
                logger.error("Assessment %s not found during media processing pipeline", assessment_id)
                return

        # 3. Concurrent Execution: Trigger LLM Evaluation & YouTube Ingestion in Parallel
        eval_coro = assessment_orchestrator.run_full_evaluation(db=None, assessment_id=assessment_id)
        yt_coro = _process_youtube_upload_and_cleanup(
            assessment_id=assessment_id,
            media_path=media_path,
            media_type=media_type,
            candidate_id=candidate_id,
        )

        eval_result, yt_url = await asyncio.gather(eval_coro, yt_coro, return_exceptions=True)

        if isinstance(eval_result, Exception):
            logger.error("LLM evaluation encountered exception for assessment %s: %s", assessment_id, eval_result)
        if isinstance(yt_url, Exception):
            logger.warning("YouTube upload task encountered exception for assessment %s: %s", assessment_id, yt_url)

    except Exception as pipeline_err:
        logger.error(
            "Background media processing & evaluation pipeline failed for assessment %s: %s",
            assessment_id,
            pipeline_err,
            exc_info=True,
        )
        try:
            with SessionLocal() as fallback_db:
                crud.update_assessment_status(fallback_db, assessment_id, "FAILED")
                logger.info("Assessment %s status updated to FAILED", assessment_id)
        except Exception as status_err:
            logger.error("Failed to update assessment %s status to FAILED: %s", assessment_id, status_err)


# Alias for backward compatibility
process_audio_and_save_data = process_media_and_upload_pipeline


def assemble_media_chunks_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: Optional[AssembleMediaRequest] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> AssembleMediaResponse:
    """Validates sequence continuity, concatenates WebM chunks with streaming, and launches evaluation pipeline."""
    from fapi.ai_prep.core.video_processor_engine import validate_chunk_sequence

    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    video_path = os.path.join(assessment_dir, "assembled.webm")
    audio_path = os.path.join(assessment_dir, "audio.wav")
    chunk_dir = os.path.join(assessment_dir, "chunks")

    if not os.path.exists(chunk_dir):
        raise HTTPException(status_code=400, detail="No chunks directory found for this assessment")

    uploaded = []
    try:
        for fname in os.listdir(chunk_dir):
            if fname.startswith("chunk_") and fname.endswith(".webm"):
                try:
                    num = int(fname.replace("chunk_", "").replace(".webm", ""))
                    uploaded.append(num)
                except ValueError:
                    pass
    except (PermissionError, OSError) as err:
        logger.error("Could not read chunk directory %s: %s", chunk_dir, err)
        raise HTTPException(status_code=500, detail="Failed to access chunk storage on server")

    if not uploaded:
        raise HTTPException(status_code=400, detail="No media chunks found to assemble")

    uploaded.sort()
    total_expected = payload.total_chunks if (payload and payload.total_chunks) else len(uploaded)

    # Validate complete chunk sequence
    seq_val = validate_chunk_sequence(existing_chunks=uploaded, total_expected=total_expected)
    if not seq_val["is_valid"]:
        logger.warning("Chunk assembly rejected for assessment %s: %s", assessment.id, seq_val["error"])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incomplete chunk sequence. {seq_val['error']}",
        )

    # Assemble chunks in memory-efficient 1MB streaming blocks
    chunk_files = [os.path.join(chunk_dir, f"chunk_{i:04d}.webm") for i in range(1, total_expected + 1)]
    try:
        os.makedirs(assessment_dir, exist_ok=True)
        with open(video_path, "wb") as outfile:
            for cf in chunk_files:
                if not os.path.exists(cf):
                    raise FileNotFoundError(f"Chunk file missing: {cf}")
                with open(cf, "rb") as infile:
                    shutil.copyfileobj(infile, outfile, length=1024 * 1024)
    except Exception as asm_err:
        logger.error("Chunk assembly failed for assessment %s: %s", assessment.id, asm_err)
        raise HTTPException(status_code=500, detail=f"Failed to assemble media chunks: {asm_err}")

    target_media = video_path if (os.path.exists(video_path) and os.path.getsize(video_path) > 0) else audio_path

    # Queue the Media Processing & YouTube Upload Pipeline in background
    if background_tasks:
        background_tasks.add_task(
            process_media_and_upload_pipeline,
            assessment.id,
            target_media,
            assessment.media_type or "VIDEO",
            candidate_id,
        )

    return AssembleMediaResponse(
        assessment_id=assessment.id,
        status="ASSEMBLING",
        assembled_video_path=video_path,
        extracted_audio_path=audio_path,
        file_size_bytes=os.path.getsize(target_media) if os.path.exists(target_media) else 0,
        dispatched_tasks=["media_processing_pipeline"],
        media_path=video_path,
        audio_path=audio_path,
        message="Media chunks successfully validated, assembled, and queued for processing",
    )


async def upload_raw_media_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    media_type: str,
    file: UploadFile,
    background_tasks: Optional[BackgroundTasks] = None,
) -> LocalMediaUploadResponse:
    """Uploads single binary media file directly to disk storage using streaming with size limits."""
    normalized_media = (media_type or "").upper().strip()
    if normalized_media not in {"AUDIO", "VIDEO", "AUDIO_ONLY"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media_type '{media_type}'. Allowed values: AUDIO, VIDEO, AUDIO_ONLY",
        )

    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    safe_filename = os.path.basename(file.filename or "media.webm")
    dest_path = os.path.join(assessment_dir, f"raw_{safe_filename}")

    max_media_bytes = int(getattr(settings, "MAX_MEDIA_UPLOAD_MB", 500)) * 1024 * 1024
    total_written = 0

    try:
        os.makedirs(assessment_dir, exist_ok=True)
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_media_bytes:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Media file ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_MEDIA_UPLOAD_MB}MB)",
                    )
                await asyncio.to_thread(buffer.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write raw media file to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write media file to server storage",
        )

    if background_tasks:
        background_tasks.add_task(
            process_media_and_upload_pipeline,
            assessment.id,
            dest_path,
            normalized_media,
            candidate_id,
        )

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment.id,
        file_path=dest_path,
        media_type=normalized_media,
        message="Media uploaded and processing pipeline queued successfully",
    )


AUDIO_MIME_TO_EXTENSION: Dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/flac": "flac",
}


async def upload_assessment_audio_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    file: UploadFile,
    mime_type: Optional[str] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> AudioUploadResponse:
    """Uploads direct audio recording binary to server storage with extension detection and size limits."""
    from fapi.ai_prep.schemas import AudioUploadResponse
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    os.makedirs(assessment_dir, exist_ok=True)

    ext = None
    if mime_type and mime_type.lower() in AUDIO_MIME_TO_EXTENSION:
        ext = AUDIO_MIME_TO_EXTENSION[mime_type.lower()]
    elif file.filename and "." in file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext in {"wav", "webm", "mp3", "ogg", "m4a", "aac", "flac"}:
            ext = file_ext
    if not ext:
        ext = "webm" if (mime_type and "webm" in mime_type) else "wav"

    dest_path = os.path.join(assessment_dir, f"audio.{ext}")
    max_audio_bytes = int(getattr(settings, "MAX_AUDIO_UPLOAD_MB", 100)) * 1024 * 1024
    total_written = 0

    try:
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_audio_bytes:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Audio file ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_AUDIO_UPLOAD_MB}MB)",
                    )
                await asyncio.to_thread(buffer.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write audio recording file to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write audio file to server storage",
        )

    if background_tasks:
        background_tasks.add_task(
            process_media_and_upload_pipeline,
            assessment.id,
            dest_path,
            "AUDIO",
            candidate_id,
        )

    return AudioUploadResponse(
        success=True,
        assessment_id=assessment.id,
        message="Audio recording uploaded and processing pipeline queued successfully",
        size_bytes=total_written,
        mime_type=mime_type or f"audio/{ext}",
        file_path=dest_path,
    )


def _auto_assemble_chunks_if_present(assessment_dir: str) -> Optional[str]:
    """Auto-assembles sequential WebM chunks from chunks/ into assembled.webm atomically if top-level media is absent."""
    chunk_dir = os.path.join(assessment_dir, "chunks")
    assembled_path = os.path.join(assessment_dir, "assembled.webm")
    if os.path.exists(assembled_path) and os.path.getsize(assembled_path) > 0:
        return assembled_path

    if not os.path.exists(chunk_dir):
        return None
    try:
        chunk_files = sorted(
            [
                os.path.join(chunk_dir, f)
                for f in os.listdir(chunk_dir)
                if f.startswith("chunk_") and f.endswith(".webm")
            ]
        )
        if chunk_files:
            os.makedirs(assessment_dir, exist_ok=True)
            temp_assembled = os.path.join(assessment_dir, f"assembled_{uuid.uuid4().hex}.tmp")
            try:
                with open(temp_assembled, "wb") as outfile:
                    for cf in chunk_files:
                        with open(cf, "rb") as infile:
                            shutil.copyfileobj(infile, outfile, length=1024 * 1024)
                if os.path.exists(temp_assembled) and os.path.getsize(temp_assembled) > 0:
                    os.replace(temp_assembled, assembled_path)
                    logger.info("Atomically auto-assembled %d chunks into %s", len(chunk_files), assembled_path)
                    return assembled_path
            finally:
                if os.path.exists(temp_assembled):
                    try:
                        os.remove(temp_assembled)
                    except OSError:
                        pass
    except Exception as auto_err:
        logger.warning("Auto-assembling chunks failed: %s", auto_err)
    return None


def get_assessment_audio_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    range_header: Optional[str] = None,
) -> FileResponse:
    """Retrieves and streams stored audio recording binary from server storage with range seeking support."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    candidate_files = [
        os.path.join(assessment_dir, "audio.wav"),
        os.path.join(assessment_dir, "audio.webm"),
        os.path.join(assessment_dir, "recording.webm"),
        os.path.join(assessment_dir, "audio.mp3"),
        os.path.join(assessment_dir, "audio.ogg"),
        os.path.join(assessment_dir, "assembled.webm"),
    ]
    target_file = None
    for cf in candidate_files:
        if os.path.exists(cf) and os.path.getsize(cf) > 0:
            target_file = cf
            break

    if not target_file and os.path.exists(assessment_dir):
        for fname in os.listdir(assessment_dir):
            fpath = os.path.join(assessment_dir, fname)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0 and any(fname.endswith(s) for s in (".wav", ".webm", ".mp3", ".ogg")):
                target_file = fpath
                break

    if not target_file and os.path.exists(assessment_dir):
        target_file = _auto_assemble_chunks_if_present(assessment_dir)

    if not target_file or not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail="Assessment audio recording not found in server storage")

    mime_type = "audio/wav" if target_file.endswith(".wav") else ("audio/mp3" if target_file.endswith(".mp3") else "audio/webm")

    return FileResponse(
        path=target_file,
        media_type=mime_type,
        filename=os.path.basename(target_file),
        content_disposition_type="inline",
    )


def get_assessment_video_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    range_header: Optional[str] = None,
) -> FileResponse:
    """Retrieves and streams stored video recording from server storage with range seeking support."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    candidate_files = [
        os.path.join(assessment_dir, "assembled.webm"),
        os.path.join(assessment_dir, "video.mp4"),
        os.path.join(assessment_dir, "recording.webm"),
    ]
    target_file = None
    for cf in candidate_files:
        if os.path.exists(cf) and os.path.getsize(cf) > 0:
            target_file = cf
            break

    if not target_file and os.path.exists(assessment_dir):
        for fname in os.listdir(assessment_dir):
            fpath = os.path.join(assessment_dir, fname)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0 and (fname.endswith(".webm") or fname.endswith(".mp4") or fname.endswith(".mkv")):
                target_file = fpath
                break

    if not target_file and os.path.exists(assessment_dir):
        target_file = _auto_assemble_chunks_if_present(assessment_dir)

    if not target_file or not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail="Assessment video recording not found in server storage")

    mime_type = "video/webm" if target_file.endswith(".webm") else "video/mp4"

    return FileResponse(
        path=target_file,
        media_type=mime_type,
        filename=os.path.basename(target_file),
        content_disposition_type="inline",
    )


def get_media_storage_info_logic() -> StorageInfoResponse:
    """Returns real storage directory disk usage and assessment folder count across nested candidate partitions."""
    total, used, free = shutil.disk_usage(STORAGE_BASE_DIR if os.path.exists(STORAGE_BASE_DIR) else ".")
    assessment_count = 0
    if os.path.exists(STORAGE_BASE_DIR):
        try:
            for cand_dir in os.listdir(STORAGE_BASE_DIR):
                cand_path = os.path.join(STORAGE_BASE_DIR, cand_dir)
                if os.path.isdir(cand_path):
                    assessment_count += len([
                        item for item in os.listdir(cand_path)
                        if os.path.isdir(os.path.join(cand_path, item))
                    ])
        except (PermissionError, OSError) as err:
            logger.warning("Error calculating storage assessment count: %s", err)
    return StorageInfoResponse(
        storage_dir=os.path.abspath(STORAGE_BASE_DIR),
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        assessment_count=assessment_count,
    )


def get_assessment_processing_status_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> ProcessingStatusResponse:
    """Returns assessment pipeline processing progress snapshot dynamically from DB."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    status_str = assessment.status if assessment.status else "IN_PROGRESS"

    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 70.0, "COMPLETED": 100.0, "FAILED": 0.0}
    active_step = (
        "Evaluation Completed" if status_str == "COMPLETED"
        else ("Processing Failed" if status_str == "FAILED"
        else ("Evaluating Responses with LLM" if status_str == "EVALUATING"
        else "Processing Ingested Media"))
    )
    return ProcessingStatusResponse(
        assessment_id=assessment.id,
        status=status_str,
        progress_percentage=int(progress_map.get(status_str, 50.0)),
        active_step=active_step,
        step=active_step,
        progress_pct=progress_map.get(status_str, 50.0),
        youtube_url=assessment.youtube_url,
        message=f"Assessment is {status_str}",
    )


def _fetch_assessment_status_snapshot(assessment_id: int) -> Optional[Tuple[str, Optional[str]]]:
    """Helper to query assessment status in an isolated short-lived DB session without holding connection pool."""
    try:
        with SessionLocal() as poll_db:
            rec = crud.get_assessment_by_id_or_uuid(poll_db, assessment_id)
            if rec:
                return rec.status or "IN_PROGRESS", rec.youtube_url
    except Exception as exc:
        logger.debug("SSE status poll error for assessment %s: %s", assessment_id, exc)
    return None


def stream_assessment_processing_sse_logic(
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    db: Optional[Session] = None,
) -> StreamingResponse:
    """Real-time SSE event stream for live UI progress updates reflecting true DB state without holding DB connection pool."""
    if db is not None:
        assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        _resolve_candidate_id(db, current_user, assessment.candidate_id)
        internal_id = assessment.id
    else:
        with SessionLocal() as init_db:
            assessment = crud.get_assessment_by_id_or_uuid(init_db, assessment_id)
            if not assessment:
                raise HTTPException(status_code=404, detail="Assessment not found")
            _resolve_candidate_id(init_db, current_user, assessment.candidate_id)
            internal_id = assessment.id

    ping_interval = float(getattr(settings, "SSE_PING_INTERVAL_SECONDS", 2))

    async def event_generator():
        max_polls = int(getattr(settings, "SSE_MAX_POLLS", 60))  # Prevent infinite hanging connections
        polls = 0
        while polls < max_polls:
            polls += 1
            snapshot = await asyncio.to_thread(_fetch_assessment_status_snapshot, internal_id)
            if not snapshot:
                break
            curr_status, yt_url = snapshot
            progress_map = {"IN_PROGRESS": 35, "EVALUATING": 75, "COMPLETED": 100, "FAILED": 0}
            pct = progress_map.get(curr_status, 50)
            active_step = (
                "Report Generated" if curr_status == "COMPLETED"
                else ("Processing Failed" if curr_status == "FAILED"
                else ("LLM Evaluation in Progress" if curr_status == "EVALUATING"
                else "Media Processing & YouTube Ingestion"))
            )

            data = json.dumps({
                "assessment_id": internal_id,
                "status": curr_status,
                "step": active_step,
                "progress": pct,
                "youtube_url": yt_url,
            })
            yield f"data: {data}\n\n"

            if curr_status in {"COMPLETED", "FAILED"}:
                break

            await asyncio.sleep(min(ping_interval, 2.0))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 4. Question Bank & Catalog Logic
# ---------------------------------------------------------------------------

def list_available_assessment_types_logic() -> AssessmentTypeListResponse:
    """Fetches all active assessment types from the hardcoded catalog."""
    catalog = get_default_assessment_types()
    return AssessmentTypeListResponse(
        items=[AssessmentTypeResponse(**t) for t in catalog],
        total=len(catalog),
    )


def create_new_assessment_type_logic(type_in: AssessmentTypeCreate) -> AssessmentTypeResponse:
    """Admin endpoint to create a new assessment type in catalog."""
    catalog = get_default_assessment_types()
    new_item = type_in.dict()
    new_item["id"] = len(catalog) + 1
    return AssessmentTypeResponse(**new_item)


def list_questions_from_bank_logic(
    db: Session,
    category: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> QuestionListResponse:
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


def add_question_to_bank_logic(db: Session, payload: QuestionCreateRequest) -> QuestionResponse:
    """Adds a new question to the ai_prep_question_bank table in DB."""
    cat = payload.category.value if hasattr(payload.category, "value") else str(payload.category)
    sub_cat = payload.sub_category
    if cat != "TECHNICAL":
        sub_cat = None
    elif not sub_cat:
        sub_cat = "General"

    diff = payload.difficulty_level.value if hasattr(payload.difficulty_level, "value") else str(payload.difficulty_level)

    new_q = AiPrepQuestionORM(
        category=cat,
        sub_category=sub_cat,
        difficulty_level=diff,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return QuestionResponse.from_orm(new_q)


def update_question_in_bank_logic(
    db: Session,
    question_id: int,
    payload: QuestionUpdateRequest,
) -> QuestionResponse:
    """Updates fields on an existing question dynamically in DB."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")

    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None and hasattr(q_row, k):
            setattr(q_row, k, v.value if hasattr(v, "value") else v)

    # Enforce DDL chk_qb_subcategory constraint
    cat = q_row.category.value if hasattr(q_row.category, "value") else str(q_row.category)
    if cat != "TECHNICAL":
        q_row.sub_category = None
    elif not q_row.sub_category:
        q_row.sub_category = "General"

    q_row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(q_row)
    return QuestionResponse.from_orm(q_row)


def get_question_from_bank_logic(db: Session, question_id: int) -> QuestionResponse:
    """Fetches a specific question by ID from ai_prep_question_bank."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionResponse.from_orm(q_row)


def delete_question_from_bank_logic(db: Session, question_id: int) -> Dict[str, Any]:
    """Deactivates/deletes a question from ai_prep_question_bank."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")
    q_row.is_active = False
    q_row.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Question deactivated successfully", "id": question_id}
