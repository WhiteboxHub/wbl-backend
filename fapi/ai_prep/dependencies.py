from typing import Any
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.ai_prep.models import AiPrepAssessment
from fapi.utils.auth_dependencies import get_current_user


def get_assessment_or_403(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
) -> AiPrepAssessment:
    """
    FastAPI Dependency (W1-BE1-05) to fetch an assessment session and enforce JWT ownership.
    - Returns 404 Not Found if assessment session does not exist.
    - Returns 403 Forbidden if candidate tries to access another candidate's practice session.
    """
    assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {assessment_id} not found."
        )

    # Validate candidate ownership against authenticated JWT user ID
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    if user_id and assessment.candidate_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Candidate cannot access another candidate's assessment session."
        )


    return assessment
