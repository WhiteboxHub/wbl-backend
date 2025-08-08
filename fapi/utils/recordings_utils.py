
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, session
from fapi.db.models import Recording,RecordingBatch, Session, CourseSubject,Course,Subject
from fastapi import HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from fapi.db.models import Batch
from typing import Dict, Any
from sqlalchemy.future import select
from fastapi import HTTPException
logger = logging.getLogger(__name__)

async def fetch_subject_batch_recording(course: str, batchid: int, db: AsyncSession) -> Dict[str, Any]:
    try:
        # Step 1: Get Course
        course_stmt = select(Course).where(Course.alias == course)
        course_result =  db.execute(course_stmt)               # <-- await here
        course_obj = course_result.scalar_one_or_none()
        if not course_obj:
            raise HTTPException(status_code=404, detail="Course not found")

        # Step 2: Get all subjects for that course
        subject_stmt = select(Subject).join(CourseSubject).where(
            CourseSubject.course_id == course_obj.id
        )
        subject_result =  db.execute(subject_stmt)             # <-- await here
        subjects = subject_result.scalars().all()
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
        rec_result =  db.execute(rec_stmt)                      # <-- await here
        recordings = rec_result.scalars().all()

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

    except Exception as e:
        print("Unexpected server error while fetching recordings:", str(e))
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")



# from sqlalchemy.future import select
# from sqlalchemy.orm import joinedload
# from fastapi import HTTPException

# from fapi.db.models import Course, CourseSubject, Recording, RecordingBatch, Batch

# async def fetch_subject_batch_recording(course: str, batchid: int, db):
#     try:
#         # 1️⃣ Get the course object
#         course_stmt = select(Course).where(Course.alias == course)
#         course_result = db.execute(course_stmt)
#         course_obj = course_result.scalar_one_or_none()

#         if not course_obj:
#             return {"status": "error", "message": "Course not found", "recordings": []}

#         # 2️⃣ Get all course_subject entries for this course
#         course_subject_stmt = select(CourseSubject).where(CourseSubject.course_id == course_obj.id)
#         course_subject_result = db.execute(course_subject_stmt)
#         course_subjects = course_subject_result.scalars().all()

#         if not course_subjects:
#             return {"status": "error", "message": "No subjects found for this course", "recordings": []}

#         # 3️⃣ Collect subject IDs
#         subject_ids = [cs.subject_id for cs in course_subjects]

#         # 4️⃣ Get recordings for the batch & subjects
#         recording_stmt = (
#             select(Recording)
#             .join(RecordingBatch, Recording.id == RecordingBatch.recording_id)
#             .join(Batch, RecordingBatch.batch_id == Batch.batchid)
#             .where(RecordingBatch.batch_id == batchid, Recording.new_subject_id.in_(subject_ids))
#             .options(joinedload(Recording.recording_batches))
#         )
#         recording_result = db.execute(recording_stmt)
#         recordings = recording_result.unique().scalars().all()  # <-- only changed here

#         # 5️⃣ Prepare the response to match frontend expectations
#         response_data = []
#         for rec in recordings:
#             response_data.append({
#                 "id": rec.id,
#                 "title": getattr(rec, "title", ""),              # Defensive get attribute
#                 "description": getattr(rec, "description", ""),
#                 "video_url": getattr(rec, "link", ""),          # changed to link, your DDL shows 'link'
#                 "subject_id": rec.new_subject_id,
#                 "created_at": rec.lastmoddatetime.isoformat() if rec.lastmoddatetime else None,
#             })

#         return {
#             "status": "success",
#             "message": "Recordings fetched successfully",
#             "recordings": response_data
#         }

#     except Exception as e:
#         # Any unhandled error — avoid exposing raw error to frontend
#         raise HTTPException(status_code=500, detail=f"Error fetching recordings: {str(e)}")
