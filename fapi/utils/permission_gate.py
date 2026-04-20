from fastapi import Depends, HTTPException, Request, status
from fapi.utils.auth_dependencies import get_current_user
from fapi.utils import onboarding_utils
from fapi.db.database import SessionLocal

ALLOWED_GET_PREFIXES = {
    "/api/course-content",
    "/api/session-types",
    "/api/sessions",
    "/api/materials",
    "/api/recordings",
    "/api/batches",
    "/api/referrals",
    "/api/candidate/placements",
    "/api/user_dashboard",
    "/api/candidates/search-names",
    "/api/interviews",
    "/api/session",
    "/api/recording",
    "/api/materials",
    "/api/course-contents",
    "/api/referrals",
    "/api/positions",
    "/api/weekly-workflow/eligible-candidates",
    "/api/automation-workflow",
}

ALLOWED_POST_PREFIXES = {
    "/api/candidates/track-clicks-batch",
    "/api/onboarding",
}

def _is_admin(user) -> bool:
    raw_uname = getattr(user, "uname", None)
    raw_username = getattr(user, "username", "")
    uname = raw_uname if isinstance(raw_uname, str) and raw_uname else raw_username
    if not isinstance(uname, str):
        uname = ""
    uname = uname.lower()
    return (
        getattr(user, "role", None) == "admin"
        or getattr(user, "is_admin", False)
        or uname == "admin"
    )

def enforce_access(request: Request, current_user=Depends(get_current_user)):
    method = request.method.upper()
    path = request.url.path.rstrip("/")
    if _is_admin(current_user):
        return current_user

    if path == "/api/onboarding" or path.startswith("/api/onboarding/"):
        return current_user

    user_email = getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    with SessionLocal() as db:
        state = onboarding_utils.get_or_create_onboarding_state(db, user_email, authuser_id)
        status_payload = onboarding_utils.onboarding_status_payload(state)
        if not status_payload.get("onboarding_completed", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Complete onboarding before accessing dashboard features.",
                    "onboarding": status_payload,
                },
            )

    # Authenticated learners/employees may use CoderPad (snippets, run, assignments).
    if path == "/api/coderpad" or path.startswith("/api/coderpad/"):
        return current_user

    if method == "GET":
        for prefix in ALLOWED_GET_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return current_user
    
    if method == "POST":
        for prefix in ALLOWED_POST_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this resource."
    )


