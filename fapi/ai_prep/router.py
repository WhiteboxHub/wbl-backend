import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepHardwareCheckORM,
    AiPrepQuestionBankORM,
    AssessmentStatusEnum,
    QuestionCategoryEnum,
    DifficultyLevelEnum,
    AiPrepConsentORM,
    AiPrepAssessmentORM as AiPrepAssessment,
    AiPrepAssessmentQuestionORM as AiPrepAssessmentQuestion,
    AiPrepConsentORM as AiPrepConsent,
    AiPrepQuestionBankORM as AiPrepQuestionBank,
    AiPrepDeletionRequestORM,
    DeletionRequestStatusEnum,
    RunTypeEnum,
    RunStatusEnum,
)
from fapi.ai_prep.schemas import (
    AssessmentCreate, AssessmentResponse, AssessmentQuestionSchema,
    AssessmentStatusUpdate, HardwareCheckCreate, HardwareCheckResponse,
    AssessmentListResponse, QuestionBankCreate, QuestionBankResponse,
    ConsentCreate, ConsentResponse, HardwareCheckRequest, ConsentRequest,
    DashboardResponse, ProcessingStatusResponse, ProcessingStepsStatus,
    DeletionRequestCreate, DeletionRequestResponse
)
from fapi.ai_prep.services.assessment_service import validate_status_transition, validate_pause_permission
from fapi.ai_prep.services.media_service import MediaService
from fapi.ai_prep.crud.questions import get_random_questions_for_candidate
from fapi.ai_prep.crud.analytics import get_candidate_dashboard_metrics
from fapi.ai_prep.crud.runs import get_runs_by_assessment_id
from fapi.ai_prep.api import media_router

router = APIRouter(
    prefix="/ai-prep",
    tags=["AI Prep"]
)


# ---------------------------------------------------------------------
# 1. POST /api/ai-prep/assessments (Create Assessment Session)
# ---------------------------------------------------------------------
@router.post("/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreate,
    candidate_id: int = Query(default=1, description="Candidate ID"),
    db: Session = Depends(get_db)
):
    """Create a new practice assessment session and select matching questions."""
    # Calculate dynamic attempt_number
    past_count = db.query(AiPrepAssessment).filter(
        AiPrepAssessment.candidate_id == candidate_id,
        AiPrepAssessment.assessment_type == payload.assessment_type
    ).count()
    attempt_number = past_count + 1

    assessment = AiPrepAssessment(
        candidate_id=candidate_id,
        candidate_resume_id=payload.candidate_resume_id,
        assessment_type=payload.assessment_type,
        assessment_mode=payload.assessment_mode,
        status=AssessmentStatusEnum.TESTING,
        attempt_number=attempt_number,
        job_description_text=payload.job_description_text,
        created_at=datetime.utcnow()
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    # Map assessment type to question category
    category_map = {
        "TECHNICAL": "TECHNICAL",
        "SYSTEM_DESIGN": "SYSTEM_DESIGN",
        "RECRUITER": "RECRUITER",
        "HIRING_MANAGER": "HIRING_MANAGER",
        "HR": "BEHAVIORAL",
        "GENERAL_INTRO": "GENERAL",
        "JOB_DESCRIPTION_INTRO": "GENERAL"
    }
    target_category = category_map.get(payload.assessment_type.name, "GENERAL")

    # Map assessment type to dynamic question counts limit
    limit_map = {
        "GENERAL_INTRO": 5,
        "JOB_DESCRIPTION_INTRO": 5,
        "RECRUITER": 6,
        "HIRING_MANAGER": 7,
        "TECHNICAL": 8,
        "SYSTEM_DESIGN": 4,
        "HR": 6
    }
    question_limit = limit_map.get(payload.assessment_type.name, 5)

    questions = get_random_questions_for_candidate(
        db=db,
        candidate_id=candidate_id,
        category=target_category,
        limit=question_limit
    )

    for idx, q in enumerate(questions, start=1):
        join_row = AiPrepAssessmentQuestion(
            assessment_id=assessment.id,
            question_id=q.id,
            order_index=idx
        )
        db.add(join_row)

    db.commit()
    db.refresh(assessment)

    question_schemas = [
        AssessmentQuestionSchema(
            id=aq.question.id,
            order_index=aq.order_index,
            question_text=aq.question.question_text,
            difficulty_level=aq.question.difficulty_level
        )
        for aq in assessment.questions if aq.question
    ]

    return AssessmentResponse(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
        assessment_type=assessment.assessment_type,
        assessment_mode=assessment.assessment_mode,
        status=assessment.status,
        attempt_number=assessment.attempt_number,
        questions=question_schemas,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at
    )


# ---------------------------------------------------------------------
# 2. GET /api/ai-prep/assessments/{assessment_id} (Fetch Assessment)
# ---------------------------------------------------------------------
@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """Fetch assessment session details by ID."""
    assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {assessment_id} not found."
        )

    question_schemas = [
        AssessmentQuestionSchema(
            id=aq.question.id,
            order_index=aq.order_index,
            question_text=aq.question.question_text,
            difficulty_level=aq.question.difficulty_level
        )
        for aq in assessment.questions if aq.question
    ]

    coaching_band = assessment.report.coaching_band if assessment.report else None

    return AssessmentResponse(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
        assessment_type=assessment.assessment_type,
        assessment_mode=assessment.assessment_mode,
        status=assessment.status,
        attempt_number=assessment.attempt_number,
        questions=question_schemas,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        coaching_band=coaching_band
    )


