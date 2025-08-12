



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

from fapi.db.models import (
    Recording, RecordingBatch, CourseSubject,
    Course, Subject, Batch
)

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


