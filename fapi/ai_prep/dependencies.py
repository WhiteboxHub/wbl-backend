"""Authentication, Authorization, and Session Dependencies for AI Prep Tool."""
import logging
from typing import Dict, Any, Optional, Tuple
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import AuthUserORM, CandidateORM
from fapi.ai_prep.crud import check_candidate_llm_key, check_candidate_resume

logger = logging.getLogger(__name__)


def resolve_candidate_for_user(db: Session, user: AuthUserORM) -> Optional[CandidateORM]:
    """Resolves CandidateORM record for the authenticated user by username/email or user ID."""
    uname = (getattr(user, "uname", "") or "").strip()
    
    # Match by candidate email == user uname
    candidate = db.query(CandidateORM).filter(CandidateORM.email == uname).first()
    if candidate:
        return candidate
        
    # Fallback to direct ID match if candidate ID aligns
    if getattr(user, "id", None):
        candidate = db.query(CandidateORM).filter(CandidateORM.id == user.id).first()
        if candidate:
            return candidate

    return None


def get_user_role_context(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Determines user's role (candidate, employee, admin) and links candidate record if applicable.
    """
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee"))
    is_admin = bool(getattr(current_user, "is_admin", False) or role == "admin" or uname == "admin")

    candidate_record = None
    candidate_id = None

    if not is_admin and not is_employee:
        candidate_record = resolve_candidate_for_user(db, current_user)
        if candidate_record:
            candidate_id = candidate_record.id
        else:
            candidate_id = current_user.id  # Fallback to user.id
    else:
        # For staff/admin, candidate_record is optional
        candidate_record = resolve_candidate_for_user(db, current_user)
        if candidate_record:
            candidate_id = candidate_record.id

    return {
        "user": current_user,
        "role": role,
        "is_employee": is_employee,
        "is_admin": is_admin,
        "candidate": candidate_record,
        "candidate_id": candidate_id,
    }


def require_candidate_or_employee(
    auth_ctx: Dict[str, Any] = Depends(get_user_role_context),
) -> Dict[str, Any]:
    """Requires an authenticated session of any valid role (candidate or employee/admin)."""
    return auth_ctx


def require_employee_or_admin(
    auth_ctx: Dict[str, Any] = Depends(get_user_role_context),
) -> Dict[str, Any]:
    """Enforces employee or admin authorization."""
    if not auth_ctx["is_employee"] and not auth_ctx["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee or Admin privileges required to access this resource",
        )
    return auth_ctx


def enforce_candidate_access(
    requested_candidate_id: Optional[int],
    auth_ctx: Dict[str, Any],
) -> int:
    """
    Guarantees authorization:
    - If user is candidate: MUST only access their own candidate ID.
    - If user is employee/admin: can access requested candidate ID (or defaults to own).
    """
    is_privileged = auth_ctx["is_employee"] or auth_ctx["is_admin"]
    self_id = auth_ctx.get("candidate_id")

    if not is_privileged:
        if requested_candidate_id is not None and requested_candidate_id != self_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidates are only authorized to access their own assessments and keys.",
            )
        if self_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to resolve candidate profile from session.",
            )
        return self_id

    # For employee / admin
    if requested_candidate_id is not None:
        return requested_candidate_id
    if self_id is not None:
        return self_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Candidate ID must be specified for employee query.",
    )


def verify_assessment_prerequisites(
    db: Session,
    candidate_id: int,
) -> Dict[str, Any]:
    """
    Validates LLM API key and Resume before starting an assessment session.
    Raises HTTPException(400) if prerequisites are not satisfied.
    """
    llm_status = check_candidate_llm_key(db, candidate_id)
    resume_status = check_candidate_resume(db, candidate_id)

    errors = []
    if not llm_status["is_configured"]:
        errors.append("Active LLM API Key is missing or invalid.")
    if not resume_status["has_resume"] and not resume_status["has_parsed_json"]:
        errors.append("Resume has not been uploaded or parsed.")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AssessmentPrerequisitesFailed",
                "message": "Cannot start assessment. Prerequisites not met.",
                "reasons": errors,
                "llm_check": llm_status,
                "resume_check": resume_status,
            },
        )

    return {
        "candidate_id": candidate_id,
        "llm_status": llm_status,
        "resume_status": resume_status,
    }
