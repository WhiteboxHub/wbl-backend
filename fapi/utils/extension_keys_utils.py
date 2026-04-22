from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import ExtensionKeyORM
from fapi.db.schemas import ExtensionKeyCreate, ExtensionKeyUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

@cache_result(ttl=300, prefix="extension_keys")
def get_extension_keys(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[ExtensionKeyORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999 
    
    query = db.query(ExtensionKeyORM).order_by(ExtensionKeyORM.id.desc()).offset(skip)
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

@cache_result(ttl=300, prefix="extension_keys")
def get_extension_key(db: Session, key_id: int) -> Optional[ExtensionKeyORM]:
    return db.query(ExtensionKeyORM).filter(ExtensionKeyORM.id == key_id).first()

def create_extension_key(db: Session, extension_key: ExtensionKeyCreate) -> ExtensionKeyORM:
    invalidate_cache("extension_keys")
    db_key = ExtensionKeyORM(**extension_key.model_dump())
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key

def update_extension_key(db: Session, key_id: int, extension_key: ExtensionKeyUpdate) -> Optional[ExtensionKeyORM]:
    invalidate_cache("extension_keys")
    db_key = db.query(ExtensionKeyORM).filter(ExtensionKeyORM.id == key_id).first()
    if not db_key:
        return None
    
    update_data = extension_key.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_key, key, value)
    
    db.commit()
    db.refresh(db_key)
    return db_key

def delete_extension_key(db: Session, key_id: int) -> bool:
    invalidate_cache("extension_keys")
    db_key = db.query(ExtensionKeyORM).filter(ExtensionKeyORM.id == key_id).first()
    if not db_key:
        return False
    
    db.delete(db_key)
    db.commit()
    return True

@cache_result(ttl=300, prefix="extension_keys")
def search_extension_keys(db: Session, term: str) -> List[ExtensionKeyORM]:
    return db.query(ExtensionKeyORM).filter(
        or_(
            ExtensionKeyORM.uname.ilike(f"%{term}%"),
            ExtensionKeyORM.device_name.ilike(f"%{term}%"),
            ExtensionKeyORM.api_key.ilike(f"%{term}%")
        )
    ).limit(100).all()

@cache_result(ttl=300, prefix="extension_keys")
def count_extension_keys(db: Session) -> int:
    return db.query(ExtensionKeyORM).count()

async def insert_extension_keys_bulk(keys: List[ExtensionKeyCreate], db: Session) -> dict:
    invalidate_cache("extension_keys")
    inserted = 0
    failed = 0
    duplicates = 0
    
    try:
        for key_data in keys:
            try:
                existing = db.query(ExtensionKeyORM).filter(
                    ExtensionKeyORM.api_key == key_data.api_key
                ).first()
                if existing:
                    duplicates += 1
                    continue
                
                db_key = ExtensionKeyORM(**key_data.model_dump())
                db.add(db_key)
                inserted += 1
                
                if inserted % 100 == 0:
                    db.flush()
                    
            except Exception as e:
                failed += 1
        
        db.commit()
        
        return {
            "inserted": inserted,
            "skipped": duplicates,
            "total": len(keys)
        }
        
    except Exception as e:
        db.rollback()
        raise e

def get_extension_keys_version(db: Session) -> Response:
    return generate_version_for_model(db, ExtensionKeyORM)
