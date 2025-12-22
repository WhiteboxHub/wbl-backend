from fastapi import Depends, HTTPException, Request, status
from fapi.utils.auth_dependencies import get_current_user

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
    "/api/metrics/all",
}

def _is_admin(user) -> bool:
    uname = (getattr(user, "uname", None) or getattr(user, "username", "") or "").lower()
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
    if method == "GET":
        for prefix in ALLOWED_GET_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this resource."
    )




