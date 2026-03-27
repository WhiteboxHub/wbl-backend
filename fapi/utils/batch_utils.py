from sqlalchemy.orm import Session
from fapi.db import models, schemas
from typing import Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

@cache_result(ttl=300, prefix="batches")
def get_all_batches(db: Session, search: Optional[str] = None):
    query = db.query(models.Batch)

    if search:
        search = search.strip()
        filters = []

        filters.append(models.Batch.batchname.ilike(f"%{search}%"))

        if search.isdigit():
            filters.append(models.Batch.batchid == int(search))

        query = query.filter(*filters)

    return query.order_by(models.Batch.batchid.desc()).all()


@cache_result(ttl=300, prefix="batches")
def get_batch_by_id(db: Session, batch_id: int):
    return db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()


def create_batch(db: Session, batch: schemas.BatchCreate):
    invalidate_cache("batches")
    invalidate_cache("metrics")
    db_batch = models.Batch(**batch.dict())
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch


def update_batch(db: Session, batch_id: int, batch: schemas.BatchUpdate):
    invalidate_cache("batches")
    invalidate_cache("metrics")
    db_batch = db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()
    if not db_batch:
        return None
    for key, value in batch.dict(exclude_unset=True).items():
        setattr(db_batch, key, value)
    db.commit()
    db.refresh(db_batch)
    return db_batch


def delete_batch(db: Session, batch_id: int):
    invalidate_cache("batches")
    invalidate_cache("metrics")
    db_batch = db.query(models.Batch).filter(models.Batch.batchid == batch_id).first()
    if not db_batch:
        return None
    db.delete(db_batch)
    db.commit()
    return db_batch
def get_batches_version(db: Session) -> Response:
    return generate_version_for_model(db, models.Batch)
