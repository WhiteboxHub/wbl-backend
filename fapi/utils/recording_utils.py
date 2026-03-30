# fapi/utils/recording_utils.py
from sqlalchemy.orm import Session
from fapi.db.models import Recording
from sqlalchemy import or_
from fapi.db import schemas
from typing import Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache


@cache_result(ttl=300, prefix="recordings")
def get_all_recordings(db: Session, search: Optional[str] = None):
    query = db.query(Recording)

    if search:
        search = search.strip()
        filters = []

        # Partial match on batchname, subject, description
        #filters.append(Recording.batchname.ilike(f"%{search}%"))
        filters.append(Recording.subject.ilike(f"%{search}%"))
        filters.append(Recording.description.ilike(f"%{search}%"))

        # If numeric, also check id
        if search.isdigit():
            filters.append(Recording.id == int(search))

        query = query.filter(or_(*filters))

    return query.order_by(Recording.id.desc()).all()


@cache_result(ttl=300, prefix="recordings")
def get_recording_by_id(db: Session, recording_id: int):
    return db.query(Recording).filter(Recording.id == recording_id).first()


def create_recording(db: Session, recording: schemas.RecordingCreate):
    invalidate_cache("recordings")
    invalidate_cache("resources")
    db_recording = Recording(**recording.dict())
    db.add(db_recording)
    db.commit()
    db.refresh(db_recording)
    return db_recording


def update_recording(db: Session, recording_id: int, recording: schemas.RecordingUpdate):
    invalidate_cache("recordings")
    invalidate_cache("resources")
    db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not db_recording:
        return None
    for key, value in recording.dict(exclude_unset=True).items():
        setattr(db_recording, key, value)
    db.commit()
    db.refresh(db_recording)
    return db_recording


def delete_recording(db: Session, recording_id: int):
    invalidate_cache("recordings")
    invalidate_cache("resources")
    db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not db_recording:
        return None
    db.delete(db_recording)
    db.commit()
    return db_recording

def get_recordings_version(db: Session) -> Response:
    return generate_version_for_model(db, Recording)
