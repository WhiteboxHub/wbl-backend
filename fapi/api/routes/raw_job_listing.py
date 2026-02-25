from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.schemas import (
    RawJobListingCreate, 
    RawJobListingUpdate, 
    RawJobListingOut,
    RawJobListingBulkCreate,
    RawJobListingBulkResponse
)
from fapi.utils import raw_job_listing_utils
from fapi.db.models import RawJobListingORM
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter(prefix="/raw-positions", tags=["Raw Positions"])

security = HTTPBearer()

@router.head("/")
@router.head("/paginated")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, RawJobListingORM)

def check_raw_positions_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(RawJobListingORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        RawJobListingORM.id,
                        func.coalesce(RawJobListingORM.raw_title, ''),
                        func.coalesce(RawJobListingORM.raw_company, ''),
                        func.coalesce(RawJobListingORM.raw_location, ''),
                        func.coalesce(RawJobListingORM.processing_status, '')
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
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

@router.get("/", response_model=List[RawJobListingOut])
def read_raw_job_listings(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return raw_job_listing_utils.get_raw_job_listings(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_raw_job_listings_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = raw_job_listing_utils.count_raw_job_listings(db)
    data = raw_job_listing_utils.get_raw_job_listings(db, skip=skip, limit=page_size)
    total_pages = (total_records + page_size - 1) // page_size  
    
    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

@router.get("/count", response_model=dict)
def count_raw_job_listings(db: Session = Depends(get_db)):
    count = raw_job_listing_utils.count_raw_job_listings(db)
    return {"count": count}

@router.get("/search", response_model=List[RawJobListingOut])
def search_raw_job_listings(term: str, db: Session = Depends(get_db)):
    return raw_job_listing_utils.search_raw_job_listings(db, term=term)

@router.get("/{raw_job_listing_id}", response_model=RawJobListingOut)
def read_raw_job_listing(raw_job_listing_id: int, db: Session = Depends(get_db)):
    db_raw_job_listing = raw_job_listing_utils.get_raw_job_listing(db, raw_job_listing_id=raw_job_listing_id)
    if not db_raw_job_listing:
        raise HTTPException(status_code=404, detail="Raw job listing not found")
    return db_raw_job_listing

@router.post("/", response_model=RawJobListingOut, status_code=status.HTTP_201_CREATED)
def create_raw_job_listing(raw_job_listing: RawJobListingCreate, db: Session = Depends(get_db)):
    return raw_job_listing_utils.create_raw_job_listing(db, raw_job_listing=raw_job_listing)

@router.post("/bulk", response_model=RawJobListingBulkResponse)
async def create_raw_job_listings_bulk(
    bulk_data: RawJobListingBulkCreate,
    db: Session = Depends(get_db)
):
    return await raw_job_listing_utils.insert_raw_job_listings_bulk(bulk_data.positions, db)

@router.put("/{raw_job_listing_id}", response_model=RawJobListingOut)
def update_raw_job_listing(raw_job_listing_id: int, raw_job_listing: RawJobListingUpdate, db: Session = Depends(get_db)):
    db_raw_job_listing = raw_job_listing_utils.update_raw_job_listing(db, raw_job_listing_id=raw_job_listing_id, raw_job_listing=raw_job_listing)
    if not db_raw_job_listing:
        raise HTTPException(status_code=404, detail="Raw job listing not found")
    return db_raw_job_listing

@router.delete("/{raw_job_listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_raw_job_listing(raw_job_listing_id: int, db: Session = Depends(get_db)):
    success = raw_job_listing_utils.delete_raw_job_listing(db, raw_job_listing_id=raw_job_listing_id)
    if not success:
        raise HTTPException(status_code=404, detail="Raw job listing not found")
    return None
