from fastapi import Depends, HTTPException, Request, status
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.database import SessionLocal
from fapi.utils.onboarding_utils import get_onboarding_snapshot

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

    role = getattr(current_user, "role", None)
    email = getattr(current_user, "uname", None) or getattr(current_user, "username", None)
    if role == "candidate" and isinstance(email, str) and email:
        onboarding_allowed_prefixes = {
            "/api/approval/onboarding",
            "/api/login",
            "/api/google_login",
            "/api/verify_google_token",
        }
        with SessionLocal() as db:
            onboarding = get_onboarding_snapshot(db, email)
        if onboarding.get("access_restricted"):
            if not any(path == p or path.startswith(p + "/") for p in onboarding_allowed_prefixes):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "message": "Complete onboarding before accessing dashboard features.",
                        "next_step": onboarding.get("next_step"),
                        "onboarding": onboarding,
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


