from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import logging
from fapi.db.database import SessionLocal
from fapi.db.schemas import Recording

from fapi.utils.recordings_utils import fetch_subject_batch_recording

router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
logger = logging.getLogger("recordings_logger")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

async def get_recordings(
    course: str = Query(...),
    batchid: int = Query(...),
    db: AsyncSession = Depends(get_db)
):
    return await fetch_subject_batch_recording(course, batchid, db)


