from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import recording_batch_utils
from fapi.utils.recording_batch_utils import get_recording_batches_version

router = APIRouter()
security = HTTPBearer()

@router.head("/recording-batches")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_recording_batches_version(db)

@router.get("/recording-batches", response_model=List[schemas.RecordingBatch])
def get_recording_batches(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all recording batch mappings"""
    return recording_batch_utils.get_all_recording_batches(db)

@router.get("/recording-batches/recording/{recording_id}", response_model=List[schemas.RecordingBatch])
def get_batches_for_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all batches for a specific recording"""
    return recording_batch_utils.get_batches_for_recording(db, recording_id)

@router.get("/recording-batches/batch/{batch_id}", response_model=List[schemas.RecordingBatch])
def get_recordings_for_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all recordings for a specific batch"""
    return recording_batch_utils.get_recordings_for_batch(db, batch_id)

@router.get("/recording-batches/{recording_id}/{batch_id}", response_model=schemas.RecordingBatch)
def get_recording_batch(
    recording_id: int,
    batch_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific recording batch mapping"""
    recording_batch = recording_batch_utils.get_recording_batch(db, recording_id, batch_id)
    if not recording_batch:
        raise HTTPException(status_code=404, detail="Recording batch mapping not found")
    return recording_batch

@router.post("/recording-batches", response_model=schemas.RecordingBatch)
def create_recording_batch(
    recording_batch: schemas.RecordingBatchCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new recording batch mapping"""
    try:
        return recording_batch_utils.create_recording_batch(db, recording_batch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/recording-batches/{recording_id}/{batch_id}", response_model=schemas.RecordingBatch)
def update_recording_batch(
    recording_id: int,
    batch_id: int,
    recording_batch: schemas.RecordingBatchCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing recording batch mapping"""
    try:
        return recording_batch_utils.update_recording_batch(
            db, recording_id, batch_id, recording_batch
        )
    except ValueError as e:
        error_message = str(e)
        if error_message == "Recording batch mapping not found":
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=422, detail=error_message)

@router.delete("/recording-batches/{recording_id}/{batch_id}")
def delete_recording_batch(
    recording_id: int,
    batch_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a recording batch mapping"""
    try:
        recording_batch_utils.delete_recording_batch(db, recording_id, batch_id)
        return {"status": "success", "message": "Recording batch mapping deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))