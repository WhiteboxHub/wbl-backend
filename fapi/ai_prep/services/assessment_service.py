from datetime import datetime
from sqlalchemy.orm import Session

from fapi.ai_prep.models import (
    AiPrepAssessment, AiPrepAssessmentQuestion, AiPrepQuestionBank,
    AssessmentStatusEnum
)
from fapi.ai_prep.schemas import AssessmentCreate, AssessmentResponse, AssessmentQuestionSchema

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
