from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import (
    EmailPositionCreate, 
    EmailPositionUpdate, 
    EmailPositionOut,
    EmailPositionBulkCreate,
    EmailPositionBulkResponse
)
from fapi.utils import email_position_utils
from fapi.utils.email_position_utils import get_email_positions_version

router = APIRouter(prefix="/email-positions", tags=["Email Positions"])

security = HTTPBearer()

@router.head("/")
@router.head("/paginated")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_email_positions_version(db)

@router.get("/", response_model=List[EmailPositionOut])
def read_email_positions(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return email_position_utils.get_email_positions(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_email_positions_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = email_position_utils.count_email_positions(db)
    data = email_position_utils.get_email_positions(db, skip=skip, limit=page_size)
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
def count_email_positions(db: Session = Depends(get_db)):
    count = email_position_utils.count_email_positions(db)
    return {"count": count}

@router.get("/search", response_model=List[EmailPositionOut])
def search_email_positions(term: str, db: Session = Depends(get_db)):
    return email_position_utils.search_email_positions(db, term=term)

@router.get("/{email_position_id}", response_model=EmailPositionOut)
def read_email_position(email_position_id: int, db: Session = Depends(get_db)):
    db_email_position = email_position_utils.get_email_position(db, email_position_id=email_position_id)
    if not db_email_position:
        raise HTTPException(status_code=404, detail="Email position not found")
    return db_email_position

@router.post("/", response_model=EmailPositionOut, status_code=status.HTTP_201_CREATED)
def create_email_position(email_position: EmailPositionCreate, db: Session = Depends(get_db)):
    return email_position_utils.create_email_position(db, email_position=email_position)

@router.post("/bulk", response_model=EmailPositionBulkResponse)
async def create_email_positions_bulk(
    bulk_data: EmailPositionBulkCreate,
    db: Session = Depends(get_db)
):
    return await email_position_utils.insert_email_positions_bulk(bulk_data.positions, db)

@router.put("/{email_position_id}", response_model=EmailPositionOut)
def update_email_position(email_position_id: int, email_position: EmailPositionUpdate, db: Session = Depends(get_db)):
    db_email_position = email_position_utils.update_email_position(db, email_position_id=email_position_id, email_position=email_position)
    if not db_email_position:
        raise HTTPException(status_code=404, detail="Email position not found")
    return db_email_position

@router.delete("/{email_position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_position(email_position_id: int, db: Session = Depends(get_db)):
    success = email_position_utils.delete_email_position(db, email_position_id=email_position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Email position not found")
    return None
