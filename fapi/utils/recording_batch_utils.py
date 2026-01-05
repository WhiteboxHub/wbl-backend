from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models, schemas

def get_all_recording_batches(db: Session) -> List[models.RecordingBatch]:
    """Get all recording batch mappings"""
    return db.query(models.RecordingBatch).all()

def get_recording_batch(db: Session, recording_id: int, batch_id: int) -> Optional[models.RecordingBatch]:
    """Get specific recording batch mapping"""
    return db.query(models.RecordingBatch).filter(
        models.RecordingBatch.recording_id == recording_id,
        models.RecordingBatch.batch_id == batch_id
    ).first()

def get_batches_for_recording(db: Session, recording_id: int) -> List[models.RecordingBatch]:
    """Get all batches for a recording"""
    return db.query(models.RecordingBatch).filter(
        models.RecordingBatch.recording_id == recording_id
    ).all()

def get_recordings_for_batch(db: Session, batch_id: int) -> List[models.RecordingBatch]:
    """Get all recordings for a batch"""
    return db.query(models.RecordingBatch).filter(
        models.RecordingBatch.batch_id == batch_id
    ).all()

def create_recording_batch(db: Session, recording_batch: schemas.RecordingBatchCreate) -> models.RecordingBatch:
    """Create a new recording batch mapping"""
    existing = get_recording_batch(db, recording_batch.recording_id, recording_batch.batch_id)
    if existing:
        raise ValueError("Recording batch mapping already exists")
    
    # Verify recording exists
    recording = db.query(models.Recording).filter(models.Recording.id == recording_batch.recording_id).first()
    if not recording:
        raise ValueError("Recording not found")
    
    # Verify batch exists
    batch = db.query(models.Batch).filter(models.Batch.batchid == recording_batch.batch_id).first()
    if not batch:
        raise ValueError("Batch not found")
    
    db_recording_batch = models.RecordingBatch(**recording_batch.model_dump())
    db.add(db_recording_batch)
    db.commit()
    db.refresh(db_recording_batch)
    return db_recording_batch

def delete_recording_batch(db: Session, recording_id: int, batch_id: int) -> bool:
    """Delete a recording batch mapping"""
    db_recording_batch = get_recording_batch(db, recording_id, batch_id)
    if not db_recording_batch:
        raise ValueError("Recording batch mapping not found")
    
    db.delete(db_recording_batch)
    db.commit()
    return True