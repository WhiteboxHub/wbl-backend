from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import (
    RawPositionCreate, 
    RawPositionUpdate, 
    RawPositionOut,
    RawPositionBulkCreate,
    RawPositionBulkResponse
)
from fapi.utils import raw_position_utils

router = APIRouter(prefix="/raw-positions", tags=["Raw Positions"])

@router.get("/", response_model=List[RawPositionOut])
def read_raw_positions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return raw_position_utils.get_raw_positions(db, skip=skip, limit=limit)

@router.get("/{raw_position_id}", response_model=RawPositionOut)
def read_raw_position(raw_position_id: int, db: Session = Depends(get_db)):
    db_raw_position = raw_position_utils.get_raw_position(db, raw_position_id=raw_position_id)
    if not db_raw_position:
        raise HTTPException(status_code=404, detail="Raw position not found")
    return db_raw_position

@router.post("/", response_model=RawPositionOut, status_code=status.HTTP_201_CREATED)
def create_raw_position(raw_position: RawPositionCreate, db: Session = Depends(get_db)):
    return raw_position_utils.create_raw_position(db, raw_position=raw_position)

@router.post("/bulk", response_model=RawPositionBulkResponse)
async def create_raw_positions_bulk(
    bulk_data: RawPositionBulkCreate,
    db: Session = Depends(get_db)
):
    """Bulk insert raw positions"""
    return await raw_position_utils.insert_raw_positions_bulk(bulk_data.positions, db)

@router.put("/{raw_position_id}", response_model=RawPositionOut)
def update_raw_position(raw_position_id: int, raw_position: RawPositionUpdate, db: Session = Depends(get_db)):
    db_raw_position = raw_position_utils.update_raw_position(db, raw_position_id=raw_position_id, raw_position=raw_position)
    if not db_raw_position:
        raise HTTPException(status_code=404, detail="Raw position not found")
    return db_raw_position

@router.delete("/{raw_position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_raw_position(raw_position_id: int, db: Session = Depends(get_db)):
    success = raw_position_utils.delete_raw_position(db, raw_position_id=raw_position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Raw position not found")
    return None
