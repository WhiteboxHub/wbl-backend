"""
FastAPI Dependencies for AIPrep
===============================
Provides DB session injection and candidate authentication.
"""
import os
import logging
from typing import Optional, Generator
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from jose import jwt, JWTError
from fapi.ai_prep import crud, models

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """Yields request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_candidate_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> int:
    """
    Extracts and validates candidate ID from Bearer JWT Authorization header.
    Raises HTTP 401 Unauthorized if token is missing, invalid, or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    secret_key = os.getenv("SECRET_KEY", "dev_secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        candidate_id = payload.get("sub") or payload.get("candidate_id") or payload.get("user_id")
        if candidate_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: Candidate ID not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return int(candidate_id)
    except (JWTError, ValueError) as exc:
        logger.warning("JWT validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_assessment_or_403(
    id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
) -> models.AiPrepAssessment:
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
