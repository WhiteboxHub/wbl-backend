

# fapi/utils/resources_utils.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.future import select
from sqlalchemy import case, or_
from fapi.db.models import Session as SessionORM, CourseSubject , CourseMaterial, Recording, RecordingBatch, CourseSubject, Course, Subject, Batch, CourseContent
from typing import List, Dict, Any
from fastapi import HTTPException, status
from fapi.db.database import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
import logging


logger = logging.getLogger(__name__)


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


        # Convert ORM objects to dictionaries
        return [
            {column.name: getattr(row, column.name) for column in row.__table__.columns}
            for row in results
        ]

    
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


def fetch_subject_batch_recording(course: str, batchid: int, db: Session):
    try:
        course_obj = db.query(Course).filter(Course.alias == course).first()
        if not course_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{course}' not found"
            )
        
        recordings = (
            db.query(Recording)
            .join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
            .join(Batch, RecordingBatch.batch_id == Batch.batchid)
            .filter(Batch.batchid == batchid)
            .all()
        )
        if not recordings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No recordings found for batch ID '{batchid}'"
            )
        
        return {"recordings": recordings}

    except HTTPException:
        
        raise
    except Exception as e:
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching recordings: {str(e)}"
        )



def fetch_course_batches(db: Session) -> List[Dict[str, Any]]:
    course = "ML"  
    try:
        course_obj = db.execute(
            select(Course).where(Course.alias == course)
        ).scalar_one_or_none()

        if not course_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{course}' not found"
            )

        stmt = (
            select(Batch.batchname, Batch.batchid)
            .where(Batch.courseid == course_obj.id)
            .group_by(Batch.batchname, Batch.batchid)
            .order_by(Batch.batchname.desc())
        )
        result = db.execute(stmt)
        rows = result.all()

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No batches found for course '{course}'"
            )

        return [{"batchname": row.batchname, "batchid": row.batchid} for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching batches for course '{course}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")

