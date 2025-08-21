from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import batch_utils

router = APIRouter(prefix="/batches", tags=["Batches"])

@router.get("/", response_model=list[schemas.BatchOut])
def read_batches(db: Session = Depends(get_db)):
    return batch_utils.get_batches(db)

@router.get("/{batch_id}", response_model=schemas.BatchOut)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = batch_utils.get_batch_by_id(db, batch_id)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@router.post("/", response_model=schemas.BatchOut)
def create_batch(batch: schemas.BatchCreate, db: Session = Depends(get_db)):
    return batch_utils.create_batch(db, batch)

@router.put("/{batch_id}", response_model=schemas.BatchOut)
def update_batch(batch_id: int, batch: schemas.BatchUpdate, db: Session = Depends(get_db)):
    db_batch = batch_utils.update_batch(db, batch_id, batch)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@router.delete("/{batch_id}", response_model=schemas.BatchOut)
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = batch_utils.delete_batch(db, batch_id)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch
