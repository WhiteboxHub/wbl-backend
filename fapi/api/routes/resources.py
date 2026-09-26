import logging
import traceback
import os
import anyio
import httpx
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status,
    Response
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt as jose_jwt, JWTError
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import CourseContentResponse, BatchMetrics
from fapi.db.models import CourseContent, CourseContent as CourseContentORM, Batch as BatchORM, Recording as RecordingORM
from fapi.core.config import limiter, SECRET_KEY, ALGORITHM
from fapi.utils.resources_utils import (
    fetch_kumar_recordings,
    fetch_subject_batch_recording,
    fetch_course_batches,
    fetch_session_types_by_team,
    fetch_sessions_by_type_orm,
    fetch_keyword_presentation,
)
from fapi.utils.avatar_dashboard_utils import get_batch_metrics
from fapi.utils.auth_dependencies import get_current_user
from fapi.utils.table_fingerprint import generate_version_for_model

router = APIRouter()
security = HTTPBearer(auto_error=False)


def _is_request_authenticated(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> bool:
    """
    Return True only when the request carries a non-empty, valid, non-expired
    Bearer JWT signed with the project's SECRET_KEY.

    This intentionally mirrors the decode logic in
    fapi/utils/auth_dependencies.py:decode_token so that both paths use the
    same secret and algorithm without duplicating business logic.
    """
    if not credentials or not credentials.credentials:
        return False
    try:
        jose_jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return True
    except JWTError:
        # Expired, tampered, or otherwise invalid — treat as unauthenticated
        return False


def extract_role_and_team_from_token(token: str):
    """
    Extract role, team, and is_employee from JWT token.
    """
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        role = payload.get("role")
        team = payload.get("team")
        is_employee = payload.get("is_employee", False)
        return role, team, is_employee
    except Exception as e:
        logging.error(f"Error extracting info from token: {e}")
        return None, None, False


@router.head("/course-content")
def check_course_content_version(
    db: Session = Depends(get_db),
    # _user = Depends(get_current_user),
):
    return generate_version_for_model(db, CourseContentORM)

@router.get("/course-content", response_model=List[CourseContentResponse])
async def get_course_content(
    # _user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def _get_content():
        result = db.execute(select(CourseContent))
        return result.scalars().all()

    return await anyio.to_thread.run_sync(_get_content)


@router.get("/session-types")
async def get_session_types(
    team: str = "null",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = getattr(current_user, "role", None)
    user_team = getattr(current_user, "team", None)
    is_employee = getattr(current_user, "is_employee", False)
    
    async def _get_types():
        return await anyio.to_thread.run_sync(fetch_session_types_by_team, db, team, role, user_team, is_employee)

    try:
        types = await _get_types()
        if not types:
            raise HTTPException(status_code=404, detail="Types not found")
        return {"types": types}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_sessions(
    course_name: Optional[str] = None,
    session_type: Optional[str] = None,
    team: str = "admin",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = getattr(current_user, "role", None)
    user_team = getattr(current_user, "team", None)
    is_employee = getattr(current_user, "is_employee", False)
    
    async def _get_sessions():
        course_name_to_id = {"QA": 1, "UI": 2, "ML": 3}
        course_id = None
        if course_name:
            course_id = course_name_to_id.get(course_name.upper())
            if not course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid course name: {course_name}. Valid values are QA, UI, ML."
                )
        return await anyio.to_thread.run_sync(
            fetch_sessions_by_type_orm, db, course_id, session_type, team, role, user_team, is_employee
        )

    try:
        sessions = await _get_sessions()
        if not sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sessions not found"
            )
        return {"sessions": sessions}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()  
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/materials")
@limiter.limit("60/minute")
async def get_materials(
    request: Request,
    course: str = Query(..., description="Course name: QA, UI, or ML"),
    search: str = Query(..., description="Type of material: Presentations, Cheatsheets, etc."),
    enforce_access: Optional[HTTPAuthorizationCredentials] = Security(security),
):
    credentials = enforce_access
    valid_courses = ["QA", "UI", "ML"]
    if course.upper() not in valid_courses:
        raise HTTPException(
            status_code=400,
            detail="Invalid course. Please select one of: QA, UI, ML"
        )

    data = fetch_keyword_presentation(search, course)

    authenticated = _is_request_authenticated(credentials)
    if not authenticated:
        # Strip the protected material URL so unauthenticated callers cannot
        # obtain direct PDF/Drive links.  The listing (name, type, etc.) is
        # still returned so the UI can display the course catalogue.
        data = [{**item, "link": None} for item in (data or [])]

    return JSONResponse(content=data)

@router.get("/github-classroom-repos")
@limiter.limit("60/minute")
async def get_github_classroom_repos(
    request: Request,
    course: str = Query("ML", description="Course name: ML"),
    enforce_access: Optional[HTTPAuthorizationCredentials] = Security(security),
):
    credentials = enforce_access
    # 1. Fetch manually added Git materials from the DB
    def _fetch_manual_git():
        try:
            return fetch_keyword_presentation("Git Repo's", course)
        except Exception as e:
            logging.error(f"Error fetching manual Git repos: {e}")
            return []

    manual_repos = await anyio.to_thread.run_sync(_fetch_manual_git)

    # 2. Fetch dynamic repos from GitHub
    url = "https://api.github.com/search/repositories?q=classroom+org:WhiteboxHub&sort=updated&per_page=100"
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    formatted_repos = []
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            for i, repo in enumerate(items):
                formatted_repos.append({
                    "id": f"gh-{repo.get('id')}",
                    "name": repo.get("name"),
                    "link": repo.get("html_url"),
                    "description": repo.get("description", ""),
                    "type": "G",
                    "sortorder": 9999 + i
                })
        except Exception as e:
            logging.error(f"Error fetching GitHub repos: {str(e)}")
            # We don't raise an exception here so manual repos can still load
            pass

    # Combine manual repos (from DB) and dynamic repos (from GitHub API)
    combined = manual_repos + formatted_repos

    authenticated = _is_request_authenticated(credentials)
    if not authenticated:
        # Strip repo URLs for unauthenticated callers
        combined = [{**item, "link": None} for item in combined]

    return JSONResponse(content=combined)



@router.head("/batches")
def check_batches_version(
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    return generate_version_for_model(db, BatchORM)

@router.get("/batches")
def get_batches(
    course: str = Query(..., description="Course alias (e.g., ML, UI, DS)"),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    return fetch_course_batches(course, db)


@router.get("/batches/metrics", response_model=BatchMetrics)
def get_batch_metrics_endpoint(
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    return get_batch_metrics(db)


@router.head("/recording")
def check_recording_version(
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    return generate_version_for_model(db, RecordingORM)

@router.get("/recording")
def get_recordings(
    course: str,
    batchid: int,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    try:
        if batchid == 99999:
            return fetch_kumar_recordings(db, search=search)
        return fetch_subject_batch_recording(course, db, batchid=batchid, search=search)
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching recordings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")