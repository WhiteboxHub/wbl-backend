# fapi/utils/resources_util.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from fapi.db.models import Session, CourseSubject, Course
from typing import List


async def fetch_session_types_by_team(db: AsyncSession, team: str) -> List[str]:
    if team in ["admin", "instructor"]:
        result = await db.execute(select(Session.type).distinct().order_by(Session.type))
    else:
        allowed_types = [
            "Resume Session", "Job Help", "Interview Prep", 
            "Individual Mock", "Group Mock", "Misc"
        ]
        result = await db.execute(
            select(Session.type).distinct()
            .where(Session.type.in_(allowed_types))
            .order_by(Session.type)
        )
    return [row[0] for row in result.fetchall()]


async def fetch_sessions_by_type_orm(db: AsyncSession, course_id: int, session_type: str, team: str):
    if not course_id or not session_type:
        return []

    allowed_types = [
        "Resume Session", "Job Help", "Interview Prep", 
        "Individual Mock", "Group Mock", "Misc"
    ]

    if team not in ["admin", "instructor"] and session_type not in allowed_types:
        return []

    query = (
        select(Session)
        .join(CourseSubject, Session.subject_id == CourseSubject.subject_id)
        .where(
            Session.subject_id != 0,
            CourseSubject.course_id == course_id,
            Session.type == session_type,
            or_(
                CourseSubject.course_id != 3,
                Session.sessiondate >= "2024-01-01"
            )
        )
        .order_by(Session.sessiondate.desc())
    )

    result = await db.execute(query)
    return result.scalars().all()
