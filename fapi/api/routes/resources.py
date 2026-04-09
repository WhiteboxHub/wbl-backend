import logging
import traceback
import jwt
import os
import asyncio
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
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import CourseContentResponse, BatchMetrics
from fapi.db.models import CourseContent, CourseContent as CourseContentORM, Batch as BatchORM, Recording as RecordingORM
from fapi.core.config import SECRET_KEY
from fapi.core.config import limiter
from fastapi import Request
from fapi.utils.resources_utils import (
    fetch_kumar_recordings,
    fetch_subject_batch_recording,
    fetch_course_batches,
    fetch_session_types_by_team,
    fetch_sessions_by_type_orm,
    fetch_keyword_presentation,
)
from fapi.utils.avatar_dashboard_utils import get_batch_metrics
from fapi.utils.table_fingerprint import generate_version_for_model

router = APIRouter()
security = HTTPBearer()

def extract_role_and_team_from_token(token: str):
    """
    Extract role and team from JWT token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        role = payload.get("role")
        team = payload.get("team")
        return role, team
    except Exception as e:
        logging.error(f"Error extracting role and team from token: {e}")
        return None, None


@router.head("/course-content")
def check_course_content_version(db: Session = Depends(get_db)):
    return generate_version_for_model(db, CourseContentORM)

@router.get("/course-content", response_model=List[CourseContentResponse])
async def get_course_content(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    def _get_content():
        result = db.execute(select(CourseContent))
        return result.scalars().all()

    return await asyncio.to_thread(_get_content)


@router.get("/session-types")
async def get_session_types(
    team: str = "null",
    credentials: HTTPAuthorizationCredentials = Security(security),  
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    
    # Extract role and team from token
    role, user_team = extract_role_and_team_from_token(token)
    
    async def _get_types():
        return await asyncio.to_thread(fetch_session_types_by_team, db, team, role, user_team)

    try:
        types = await _get_types()
        if not types:
            raise HTTPException(status_code=404, detail="Types not found")
        return {"types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_sessions(
    course_name: Optional[str] = None,
    session_type: Optional[str] = None,
    team: str = "admin",
    credentials: HTTPAuthorizationCredentials = Security(security),  
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    
    # Extract role and team from token
    role, user_team = extract_role_and_team_from_token(token)
    
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
        return await asyncio.to_thread(
            fetch_sessions_by_type_orm, db, course_id, session_type, team, role, user_team
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
@limiter.limit("15/minute")
async def get_materials(
    request: Request, 
    course: str = Query(..., description="Course name: QA, UI, or ML"),
    search: str = Query(..., description="Type of material: Presentations, Cheatsheets, etc.")
):
    valid_courses = ["QA", "UI", "ML"]
    if course.upper() not in valid_courses:
        raise HTTPException(
            status_code=400,
            detail="Invalid course. Please select one of: QA, UI, ML"
        )

    data = fetch_keyword_presentation(search, course)
    return JSONResponse(content=data)


@router.head("/batches")
def check_batches_version(db: Session = Depends(get_db)):
    return generate_version_for_model(db, BatchORM)

@router.get("/batches")
def get_batches(
    course: str = Query(..., description="Course alias (e.g., ML, UI, DS)"),
    db: Session = Depends(get_db)
):
    return fetch_course_batches(course, db)


@router.get("/batches/metrics", response_model=BatchMetrics)
def get_batch_metrics_endpoint(db: Session = Depends(get_db)):
    return get_batch_metrics(db)


@router.head("/recording")
def check_recording_version(db: Session = Depends(get_db)):
    return generate_version_for_model(db, RecordingORM)

@router.get("/recording")
def get_recordings(
    course: str,
    batchid: int,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
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
