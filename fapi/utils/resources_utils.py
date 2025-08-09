
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from typing import Dict, Any, List
import logging

from fapi.db.models import (
    Recording, RecordingBatch, CourseSubject,
    Course, Subject, Batch
)

logger = logging.getLogger(__name__)


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
