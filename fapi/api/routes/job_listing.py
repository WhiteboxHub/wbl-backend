from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.models import AuthUserORM
from fapi.db.schemas import (
    JobListingCreate, 
    JobListingUpdate, 
    JobListingOut,
    JobListingBulkCreate,
    JobListingBulkResponse,
    PaginatedJobListingResponse,
    CliWindowResponse,
)
from fapi.utils import job_listing_utils
from fapi.utils.job_listing_utils import get_positions_version
from fapi.utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/positions", tags=["Positions"], redirect_slashes=False)

security = HTTPBearer()

@router.head("/")
@router.head("/paginated")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_positions_version(db)

@router.get("/", response_model=List[JobListingOut])
def read_positions(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return job_listing_utils.get_positions(db, skip=skip, limit=limit)

@router.get("/paginated", response_model=PaginatedJobListingResponse)
def read_positions_paginated(

  page: int = 1,
    page_size: int = 500,

    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get job listings with page-based pagination"""
    page_size = min(max(1, page_size), 1500)

    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = job_listing_utils.count_positions(db, search=search)
    data = job_listing_utils.get_positions(db, skip=skip, limit=page_size, search=search)
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


@router.get("/cli_window", response_model=CliWindowResponse)
def read_positions_cli_window(
    days: int = Query(
        0,
        ge=0,
        le=3650,
        description="0 = no time filter (all listings with job_url); >0 = last N UTC days",
    ),
    page_size: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0, le=10_000_000),
    status: Optional[str] = Query("open", description="Use 'all' to disable status filter"),
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user),
):
    """JobCLI: canonical listings (optional time window), oldest first (not cached)."""
    data, total_in_window = job_listing_utils.query_cli_window_listings(
        db,
        days=days,
        page_size=page_size,
        status=status,
        authuser_id=getattr(current_user, "id", None),
        offset=offset,
    )
    return {
        "days": days,
        "page_size": page_size,
        "offset": offset,
        "total_in_window": total_in_window,
        "returned_count": len(data),
        "sort": "created_at_asc",
        "data": data,
    }


@router.get("/{position_id}", response_model=JobListingOut)
def read_position(position_id: int, db: Session = Depends(get_db)):
    db_position = job_listing_utils.get_position(db, position_id=position_id)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position

@router.post("/", response_model=JobListingOut, status_code=status.HTTP_201_CREATED)
def create_position(position: JobListingCreate, db: Session = Depends(get_db)):
    return job_listing_utils.create_position(db, position=position)

@router.post("/bulk", response_model=JobListingBulkResponse)
async def create_positions_bulk(
    bulk_data: JobListingBulkCreate,
    db: Session = Depends(get_db)
):
    return await job_listing_utils.insert_positions_bulk(bulk_data.positions, db)

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
