# # fapi/api/routes/resources.py

# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession
# from fapi.db.database import get_db
# from fapi.utils.resources_utils import fetch_session_types_by_team, fetch_sessions_by_type_orm
# from fapi.auth import get_current_user
# from typing import Optional

# router = APIRouter()


# @router.get("/session-types")
# async def get_session_types(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
#     try:
#         team = current_user.get("team", "null")
#         types = await fetch_session_types_by_team(db, team)
#         if not types:
#             raise HTTPException(status_code=404, detail="Types not found")
#         return {"types": types}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/sessions")
# async def get_sessions(course_name: Optional[str] = None, session_type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
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

#         # You can also extract the actual user from token
#         team = "admin"  # Or extract from current_user if needed

#         sessions = await fetch_sessions_by_type_orm(db, course_id, session_type, team)
#         if not sessions:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessions not found")
#         return {"sessions": sessions}
#     except Exception as e:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# fapi/api/routes/resources.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fapi.db.database import get_db
from fapi.utils.resources_utils import fetch_session_types_by_team, fetch_sessions_by_type_orm
from typing import Optional

router = APIRouter()


@router.get("/session-types")
async def get_session_types(team: str = "null", db: AsyncSession = Depends(get_db)):
    try:
        types = await fetch_session_types_by_team(db, team)
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
    db: AsyncSession = Depends(get_db)
):
    try:
        course_name_to_id = {
            "QA": 1,
            "UI": 2,
            "ML": 3,
        }

        if course_name:
            course_id = course_name_to_id.get(course_name.upper())
            if not course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid course name: {course_name}. Valid values are QA, UI, ML."
                )
        else:
            course_id = None

        sessions = await fetch_sessions_by_type_orm(db, course_id, session_type, team)
        if not sessions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessions not found")
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    

