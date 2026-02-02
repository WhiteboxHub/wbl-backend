from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import PositionCreate, PositionUpdate, PositionOut
from fapi.utils import position_utils

router = APIRouter(prefix="/positions", tags=["Positions"], redirect_slashes=False)

@router.get("/", response_model=List[PositionOut])
def read_positions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return position_utils.get_positions(db, skip=skip, limit=limit)

@router.get("/search", response_model=List[PositionOut])
def search_positions(term: str, db: Session = Depends(get_db)):
    return position_utils.search_positions(db, term=term)

@router.get("/{position_id}", response_model=PositionOut)
def read_position(position_id: int, db: Session = Depends(get_db)):
    db_position = position_utils.get_position(db, position_id=position_id)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position

@router.post("/", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(position: PositionCreate, db: Session = Depends(get_db)):
    return position_utils.create_position(db, position=position)

@router.put("/{position_id}", response_model=PositionOut)
def update_position(position_id: int, position: PositionUpdate, db: Session = Depends(get_db)):
    db_position = position_utils.update_position(db, position_id=position_id, position=position)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position

@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, db: Session = Depends(get_db)):
    success = position_utils.delete_position(db, position_id=position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Position not found")
    return None
