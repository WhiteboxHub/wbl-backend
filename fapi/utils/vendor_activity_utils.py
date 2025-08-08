# -----------------------------
# fapi/utils/vendor_activity_utils.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fapi.db.models import DailyVendorActivityORM
from fapi.db.schemas import DailyVendorActivityCreate, DailyVendorActivityUpdate
from sqlalchemy.exc import SQLAlchemyError

def get_all_daily_activities(db: Session):
    return db.query(DailyVendorActivityORM).order_by(DailyVendorActivityORM.activity_id.desc()).all()

def create_daily_activity(db: Session, data: DailyVendorActivityCreate):
    activity = DailyVendorActivityORM(**data.dict())
    db.add(activity)
    try:
        db.commit()
        db.refresh(activity)
        return activity
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")

def update_daily_activity(db: Session, activity_id: int, data: DailyVendorActivityUpdate):
    fields = data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No update data provided")

    activity = db.query(DailyVendorActivityORM).filter(DailyVendorActivityORM.activity_id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    for key, value in fields.items():
        setattr(activity, key, value)

    try:
        db.commit()
        db.refresh(activity)
        return activity
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

def delete_daily_activity(db: Session, activity_id: int):
    activity = db.query(DailyVendorActivityORM).filter(DailyVendorActivityORM.activity_id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()
    return {"message": f"Daily vendor activity {activity_id} deleted successfully"}
