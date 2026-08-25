from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from fapi.ai_prep.models import AiPrepAssessmentORM, AssessmentStatusEnum


def get_assessment(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentORM]:
    """Retrieve an assessment by id."""
    return db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()


def list_assessments_by_candidate(
    db: Session,
    candidate_id: int,
    skip: int = 0,
    limit: int = 50
) -> List[AiPrepAssessmentORM]:
    """List all assessments for a given candidate."""
    return db.query(AiPrepAssessmentORM).filter(
        AiPrepAssessmentORM.candidate_id == candidate_id
    ).order_by(AiPrepAssessmentORM.created_at.desc()).offset(skip).limit(limit).all()


def update_assessment_status(
    db: Session,
    assessment_id: int,
    status: AssessmentStatusEnum,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None
) -> Optional[AiPrepAssessmentORM]:
    """Update assessment status and timestamps."""
    assessment = get_assessment(db, assessment_id)
    if assessment:
        assessment.status = status
        if started_at:
            assessment.started_at = started_at
        if completed_at:
            assessment.completed_at = completed_at
        db.commit()
        db.refresh(assessment)
    return assessment
