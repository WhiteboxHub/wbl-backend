from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import JobListingCreate, JobListingUpdate, JobListingOut
from fapi.utils import job_listing_utils

router = APIRouter(prefix="/positions", tags=["Positions"], redirect_slashes=False)

@router.get("/", response_model=List[JobListingOut])
def read_positions(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return job_listing_utils.get_positions(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_positions_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    """Get job listings with page-based pagination"""
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = job_listing_utils.count_positions(db)
    data = job_listing_utils.get_positions(db, skip=skip, limit=page_size)
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
def count_positions(db: Session = Depends(get_db)):
    """Get total count of job listings for pagination"""
    count = job_listing_utils.count_positions(db)
    return {"count": count}

@router.get("/search", response_model=List[JobListingOut])
def search_positions(term: str, db: Session = Depends(get_db)):
    return job_listing_utils.search_positions(db, term=term)

@router.get("/{position_id}", response_model=JobListingOut)
def read_position(position_id: int, db: Session = Depends(get_db)):
    db_position = job_listing_utils.get_position(db, position_id=position_id)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position

@router.post("/", response_model=JobListingOut, status_code=status.HTTP_201_CREATED)
def create_position(position: JobListingCreate, db: Session = Depends(get_db)):
    return job_listing_utils.create_position(db, position=position)

@router.put("/{position_id}", response_model=JobListingOut)
def update_position(position_id: int, position: JobListingUpdate, db: Session = Depends(get_db)):
    db_position = job_listing_utils.update_position(db, position_id=position_id, position=position)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position

@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, db: Session = Depends(get_db)):
    success = job_listing_utils.delete_position(db, position_id=position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Position not found")
    return None
