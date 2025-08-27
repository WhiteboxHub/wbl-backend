from sqlalchemy.orm import Session
from fapi.db.models import Recording
from sqlalchemy import or_
from fapi.db import schemas


def get_all_recordings(db: Session, page: int = 1, per_page: int = 10, search: str = None):
    skip = (page - 1) * per_page
    query = db.query(Recording)

    # Apply search (by ID or batchname)
    if search:
        if search.isdigit():
            query = query.filter(
                or_(Recording.id == int(search), Recording.batchname.ilike(f"%{search}%"))
            )
        else:
            query = query.filter(
                or_(Recording.batchname.ilike(f"%{search}%"),
                    Recording.subject.ilike(f"%{search}%"),
                    Recording.description.ilike(f"%{search}%")
                )
            )

    total = query.count()

    recordings = (
        query.order_by(Recording.id.desc())
        .offset(skip)
        .limit(per_page)
        .all()
    )

    return {"recordings": recordings, "total": total}

def get_recording_by_id(db: Session, recording_id: int):
    return db.query(Recording).filter(Recording.id == recording_id).first()

def create_recording(db: Session, recording: schemas.RecordingCreate):
    db_recording = Recording(**recording.dict())
    db.add(db_recording)
    db.commit()
    db.refresh(db_recording)
    return db_recording

def update_recording(db: Session, recording_id: int, recording: schemas.RecordingUpdate):
    db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if db_recording:
        for key, value in recording.dict(exclude_unset=True).items():
            setattr(db_recording, key, value)
        db.commit()
        db.refresh(db_recording)
    return db_recording

def delete_recording(db: Session, recording_id: int):
    db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if db_recording:
        db.delete(db_recording)
        db.commit()
    return db_recording