# ---------------------------------------------------------------------
# 3. PATCH /api/ai-prep/assessments/{id}/status (Update Status)
# ---------------------------------------------------------------------
@router.patch("/assessments/{assessment_id}/status", response_model=AssessmentResponse)
def update_assessment_status(
    assessment_id: int,
    payload: AssessmentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update assessment status (e.g. TESTING -> IN_PROGRESS -> COMPLETED)."""
    assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {assessment_id} not found."
        )

    # W2-BE1-01 Enforce strict status transition rules
    validate_status_transition(assessment.status, payload.status)

    # W2-BE1-02 Enforce server-side no-pause rule for GENERAL_INTRO and JOB_DESCRIPTION_INTRO
    validate_pause_permission(assessment.assessment_type, payload.status, payload.is_paused)

    assessment.status = payload.status
    if payload.status == AssessmentStatusEnum.IN_PROGRESS and not assessment.started_at:
        assessment.started_at = datetime.utcnow()
    elif payload.status == AssessmentStatusEnum.COMPLETED and not assessment.completed_at:
        assessment.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(assessment)
    return get_assessment(assessment_id=assessment_id, db=db)


# ---------------------------------------------------------------------
# 4. GET /api/ai-prep/assessments (List Candidate Sessions)
# ---------------------------------------------------------------------
@router.get("/assessments", response_model=AssessmentListResponse)
def list_assessments(
    candidate_id: int = Query(default=1, description="Candidate ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List paginated assessment sessions for a candidate."""
    query = db.query(AiPrepAssessment).filter(AiPrepAssessment.candidate_id == candidate_id)
    total = query.count()
    items_orm = query.order_by(AiPrepAssessment.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for a in items_orm:
        question_schemas = [
            AssessmentQuestionSchema(
                id=aq.question.id,
                order_index=aq.order_index,
                question_text=aq.question.question_text,
                difficulty_level=aq.question.difficulty_level
            )
            for aq in a.questions if aq.question
        ]
        coaching_band = a.report.coaching_band if a.report else None

        items.append(
            AssessmentResponse(
                id=a.id,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                assessment_mode=a.assessment_mode,
                status=a.status,
                attempt_number=a.attempt_number,
                questions=question_schemas,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
                coaching_band=coaching_band
            )
        )

    return AssessmentListResponse(items=items, total=total)


# ---------------------------------------------------------------------
# 5. POST /api/ai-prep/hardware-check (Record Hardware Check)
# ---------------------------------------------------------------------
@router.post("/hardware-check", response_model=HardwareCheckResponse, status_code=status.HTTP_201_CREATED)
def record_hardware_check(payload: HardwareCheckRequest, db: Session = Depends(get_db)):
    """Record initial hardware and permissions check for an assessment session."""
    hw_check = AiPrepHardwareCheckORM(
        assessment_id=payload.assessment_id,
        browser_info=payload.browser_info,
        os_info=payload.os_info,
        camera_permission=payload.camera_permission,
        mic_permission=payload.mic_permission,
        speaker_ok=payload.speaker_ok,
        bandwidth_kbps=payload.bandwidth_kbps,
        yolo_model_enabled=payload.yolo_model_enabled,
        tested_at=datetime.utcnow()
    )
    db.add(hw_check)
    db.commit()
    db.refresh(hw_check)
    return hw_check


# ---------------------------------------------------------------------
# 6. GET /api/ai-prep/hardware-check/{assessment_id} (Fetch Hardware Check)
# ---------------------------------------------------------------------
@router.get("/hardware-check/{assessment_id}", response_model=HardwareCheckResponse)
def get_hardware_check(assessment_id: int, db: Session = Depends(get_db)):
    """Fetch hardware check status for an assessment session."""
    hw_check = db.query(AiPrepHardwareCheckORM).filter(AiPrepHardwareCheckORM.assessment_id == assessment_id).first()
    if not hw_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hardware check record for assessment {assessment_id} not found."
        )
    return hw_check


# ---------------------------------------------------------------------
# 7. Question Bank Endpoints
# ---------------------------------------------------------------------
@router.post("/questions", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionBankCreate, db: Session = Depends(get_db)):
    """Add a question to the Question Bank."""
    q = AiPrepQuestionBankORM(
        category=payload.category,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        ideal_answer_rubric=payload.ideal_answer_rubric,
        relevant_skills_json=payload.relevant_skills_json,
        is_active=payload.is_active
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.get("/questions", response_model=List[QuestionBankResponse])
def list_questions(
    category: Optional[QuestionCategoryEnum] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List questions in Question Bank with optional category filter."""
    query = db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.is_active == True)
    if category:
        query = query.filter(AiPrepQuestionBankORM.category == category)
    return query.limit(limit).all()


# ---------------------------------------------------------------------
# 8. Consent Endpoints
# ---------------------------------------------------------------------
@router.post("/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
def record_consent(
    payload: ConsentRequest,
    candidate_id: int = Query(default=1, description="Candidate ID"),
    db: Session = Depends(get_db)
):
    """Record user privacy & data consent."""
    target_cid = payload.candidate_id if payload.candidate_id is not None else candidate_id
    consent = AiPrepConsentORM(
        candidate_id=target_cid,
        consent_type=payload.consent_type,
        consented=payload.consented,
        consented_at=datetime.utcnow()
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/consents/{candidate_id}", response_model=List[ConsentResponse])
def get_consents(candidate_id: int, db: Session = Depends(get_db)):
    """Fetch consent status records for a candidate."""
    return db.query(AiPrepConsent).filter(AiPrepConsent.candidate_id == candidate_id).all()


# ---------------------------------------------------------------------
# 9. GET /api/ai-prep/analytics/dashboard/{candidate_id} (Dashboard Data)
# ---------------------------------------------------------------------
@router.get("/analytics/dashboard/{candidate_id}", response_model=DashboardResponse)
def get_dashboard_metrics(candidate_id: int, db: Session = Depends(get_db)):
    """Fetch aggregated analytics data for the candidate's dashboard (Week 2)."""
    return get_candidate_dashboard_metrics(db=db, candidate_id=candidate_id)


# ---------------------------------------------------------------------
# 10. GET /api/ai-prep/assessments/{assessment_id}/processing-status (W2-BE1-04)
# ---------------------------------------------------------------------
@router.get("/assessments/{assessment_id}/processing-status", response_model=ProcessingStatusResponse)
def get_processing_status(assessment_id: int, db: Session = Depends(get_db)):
    """Fetch processing status and step progress for an assessment session (W2-BE1-04)."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {assessment_id} not found."
        )

    runs = get_runs_by_assessment_id(db, assessment_id)
    steps = ProcessingStepsStatus()
    for run in runs:
        if run.run_type == RunTypeEnum.STT: steps.stt = run.status
        elif run.run_type == RunTypeEnum.AUDIO: steps.audio = run.status
        elif run.run_type == RunTypeEnum.VISION: steps.vision = run.status
        elif run.run_type == RunTypeEnum.LLM: steps.llm = run.status
        elif run.run_type == RunTypeEnum.YOUTUBE_UPLOAD: steps.youtube_upload = run.status
        elif run.run_type == RunTypeEnum.FULL: steps.finalize = run.status

    if assessment.status == AssessmentStatusEnum.COMPLETED:
        steps.finalize = RunStatusEnum.COMPLETED

    return ProcessingStatusResponse(status=assessment.status, steps=steps)


# ---------------------------------------------------------------------
# 11. POST /api/ai-prep/deletion-request (W3-BE1-03 GDPR Deletion Endpoint)
# ---------------------------------------------------------------------
@router.post("/deletion-request", response_model=DeletionRequestResponse, status_code=status.HTTP_201_CREATED)
def create_deletion_request(
    payload: DeletionRequestCreate,
    candidate_id: int = Query(default=1, description="Candidate ID"),
    db: Session = Depends(get_db)
):
    """
    Submit a GDPR data deletion request (W3-BE1-03).
    Creates a deletion_request row and triggers candidate data purging task.
    """
    target_cid = payload.candidate_id if payload.candidate_id is not None else candidate_id
    del_req = AiPrepDeletionRequestORM(
        candidate_id=target_cid,
        status=DeletionRequestStatusEnum.PENDING,
        requested_at=datetime.utcnow()
    )
    db.add(del_req)
    db.commit()
    db.refresh(del_req)

    # Perform media & telemetry purging for candidate
    try:
        media_service = MediaService()
        result = media_service.delete_all_media(candidate_id=target_cid, db=db)
        del_req.status = DeletionRequestStatusEnum.COMPLETED
        del_req.completed_at = datetime.utcnow()
        del_req.deleted_bytes = result.get("local_files_deleted", 0) * 1024
        db.commit()
        db.refresh(del_req)
    except Exception as exc:
        logging.getLogger("wbl.ai_prep.router").error("GDPR deletion processing failed for candidate %d: %s", target_cid, exc)

    return del_req


# Include dynamic sub-routes (media uploads)
router.include_router(media_router)
