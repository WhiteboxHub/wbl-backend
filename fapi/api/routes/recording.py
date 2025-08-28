from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from fapi.db import schemas, database
from fapi.utils import recording_utils

router = APIRouter()


@router.get("/recordings")
def get_recordings(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str = None,
    db: Session = Depends(database.get_db),
):
    return recording_utils.get_all_recordings(db, page=page, per_page=per_page, search=search)


@router.get("/recordings/{recording_id}", response_model=schemas.RecordingOut)
def get_recording(recording_id: int, db: Session = Depends(database.get_db)):
    db_recording = recording_utils.get_recording_by_id(db, recording_id)
    if not db_recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return db_recording

@router.post("/recordings", response_model=schemas.RecordingOut)
def create_recording(recording: schemas.RecordingCreate, db: Session = Depends(database.get_db)):
    return recording_utils.create_recording(db, recording)

@router.put("/recordings/{recording_id}", response_model=schemas.RecordingOut)
def update_recording(recording_id: int, recording: schemas.RecordingUpdate, db: Session = Depends(database.get_db)):
    db_recording = recording_utils.update_recording(db, recording_id, recording)
    if not db_recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return db_recording

@router.delete("/recordings/{recording_id}", response_model=schemas.RecordingOut)
def delete_recording(recording_id: int, db: Session = Depends(database.get_db)):
    db_recording = recording_utils.delete_recording(db, recording_id)
    if not db_recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return db_recording
