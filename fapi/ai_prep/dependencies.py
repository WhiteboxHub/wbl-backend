"""
FastAPI Dependencies for AIPrep
===============================
Provides strict production-grade candidate authentication:
- Extracts and validates candidate ID strictly from Bearer JWT Authorization token.
- Zero test backdoors or fallback headers.
"""
import os
import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from jose import jwt, JWTError

logger = logging.getLogger(__name__)


def get_current_candidate_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> int:
    """
    Extracts and validates candidate ID strictly from Bearer JWT Authorization header.
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


