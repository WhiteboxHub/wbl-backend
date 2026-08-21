from typing import Optional, Any
import logging
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import CandidateORM
from fapi.ai_prep.models import AiPrepAssessmentORM, AiPrepAssessment

logger = logging.getLogger("wbl.ai_prep")


def get_candidate_id_for_user(user, db: Session) -> Optional[int]:
    """
    Resolves the integer candidate_id for the current authenticated user.
    Checks candidate_id attribute, queries by email matching uname, or matches candidate id.
    """
    if hasattr(user, "candidate_id") and getattr(user, "candidate_id"):
        return int(user.candidate_id)

    uname = getattr(user, "uname", None)
    if uname:
        candidate = db.query(CandidateORM).filter(CandidateORM.email == uname).first()
        if candidate:
            return candidate.id

    user_id = getattr(user, "id", None)
    if user_id:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == user_id).first()
        if candidate:
            return candidate.id

    return None


async def get_assessment_or_403(
    assessment_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AiPrepAssessmentORM:
    """
    FastAPI dependency to retrieve an assessment and verify candidate ownership.
    Returns 404 if not found, 403 if user is not authorized.
    """
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Check if user is admin/staff
    is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", "") == "admin"
    if is_admin:
        return assessment

    candidate_id = get_candidate_id_for_user(current_user, db)
    if candidate_id is None or assessment.candidate_id != candidate_id:
        logger.warning(
            "Access forbidden for assessment %s by user %s (resolved candidate_id=%s, owner=%s)",
            assessment_id, getattr(current_user, "uname", "unknown"), candidate_id, assessment.candidate_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this assessment"
        )

    return assessment
