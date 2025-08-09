from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import logging
from fapi.db.database import SessionLocal
from sqlalchemy.exc import SQLAlchemyError
from fapi.utils.resources_utils import fetch_subject_batch_recording,fetch_course_batches
logger = logging.getLogger(__name__)
router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/api/recordings")
async def get_recordings(course: str, batchid: int, db: AsyncSession = Depends(get_db)):
    try:
        if not course or not batchid:
            raise HTTPException(status_code=400, detail="Course and batchid are required")

        return await fetch_subject_batch_recording(course, batchid, db)

    except HTTPException:
        # Re-raise FastAPI HTTPExceptions so they’re returned as is
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching recordings: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.exception("Unexpected server error in /api/recordings")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")


@router.get("/api/batches")
async def get_batches(course: str, db: AsyncSession = Depends(get_db)):
    try:
        if not course:
            raise HTTPException(status_code=400, detail="Course is required")

        batches = await fetch_course_batches(course, db)
        return {"batches": batches}

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching batches: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.exception("Unexpected server error in /api/batches")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")