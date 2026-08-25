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
)
from fapi.ai_prep.schemas import (
    HardwareCheckRequest,
    HardwareCheckResponse,
    QuestionBankCreate,
    QuestionBankResponse,
    ConsentRequest,
    ConsentResponse,
)
from fapi.ai_prep.api.media_routes import router as media_router
from fapi.ai_prep.api.assessment_routes import router as assessment_router

logger = logging.getLogger("wbl.ai_prep.router")

router = APIRouter(prefix="/ai-prep", tags=["AIPrep"])

# Include sub-routers
router.include_router(media_router)
router.include_router(assessment_router)


@router.get("/health")
async def aiprep_health():
    """Health check endpoint for AIPrep module."""
    from fapi.ai_prep.services.storage_service import get_storage_service
    from fapi.ai_prep.services.youtube_service import get_youtube_service

    storage = get_storage_service()
    youtube = get_youtube_service()

    return {
        "status": "ok",
        "storage_backend": storage.__class__.__name__,
        "youtube_configured": youtube.is_configured(),
        "module": "ai_prep"
    }


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
    return db.query(AiPrepConsentORM).filter(AiPrepConsentORM.candidate_id == candidate_id).all()
