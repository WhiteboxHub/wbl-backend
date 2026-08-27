from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from fapi.ai_prep.models import (
    AiPrepAssessment, AiPrepAssessmentQuestion, AiPrepQuestionBank,
    AssessmentStatusEnum, AssessmentTypeEnum
)
from fapi.ai_prep.schemas import AssessmentCreate, AssessmentResponse, AssessmentQuestionSchema

# PRD Section 6.1 No-pause assessment types
NO_PAUSE_TYPES = {AssessmentTypeEnum.GENERAL_INTRO, AssessmentTypeEnum.JOB_DESCRIPTION_INTRO}

# Allowed State Machine Transitions (Contract 1 & PRD 8.1)
VALID_TRANSITIONS = {
    AssessmentStatusEnum.TESTING: {AssessmentStatusEnum.IN_PROGRESS, AssessmentStatusEnum.FAILED},
    AssessmentStatusEnum.IN_PROGRESS: {AssessmentStatusEnum.PAUSED, AssessmentStatusEnum.PROCESSING, AssessmentStatusEnum.FAILED},
    AssessmentStatusEnum.PAUSED: {AssessmentStatusEnum.IN_PROGRESS, AssessmentStatusEnum.PROCESSING, AssessmentStatusEnum.FAILED},
    AssessmentStatusEnum.PROCESSING: {AssessmentStatusEnum.COMPLETED, AssessmentStatusEnum.FAILED},
    AssessmentStatusEnum.COMPLETED: set(),  # Terminal state
    AssessmentStatusEnum.FAILED: {AssessmentStatusEnum.TESTING}  # Retry state
}


def validate_status_transition(current_status: AssessmentStatusEnum, new_status: AssessmentStatusEnum) -> None:
    """Enforces strict state machine rules. Raises 400 Bad Request on invalid transitions."""
    if current_status == new_status:
        return

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from '{current_status.value}' to '{new_status.value}'. Allowed transitions: {[s.value for s in allowed]}"
        )


def validate_pause_permission(assessment_type: AssessmentTypeEnum, new_status: AssessmentStatusEnum, is_paused: bool = False) -> None:
    """W2-BE1-02: Server-side no-pause enforcement. Returns 400 if pausing a no-pause session."""
    if (new_status == AssessmentStatusEnum.PAUSED or is_paused) and assessment_type in NO_PAUSE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pausing is disabled for '{assessment_type.value}' assessment sessions per PRD."
        )


def start_assessment_session(db: Session, candidate_id: int, payload: AssessmentCreate) -> AssessmentResponse:
    """Business logic for initializing a practice session and attaching bank questions."""
    assessment = AiPrepAssessment(
        candidate_id=candidate_id,
        candidate_resume_id=payload.candidate_resume_id,
        assessment_type=payload.assessment_type,
        assessment_mode=payload.assessment_mode,
        status=AssessmentStatusEnum.TESTING,
        job_description_text=payload.job_description_text,
        created_at=datetime.utcnow()
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    # Attach active questions
    questions = db.query(AiPrepQuestionBank).filter(
        AiPrepQuestionBank.is_active == True
    ).limit(5).all()

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
