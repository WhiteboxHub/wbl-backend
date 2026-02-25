
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional
from fapi.db import schemas, database
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.utils import recording_utils

router = APIRouter()

security = HTTPBearer()

@router.get("/recordings", response_model=list[schemas.RecordingOut])
def get_recordings(
    search: Optional[str] = Query(None, description="Search by ID, batch name, subject, or description"),
    db: Session = Depends(database.get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return recording_utils.get_all_recordings(db, search=search)

@router.head("/recordings")
def check_recordings_version(
    db: Session = Depends(database.get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        from fastapi import Response
        import hashlib
        from sqlalchemy import func
        from fapi.db.models import Recording
        
        result = db.query(
            func.count().label("cnt"),
            func.max(Recording.id).label("max_id"),
            func.max(Recording.lastmoddatetime).label("max_mod"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        Recording.id,
                        func.coalesce(Recording.batchid, ''),
                        func.coalesce(Recording.subjectid, ''),
                        func.coalesce(Recording.description, ''),
                        func.coalesce(Recording.link, ''),
                        func.coalesce(Recording.classdate, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.max_mod}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ERROR] HEAD /recordings failed: {e}")
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


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
