# wbl-backend/fapi/utils/batch_utils.py
from sqlalchemy.orm import Session
from fapi.db import models, schemas
from typing import Optional

def get_batches_paginated(
    db: Session,
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None
):
    query = db.query(models.Batch)

    if search:
        # Try numeric search for batchid
        if search.isdigit():
            query = query.filter(models.Batch.batchid == int(search))
        else:
            # Search by batchname (case-insensitive)
            query = query.filter(models.Batch.batchname.ilike(f"%{search}%"))

    total = query.count()
    offset = (page - 1) * per_page

    batches = (
        query.order_by(models.Batch.batchid.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "batches": batches,
    }

def get_batch_by_id(db: Session, batch_id: int):
    return db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()

def create_batch(db: Session, batch: schemas.BatchCreate):
    db_batch = models.Batch(**batch.dict())
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch

def update_batch(db: Session, batch_id: int, batch: schemas.BatchUpdate):
    db_batch = db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()
    if not db_batch:
        return None
    for key, value in batch.dict(exclude_unset=True).items():
        setattr(db_batch, key, value)
    db.commit()
    db.refresh(db_batch)
    return db_batch

def delete_batch(db: Session, batch_id: int):
    db_batch = db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()
    if not db_batch:
        return None
    db.delete(db_batch)
    db.commit()
    return db_batch
