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
    AiPrepQuestionBankORM as AiPrepQuestionBank
)
from fapi.ai_prep.schemas import (
    AssessmentCreate, AssessmentResponse, AssessmentQuestionSchema,
    AssessmentStatusUpdate, HardwareCheckCreate, HardwareCheckResponse,
    AssessmentListResponse, QuestionBankCreate, QuestionBankResponse,
    ConsentCreate, ConsentResponse, HardwareCheckRequest, ConsentRequest
)

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

    from fapi.ai_prep.crud.questions import get_random_questions_for_candidate
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
# 2. GET /api/ai-prep/assessments/{id} (Get Session Details)
# ---------------------------------------------------------------------
@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """Fetch details of a specific practice assessment session."""
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
# Hardware Check Endpoints
# ---------------------------------------------------------------------
@router.post("/hardware-check", response_model=HardwareCheckResponse, status_code=status.HTTP_201_CREATED)
def record_hardware_check(payload: HardwareCheckRequest, db: Session = Depends(get_db)):
    """Record candidate camera, microphone, speaker, and bandwidth test results."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == payload.assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {payload.assessment_id} not found."
        )

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

    return HardwareCheckResponse(
        id=hw_check.id,
        assessment_id=hw_check.assessment_id,
        browser_info=hw_check.browser_info,
        os_info=hw_check.os_info,
        camera_permission=hw_check.camera_permission,
        mic_permission=hw_check.mic_permission,
        speaker_ok=hw_check.speaker_ok,
        bandwidth_kbps=hw_check.bandwidth_kbps,
        yolo_model_enabled=hw_check.yolo_model_enabled,
        tested_at=hw_check.tested_at
    )


@router.get("/hardware-check/{assessment_id}", response_model=HardwareCheckResponse)
def get_hardware_check(assessment_id: int, db: Session = Depends(get_db)):
    """Fetch the latest hardware check for an assessment session."""
    hw_check = db.query(AiPrepHardwareCheckORM).filter(
        AiPrepHardwareCheckORM.assessment_id == assessment_id
    ).order_by(AiPrepHardwareCheckORM.tested_at.desc()).first()

    if not hw_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hardware check found for assessment session {assessment_id}."
        )

    return HardwareCheckResponse(
        id=hw_check.id,
        assessment_id=hw_check.assessment_id,
        browser_info=hw_check.browser_info,
        os_info=hw_check.os_info,
        camera_permission=hw_check.camera_permission,
        mic_permission=hw_check.mic_permission,
        speaker_ok=hw_check.speaker_ok,
        bandwidth_kbps=hw_check.bandwidth_kbps,
        yolo_model_enabled=hw_check.yolo_model_enabled,
        tested_at=hw_check.tested_at
    )


# ---------------------------------------------------------------------
# Question Bank Endpoints
# ---------------------------------------------------------------------
@router.post("/questions", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionBankCreate, db: Session = Depends(get_db)):
    """Create a new question in Question Bank."""
    q = AiPrepQuestionBankORM(
        category=payload.category,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        ideal_answer_rubric=payload.ideal_answer_rubric,
        relevant_skills_json=payload.relevant_skills_json,
        is_active=True,
        created_at=datetime.utcnow()
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
# Consent Endpoints
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
# 11. GET /api/ai-prep/analytics/dashboard/{candidate_id} (Dashboard Data)
# ---------------------------------------------------------------------
from fapi.ai_prep.schemas import DashboardResponse
from fapi.ai_prep.crud.analytics import get_candidate_dashboard_metrics

@router.get("/analytics/dashboard/{candidate_id}", response_model=DashboardResponse)
def get_dashboard_metrics(candidate_id: int, db: Session = Depends(get_db)):
    """Fetch aggregated analytics data for the candidate's dashboard (Week 2)."""
    return get_candidate_dashboard_metrics(db=db, candidate_id=candidate_id)


# Include dynamic sub-routes (media uploads, processing statuses)
from fapi.ai_prep.api import media_router, assessment_router
router.include_router(media_router)
router.include_router(assessment_router)
