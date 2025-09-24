from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.utils import session_utils
from fapi.db import schemas
from fapi.db.database import get_db

router = APIRouter()


@router.get("/session", response_model=list[schemas.SessionOut])
def read_sessions(
    search_title: str = None,
    db: Session = Depends(get_db)
):
    return session_utils.get_sessions(db, search_title=search_title)


@router.get("/session/{sessionid}", response_model=schemas.SessionOut)
def read_session(sessionid: int, db: Session = Depends(get_db)):
    session = session_utils.get_session(db, sessionid=sessionid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/session", response_model=schemas.SessionOut)
def create_new_session(session: schemas.SessionCreate, db: Session = Depends(get_db)):
    return session_utils.create_session(db, session=session)


@router.put("/session/{sessionid}", response_model=schemas.SessionOut)
def update_existing_session(sessionid: int, session: schemas.SessionUpdate, db: Session = Depends(get_db)):
    updated = session_utils.update_session(db, sessionid, session)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.delete("/session/{sessionid}", response_model=schemas.SessionOut)
def delete_existing_session(sessionid: int, db: Session = Depends(get_db)):
    deleted = session_utils.delete_session(db, sessionid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return deleted

# from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Security
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# from typing import List, Optional
# from sqlalchemy.orm import Session
# from fapi.db.database import SessionLocal, get_db
# from fapi.db.schemas import CourseContentResponse, BatchMetrics
# from sqlalchemy.future import select
# from fapi.db.models import CourseContent
# import anyio
# from fastapi.responses import JSONResponse
# from fapi.core.config import limiter
# import logging
# from fapi.utils.resources_utils import (
#     fetch_subject_batch_recording,
#     fetch_course_batches,
#     fetch_session_types_by_team,
#     fetch_sessions_by_type_orm,
#     fetch_keyword_presentation
# )
# from sqlalchemy.exc import SQLAlchemyError
# import traceback
# from fapi.utils.avatar_dashboard_utils import get_batch_metrics

# router = APIRouter()

# # Use HTTPBearer for Swagger authentication
# security = HTTPBearer()

# @router.get("/course-content", response_model=List[CourseContentResponse])
# async def get_course_content(
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     def _get_content():
#         result = db.execute(select(CourseContent))
#         return result.scalars().all()
#     return await anyio.to_thread.run_sync(_get_content)

# @router.get("/session-types")
# async def get_session_types(
#     team: str = "null",
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     try:
#         types = await anyio.to_thread.run_sync(fetch_session_types_by_team, db, team)
#         if not types:
#             raise HTTPException(status_code=404, detail="Types not found")
#         return {"types": types}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/sessions")
# async def get_sessions(
#     course_name: Optional[str] = None,
#     session_type: Optional[str] = None,
#     team: str = "admin",
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     try:
#         course_name_to_id = {
#             "QA": 1,
#             "UI": 2,
#             "ML": 3,
#         }
#         if course_name:
#             course_id = course_name_to_id.get(course_name.upper())
#             if not course_id:
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail=f"Invalid course name: {course_name}. Valid values are QA, UI, ML."
#                 )
#         else:
#             course_id = None
#         sessions = await anyio.to_thread.run_sync(fetch_sessions_by_type_orm, db, course_id, session_type, team)
#         if not sessions:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Sessions not found"
#             )
#         return {"sessions": sessions}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Internal error: {str(e)}"
#         )

# @router.get("/materials")
# @limiter.limit("15/minute")
# async def get_materials(
#     request: Request,
#     course: str = Query(..., description="Course name: QA, UI, or ML"),
#     search: str = Query(..., description="Type of material: Presentations, Cheatsheets, etc."),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     valid_courses = ["QA", "UI", "ML"]
#     if course.upper() not in valid_courses:
#         raise HTTPException(
#             status_code=400,
#             detail="Invalid course. Please select one of: QA, UI, ML"
#         )
#     data = fetch_keyword_presentation(search, course)
#     return JSONResponse(content=data)

# @router.get("/recording")
# def get_recordings(
#     course: str,
#     batchid: Optional[int] = None,
#     search: Optional[str] = None,
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     recordings = fetch_subject_batch_recording(course, db, batchid=batchid, search=search)
#     if not recordings.get("batch_recordings"):
#         msg = f"No recordings found for course '{course}'"
#         if batchid:
#             msg += f" and batch '{batchid}'"
#         if search:
#             msg += f" matching '{search}'"
#         raise HTTPException(status_code=404, detail=msg)
#     return recordings

# @router.get("/batches")
# def get_batches(
#     course: str = Query(..., description="Course alias (e.g., ML, UI, DS)"),
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     return fetch_course_batches(course, db)

# @router.get("/batches/metrics", response_model=BatchMetrics)
# def get_batch_metrics_endpoint(
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     return get_batch_metrics(db)
