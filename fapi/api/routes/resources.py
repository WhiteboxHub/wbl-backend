import logging
import traceback
from typing import List, Optional
from fapi.db.models import Session as SessionORM
from fapi.db.schemas import CourseContentResponse, BatchMetrics, PaginatedRecordingOut, RecordingOut, Recording  
from fapi.utils.resources_utils import fetch_kumar_recordings
# from fapi.utils.resources_utils import fetch_course_batches_with_kumar
from datetime import datetime
import anyio
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import CourseContentResponse, BatchMetrics
from fapi.db.models import CourseContent
from fapi.core.config import limiter
from fapi.utils.resources_utils import (
    fetch_subject_batch_recording,
    fetch_course_batches,
    fetch_session_types_by_team,
    fetch_sessions_by_type_orm,
    fetch_keyword_presentation,
)
from fapi.utils.avatar_dashboard_utils import get_batch_metrics

router = APIRouter()
security = HTTPBearer() 


@router.get("/course-content", response_model=List[CourseContentResponse])
async def get_course_content(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    def _get_content():
        result = db.execute(select(CourseContent))
        return result.scalars().all()

    return await anyio.to_thread.run_sync(_get_content)


@router.get("/session-types")
async def get_session_types(
    team: str = "null",
    credentials: HTTPAuthorizationCredentials = Security(security),  
    db: Session = Depends(get_db),
):
    token = credentials.credentials
  
    async def _get_types():
        return await anyio.to_thread.run_sync(fetch_session_types_by_team, db, team)

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
            fetch_sessions_by_type_orm, db, course_id, session_type, team
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


@router.get("/batches")
def get_batches(
    course: str = Query(..., description="Course alias (e.g., ML, UI, DS)"),
    db: Session = Depends(get_db)
):
    return fetch_course_batches(course, db)


@router.get("/batches/metrics", response_model=BatchMetrics)
def get_batch_metrics_endpoint(db: Session = Depends(get_db)):
    return get_batch_metrics(db)


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

@router.get("/batches")
def get_batches_with_kumar(
    course: str = Query(..., description="Course alias (e.g., ML, UI, DS)"),
    db: Session = Depends(get_db)
):
    return fetch_course_batches_with_kumar(course, db)
