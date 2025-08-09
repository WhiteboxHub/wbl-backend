
# fapi/utils/resources_utils.py

from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import case, or_
from fapi.db.models import Session as SessionORM, CourseSubject , CourseMaterial
from typing import List
from fastapi import HTTPException, status
from sqlalchemy import case, or_
from fapi.db.database import SessionLocal



def fetch_session_types_by_team(db: Session, team: str) -> List[str]:
    if team in ["admin", "instructor"]:
        result = db.execute(select(SessionORM.type).distinct().order_by(SessionORM.type))
    else:
        allowed_types = [
            "Resume Session", "Job Help", "Interview Prep",
            "Individual Mock", "Group Mock", "Misc"
        ]
        result = db.execute(
            select(SessionORM.type).distinct()
            .where(SessionORM.type.in_(allowed_types))
            .order_by(SessionORM.type)
        )
    return [row[0] for row in result.fetchall()]


def fetch_sessions_by_type_orm(db: Session, course_id: int, session_type: str, team: str):
    if not course_id or not session_type:
        return []

    allowed_types = [
        "Resume Session", "Job Help", "Interview Prep",
        "Individual Mock", "Group Mock", "Misc"
    ]

    if team not in ["admin", "instructor"] and session_type not in allowed_types:
        return []

    query = (
        select(SessionORM)
        .join(CourseSubject, SessionORM.subject_id == CourseSubject.subject_id)
        .where(
            SessionORM.subject_id != 0,
            CourseSubject.course_id == course_id,
            SessionORM.type == session_type,
            or_(
                CourseSubject.course_id != 3,
                SessionORM.sessiondate >= "2024-01-01"
            )
        )
        .order_by(SessionORM.sessiondate.desc())
    )

    result = db.execute(query)
    return result.scalars().all()


def fetch_keyword_presentation(search: str, course: str):
    """
    ORM version of fetching course materials based on type and course.
    Uses sync SessionLocal to match existing DB setup.
    """
    # Map readable names to DB type codes
    type_mapping = {
        "Presentations": "P",
        "Cheatsheets": "C",
        "Diagrams": "D",
        "Installations": "I",
        "Templates": "T",
        "Books": "B",
        "Softwares": "S",
        "Newsletters": "N"
    }
    type_code = type_mapping.get(search)
    if not type_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid search keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Newsletters"
        )

    # Map course alias to courseid
    courseid_mapping = {
        "QA": 1,
        "UI": 2,
        "ML": 3
    }
    selected_courseid = courseid_mapping.get(course.upper())

    # Priority ordering
    priority_order = case(
        (CourseMaterial.name == 'Software Architecture', 1),
        (CourseMaterial.name == 'SDLC', 2),
        (CourseMaterial.name == 'JIRA Agile', 3),
        (CourseMaterial.name == 'HTTP', 4),
        (CourseMaterial.name == 'Web Services', 5),
        (CourseMaterial.name == 'UNIX - Shell Scripting', 6),
        (CourseMaterial.name == 'MY SQL', 7),
        (CourseMaterial.name == 'Git', 8),
        (CourseMaterial.name == 'json', 9),
        else_=10
    )

    # Query using ORM
    with SessionLocal() as session:
        results = (
            session.query(CourseMaterial)
            .filter(
                CourseMaterial.type == type_code,
                or_(CourseMaterial.courseid == 0, CourseMaterial.courseid == selected_courseid)
            )
            .order_by(priority_order)
            .all()
        )

        # Convert ORM objects to dictionaries
        return [
            {column.name: getattr(row, column.name) for column in row.__table__.columns}
            for row in results
        ]