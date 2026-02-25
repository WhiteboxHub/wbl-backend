import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.database import get_db
from fapi.utils import batch_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/batch", response_model=List[schemas.BatchOut])
def read_batches(
    search: Optional[str] = Query(None, description="Search by batch name"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return batch_utils.get_all_batches(db, search=search)

@router.head("/batch")
def check_batches_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        from fastapi import Response
        import hashlib
        from sqlalchemy import func
        from fapi.db.models import Batch
        
        result = db.query(
            func.count().label("cnt"),
            func.max(Batch.batchid).label("max_id"),
            func.max(Batch.lastmoddatetime).label("max_mod"), # Added lastmoddatetime
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        Batch.batchid,
                        func.coalesce(Batch.batchname, ''),
                        func.coalesce(Batch.subject, ''),
                        func.coalesce(Batch.startdate, ''),
                        func.coalesce(Batch.enddate, ''),
                        func.coalesce(Batch.instructorid, ''),
                        func.coalesce(Batch.lastmoddatetime, '') # Added lastmoddatetime to checksum
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        logger.error(f"[ERROR] HEAD /batch failed: {e}")
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


@router.get("/batch/{batch_id}", response_model=schemas.BatchOut)
def read_batch(
    batch_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    db_batch = batch_utils.get_batch_by_id(db, batch_id)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch


@router.post("/batch", response_model=schemas.BatchOut)
def create_batch(batch: schemas.BatchCreate, db: Session = Depends(get_db)):
    return batch_utils.create_batch(db, batch)


@router.put("/batch/{batch_id}", response_model=schemas.BatchOut)
def update_batch(batch_id: int, batch: schemas.BatchUpdate, db: Session = Depends(get_db)):
    db_batch = batch_utils.update_batch(db, batch_id, batch)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch


@router.delete("/batch/{batch_id}", response_model=schemas.BatchOut)
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = batch_utils.delete_batch(db, batch_id)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch