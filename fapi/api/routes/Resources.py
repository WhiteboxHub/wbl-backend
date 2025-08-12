from fastapi import APIRouter, HTTPException, Query, Depends
import logging
from fapi.utils.resources_utils import fetch_subject_batch_recording,fetch_course_batches
logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


from fastapi import HTTPException, status

@router.get("/api/recording")
def get_recordings(course: str, batchid: int, db: Session = Depends(get_db)):
    try:
        recordings = fetch_subject_batch_recording(course, batchid, db)
        if not recordings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No recordings found for course '{course}' and batch '{batchid}'."
            )
        return recordings
    except Exception as e:
        # Log the error if you want
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching recordings: {str(e)}"
        )

@router.get("/api/batches")
def get_batches(db: Session = Depends(get_db)):
    try:
        batches = fetch_course_batches(db)
        if not batches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No batches found."
            )
        return {"batches": batches}
    except Exception as e:
        # Log the error if you want
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching batches: {str(e)}"
        )
