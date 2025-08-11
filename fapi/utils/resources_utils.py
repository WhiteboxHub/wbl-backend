

# fapi/utils/resources_utils.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.future import select
from sqlalchemy import case, or_
from fapi.db.models import Session as SessionORM, CourseSubject , CourseMaterial, Recording, RecordingBatch, CourseSubject, Course, Subject, Batch
from typing import List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import case, or_
from fapi.db.database import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


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




async def fetch_subject_batch_recording(course: str, batchid: int, db: AsyncSession) -> Dict[str, Any]:
    try:
        # Step 1: Get Course
        course_stmt = select(Course).where(Course.alias == course)
        course_result =  db.execute(course_stmt)
        course_obj = course_result.scalar_one_or_none()
        if not course_obj:
            logger.warning(f"Course '{course}' not found.")
            raise HTTPException(status_code=404, detail="Course not found")

        # Step 2: Get all subjects for that course
        subject_stmt = (
            select(Subject)
            .join(CourseSubject)
            .where(CourseSubject.course_id == course_obj.id)
        )
        subject_result =  db.execute(subject_stmt)
        subjects = subject_result.scalars().all()
        if not subjects:
            logger.warning(f"No subjects found for course '{course}'.")
            raise HTTPException(status_code=404, detail="No subjects found for this course")

        subject_ids = [s.id for s in subjects]

        # Step 3: Get recordings for those subjects and batch
        rec_stmt = (
            select(Recording)
            .join(RecordingBatch, RecordingBatch.recording_id == Recording.id)
            .where(
                Recording.new_subject_id.in_(subject_ids),
                RecordingBatch.batch_id == batchid
            )
        )
        rec_result =  db.execute(rec_stmt)
        recordings = rec_result.scalars().all()
        if not recordings:
            logger.info(f"No recordings found for course '{course}' batch '{batchid}'.")
            return {"recordings": []}

        # Step 4: Format results
        recordings_data = [
            {
                "subject": next(s.name for s in subjects if s.id == rec.new_subject_id),
                "topic": rec.description,
                "date": rec.classdate,
                "recording_url": rec.link
            }
            for rec in recordings
        ]

        return {"recordings": recordings_data}

    except HTTPException:
        raise  # re-raise HTTPExceptions unchanged
    except Exception as e:
        logger.exception(f"Unexpected error while fetching recordings for course '{course}' batch '{batchid}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")


async def fetch_course_batches(course: str, db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        stmt = (
            select(Batch.batchname, Batch.batchid)
            .join(Course, Batch.courseid == Course.id)
            .where(Course.alias == course)
            .group_by(Batch.batchname, Batch.batchid)
            .order_by(Batch.batchname.desc())
        )
        result =  db.execute(stmt)
        rows = result.all()
        if not rows:
            logger.info(f"No batches found for course '{course}'.")
            return []
        return [{"batchname": row.batchname, "batchid": row.batchid} for row in rows]
    except Exception as e:
        logger.exception(f"Error fetching batches for course '{course}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")


def merge_batches(q1_response, q2_response):
    all_batches = q1_response + q2_response
    seen_batches = set()
    unique_batches = []

    for batch in all_batches:
        if batch['batchname'] not in seen_batches:
            seen_batches.add(batch['batchname'])
            unique_batches.append(batch)

    unique_batches.sort(key=lambda x: x['batchname'], reverse=True)
    return unique_batches

