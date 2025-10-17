from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy import case, or_, literal, desc,text,extract
from fapi.db.models import (Session as SessionORM, CourseSubject , CourseMaterial, 
                            Recording, RecordingBatch, CourseSubject,
                            Course, Subject, Batch, CourseContent)
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from fapi.db.database import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy import literal
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func


logger = logging.getLogger(__name__)



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

    courseid_mapping = {
        "QA": 1,
        "UI": 2,
        "ML": 3
    }
    selected_courseid = courseid_mapping.get(course.upper())

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

def fetch_subject_batch_recording(course: str, batchid: int, db: Session):
    course_obj = db.query(Course).filter(Course.alias == course).first()
    if not course_obj:
        return {"message": "Course not found"}

    recordings = (
        db.query(Recording)
        .join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
        .join(Batch, RecordingBatch.batch_id == Batch.batchid)
        .filter(Batch.batchid == batchid)
        .all()
    )
    return {"recordings": recordings}

# def fetch_sessions_by_type_orm(db: Session, course_id: int, session_type: str, team: str):
#     if not course_id or not session_type:
#         return []

#     allowed_types = [
#         "Resume Session", "Job Help", "Interview Prep",
#         "Individual Mock", "Group Mock", "Misc","Internal Sessions"
#     ]

#     if team not in ["admin", "instructor"] and session_type not in allowed_types:
#         return []

#     query = (
#         select(SessionORM)
#         .join(CourseSubject, SessionORM.subject_id == CourseSubject.subject_id)
#         .where(
#             SessionORM.subject_id != 0,
#             CourseSubject.course_id == course_id,
#             SessionORM.type == session_type,
#             or_(
#                 CourseSubject.course_id != 3,
#                 SessionORM.sessiondate >= "2024-01-01"
#             )
#         )
#         .order_by(SessionORM.sessiondate.desc())
#     )

#     result = db.execute(query)
#     return result.scalars().all()


