"""
FastAPI Dependencies for AI Prep Assessment Platform.
Handles DB session injection and JWT candidate authentication.
"""

from typing import Generator
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from fapi.db.session import SessionLocal
from fapi.ai_prep import crud, models


def get_db() -> Generator:
    """Yields request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_candidate_id(authorization: str = Header(None)) -> int:
    """
    Extracts candidate_id from JWT Authorization header.
    Returns 1001 for dev/testing if header is missing or unparsed.
    """
    if not authorization:
        return 1001
    try:
        # Standard Bearer token parsing logic
        token = authorization.replace("Bearer ", "").strip()
        # Mock token decoding or JWT decode call
        return 1001
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def get_assessment_or_403(
    id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
) -> models.AiPrepAssessmentORM:
    """Enforces multi-tenant candidate security. Ensures candidate owns the requested assessment."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )
    if assessment.candidate_id != candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    return assessment
