# # fapi/utils/vendor_utils.py
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, ValidationError

from fapi.db.models import VendorORM
from fapi.db.schemas import VendorCreate, VendorUpdate

class _EmailValidator(BaseModel):
    email: EmailStr

def get_all_vendors(db: Session) -> List[VendorORM]:
    vendors = db.query(VendorORM).order_by(VendorORM.id.desc()).all()
    for vendor in vendors:
        try:
            if vendor.email:
                valid = _EmailValidator(email=vendor.email)
                vendor.email = valid.email
        except ValidationError:
            print(f"⚠️ Invalid email found: '{vendor.email}' (vendor ID: {vendor.id})")
            vendor.email = None
    return vendors

def create_vendor(db: Session, vendor_data: VendorCreate):
    new_vendor = VendorORM(**vendor_data.dict())
    db.add(new_vendor)
    try:
        db.commit()
        db.refresh(new_vendor)
        return new_vendor
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists.")

def update_vendor_handler(db: Session, vendor_id: int, update_data: VendorUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    vendor = db.query(VendorORM).filter(VendorORM.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    try:
        for key, value in fields.items():
            setattr(vendor, key, value)
        db.commit()
        db.refresh(vendor)
        return vendor
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

def delete_vendor(db: Session, vendor_id: int):
    vendor = db.query(VendorORM).filter(VendorORM.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    db.delete(vendor)
    db.commit()
    return {"message": f"Vendor with ID {vendor_id} deleted successfully"}
