from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import RawJobListingORM
from fapi.db.schemas import RawJobListingCreate, RawJobListingUpdate
from typing import List, Optional

def get_raw_job_listings(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[RawJobListingORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999 
    
    query = db.query(RawJobListingORM).order_by(RawJobListingORM.id.desc()).offset(skip)
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_raw_job_listing(db: Session, raw_job_listing_id: int) -> Optional[RawJobListingORM]:
    return db.query(RawJobListingORM).filter(RawJobListingORM.id == raw_job_listing_id).first()

def create_raw_job_listing(db: Session, raw_job_listing: RawJobListingCreate) -> RawJobListingORM:
    db_raw_job_listing = RawJobListingORM(**raw_job_listing.model_dump())
    db.add(db_raw_job_listing)
    db.commit()
    db.refresh(db_raw_job_listing)
    return db_raw_job_listing

def update_raw_job_listing(db: Session, raw_job_listing_id: int, raw_job_listing: RawJobListingUpdate) -> Optional[RawJobListingORM]:
    db_raw_job_listing = db.query(RawJobListingORM).filter(RawJobListingORM.id == raw_job_listing_id).first()
    if not db_raw_job_listing:
        return None
    
    update_data = raw_job_listing.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_raw_job_listing, key, value)
    
    db.commit()
    db.refresh(db_raw_job_listing)
    return db_raw_job_listing

def delete_raw_job_listing(db: Session, raw_job_listing_id: int) -> bool:
    db_raw_job_listing = db.query(RawJobListingORM).filter(RawJobListingORM.id == raw_job_listing_id).first()
    if not db_raw_job_listing:
        return False
    
    db.delete(db_raw_job_listing)
    db.commit()
    return True

def search_raw_job_listings(db: Session, term: str) -> List[RawJobListingORM]:
    return db.query(RawJobListingORM).filter(
        or_(
            RawJobListingORM.raw_title.ilike(f"%{term}%"),
            RawJobListingORM.raw_company.ilike(f"%{term}%"),
            RawJobListingORM.raw_location.ilike(f"%{term}%"),
            RawJobListingORM.source_uid.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_raw_job_listings(db: Session) -> int:
    """Get total count of raw job listings for pagination"""
    return db.query(RawJobListingORM).count()

async def insert_raw_job_listings_bulk(positions: List[RawJobListingCreate], db: Session) -> dict:
    """Bulk insert raw job listings with duplicate handling"""
    inserted = 0
    failed = 0
    duplicates = 0
    failed_contacts = []
    
    try:
        for pos_data in positions:
            try:
                # Check for duplicates by source and source_uid
                existing = None
                if pos_data.source_uid:
                    existing = db.query(RawJobListingORM).filter(
                        RawJobListingORM.source == pos_data.source,
                        RawJobListingORM.source_uid == pos_data.source_uid
                    ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Insert new position
                db_pos = RawJobListingORM(**pos_data.model_dump())
                db.add(db_pos)
                inserted += 1
                
                # Flush every 100 records to keep memory low
                if inserted % 100 == 0:
                    db.flush()
                    
            except Exception as e:
                failed += 1
                failed_contacts.append({
                    "source_uid": pos_data.source_uid,
                    "reason": str(e)
                })
        
        db.commit()
        
        return {
            "inserted": inserted,
            "skipped": duplicates,
            "total": len(positions),
            "failed_contacts": failed_contacts
        }
        
    except Exception as e:
        db.rollback()
        raise e
