from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import SessionLocal, get_db
from fapi.db.schemas import DailyVendorActivity, DailyVendorActivityCreate, DailyVendorActivityUpdate
from fapi.utils import vendor_activity_utils

router = APIRouter()



@router.get("/daily_vendor_activities", response_model=List[DailyVendorActivity])
def read_all_activities(db: Session = Depends(get_db)):
    return vendor_activity_utils.get_all_daily_activities(db)

@router.post("/daily_vendor_activities")
def create_activity(data: DailyVendorActivityCreate, db: Session = Depends(get_db)):
    return vendor_activity_utils.create_daily_activity(db, data)

@router.put("/daily_vendor_activities/{activity_id}")
def update_activity(activity_id: int, data: DailyVendorActivityUpdate, db: Session = Depends(get_db)):
    return vendor_activity_utils.update_daily_activity(db, activity_id, data)

@router.delete("/daily_vendor_activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    return vendor_activity_utils.delete_daily_activity(db, activity_id)