def fetch_sessions_by_type_orm(db: Session, course_id: int, session_type: str, team: str):
    if not course_id or not session_type:
        return []

    allowed_types = [
        "Resume Session", "Job Help", "Interview Prep",
        "Individual Mock", "Group Mock", "Misc", "Internal Sessions"
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



# def fetch_session_types_by_team(db: Session, team: str) -> List[str]:
#     if team in ["admin", "instructor"]:
#         result = db.execute(select(SessionORM.type).distinct().order_by(SessionORM.type))
#     else:
#         allowed_types = [
#             "Resume Session", "Job Help", "Interview Prep",
#             "Individual Mock", "Group Mock", "Misc","Internal Sessions"
#         ]
#         result = db.execute(
#             select(SessionORM.type).distinct()
#             .where(SessionORM.type.in_(allowed_types))
#             .order_by(SessionORM.type)
#         )
#     return [row[0] for row in result.fetchall()]
def fetch_session_types_by_team(db: Session, team: str) -> List[str]:
    if team in ["admin", "instructor"]:
        result = db.execute(select(SessionORM.type).distinct().order_by(SessionORM.type))
    else:
        allowed_types = [
            "Resume Session", "Job Help", "Interview Prep",
            "Individual Mock", "Group Mock", "Misc", "Internal Session"
        ]
        result = db.execute(
            select(SessionORM.type).distinct()
            .where(SessionORM.type.in_(allowed_types))
            .order_by(SessionORM.type)
        )

    session_types = [row[0] for row in result.fetchall()]

    # normalize: replace "Internal Session" → "Internal Sessions"
    return ["Internal Sessions" if t == "Internal Session" else t for t in session_types]


def fetch_course_batches(db: Session) -> List[Dict[str, Any]]:
    course = "ML"  
    try:
   
        course_obj = db.execute(
            select(Course).where(Course.alias == course)
        ).scalar_one_or_none()

        if not course_obj:
            return []  

   
        stmt = (
            select(Batch.batchname, Batch.batchid)
            .where(Batch.courseid == course_obj.id)
            .group_by(Batch.batchname, Batch.batchid)
            .order_by(Batch.batchname.desc())
        )
        result = db.execute(stmt)
        rows = result.all()
        if not rows:
            return []

        return [{"batchname": row.batchname, "batchid": row.batchid} for row in rows]
    
    except Exception as e:
        logger.exception(f"Error fetching batches for course '{course}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")


    
    
async def course_content(session: AsyncSession):
    """
    Fetch course content for Fundamentals, AIML, UI, and QE.
    """
    result = await session.execute(select(
        CourseContent.Fundamentals,
        CourseContent.AIML,
        CourseContent.UI,
        CourseContent.QE
    ))
    rows = result.all()
    return [
        dict(Fundamentals=row[0], AIML=row[1], UI=row[2], QE=row[3])
        for row in rows
    ]





# def fetch_subject_batch_recording(
#     course: str,
#     db: Session,
#     batchid: Optional[int] = None,
#     search: Optional[str] = None
# ):
#     """
#     Fetch recordings for a given course, with optional batch filter and search term.
#     """

  
#     course_obj = db.execute(
#         select(Course).where(Course.alias == course)
#     ).scalar_one_or_none()

#     if not course_obj:
#         print(f"[DEBUG] Course '{course}' not found in DB")
#         raise HTTPException(status_code=404, detail=f"Course '{course}' not found")


#     query = (db.query(
#                 Recording,
#                 Batch.batchname,
#                 Course.name.label("course_name")
#             )
#             .join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
#             .join(Batch, RecordingBatch.batch_id == Batch.batchid)
            
#             .join(CourseSubject, Batch.courseid == CourseSubject.course_id)
#             .join(Course, Course.id == CourseSubject.course_id)
#             .filter(Course.alias == course)
#             .filter(Batch.batchid == batchid if batchid is not None else True)        
#             .filter(Recording.new_subject_id == CourseSubject.subject_id)
#             .order_by(Recording.classdate.desc())
#         )


   
#     if search:
#         like_str = f"%{search}%"
#         print(f"[DEBUG] Applying search filter: {like_str}")
#         query = (db.query(
#         Recording,
#         Batch.batchname,
#         Course.name.label("course_name")
#         ).join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
#         .join(Batch, RecordingBatch.batch_id == Batch.batchid)
#         .join(CourseSubject, Batch.courseid == CourseSubject.course_id)
#         .join(Course, Course.id == CourseSubject.course_id)
#         .filter(Course.alias == course)
#         .filter(Batch.batchid == batchid if batchid is not None else True)
#         .filter(Recording.new_subject_id == CourseSubject.subject_id)
#         .filter(
#             or_(
#                 Recording.description.ilike(f"%{search}%")
#             ) if search else True
#         ).order_by(Recording.classdate.desc()))

#     query = query.order_by(Recording.classdate.desc())

#     recordings = db.execute(query).scalars().all()

#     return {"batch_recordings": recordings}



# def fetch_course_batches(course: str, db: Session) -> List[Dict[str, Any]]:
#     try:
        

#         stmt = (
#         select(Batch.batchname, Batch.batchid)
#         .where(Batch.subject == course)  
#         .order_by(Batch.batchname.desc())
#     )

#         rows = db.execute(stmt).all()

#         if not rows:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"No batches found for course '{course}'"
#             )

#         return [{"batchname": row.batchname, "batchid": row.batchid} for row in rows]

#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"Error fetching batches for {course}: {e}")
#         raise HTTPException(status_code=500, detail="Unexpected server error")



def fetch_subject_batch_recording(
    course: str,
    db: Session,
    batchid: Optional[int] = None,
    search: Optional[str] = None
):
    """
    Fetch recordings for a given course, with optional batch filter and search term.
    """

  
    course_obj = db.execute(
        select(Course).where(Course.alias == course)
    ).scalar_one_or_none()

    if not course_obj:
        print(f"[DEBUG] Course '{course}' not found in DB")
        raise HTTPException(status_code=404, detail=f"Course '{course}' not found")


    query = (db.query(
                Recording,
                Batch.batchname,
                Course.name.label("course_name")
            )
            .join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
            .join(Batch, RecordingBatch.batch_id == Batch.batchid)
            
            .join(CourseSubject, Batch.courseid == CourseSubject.course_id)
            .join(Course, Course.id == CourseSubject.course_id)
            .filter(Course.alias == course)
            .filter(Batch.batchid == batchid if batchid is not None else True)        
            .filter(Recording.new_subject_id == CourseSubject.subject_id)
            .order_by(Recording.classdate.desc())
        )


   
    if search:
        like_str = f"%{search}%"
        print(f"[DEBUG] Applying search filter: {like_str}")
        query = (db.query(
        Recording,
        Batch.batchname,
        Course.name.label("course_name")
        ).join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
        .join(Batch, RecordingBatch.batch_id == Batch.batchid)
        .join(CourseSubject, Batch.courseid == CourseSubject.course_id)
        .join(Course, Course.id == CourseSubject.course_id)
        .filter(Course.alias == course)
        .filter(Batch.batchid == batchid if batchid is not None else True)
        .filter(Recording.new_subject_id == CourseSubject.subject_id)
        .filter(
            or_(
                Recording.description.ilike(f"%{search}%")
            ) if search else True
        ).order_by(Recording.classdate.desc()))

    query = query.order_by(Recording.classdate.desc())

    recordings = db.execute(query).scalars().all()

    return {"batch_recordings": recordings}



def fetch_course_batches(course: str, db: Session) -> List[Dict[str, Any]]:
    try:
        

        stmt = (
        select(Batch.batchname, Batch.batchid)
        .where(Batch.subject == course)  
        .order_by(Batch.batchname.desc())
    )

        rows = db.execute(stmt).all()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No batches found for course '{course}'"
            )

        return [{"batchname": row.batchname, "batchid": row.batchid} for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching batches for {course}: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")
    
    
def fetch_kumar_recordings(
    db: Session,
    search: Optional[str] = None
):
    """
    Fetch all recordings that contain 'Kumar' in the description or filename,
    but only include recordings from the year 2024 onwards.
    """

    try:
        query = db.query(Recording).filter(
            or_(
                Recording.description.ilike("%kumar%"),
                Recording.filename.ilike("%kumar%")
            )
        )
        if search:
            query = query.filter(Recording.description.ilike(f"%{search}%"))
        query = query.filter(
            extract('year', Recording.classdate) >= 2024
        )
        query = query.order_by(Recording.classdate.desc())
        recordings = query.all()
        return {"batch_recordings": recordings}

    except Exception as e:
        logger.exception(f"Error fetching Kumar recordings: {e}")
        raise HTTPException(status_code=500, detail="Error fetching Kumar recordings")
