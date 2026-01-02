# vendor_utils.py-

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, ValidationError

from fapi.db.models import Vendor, VendorContactExtractsORM
from fapi.db.schemas import VendorCreate, VendorUpdate

logger = logging.getLogger(__name__)


# ---------- Helpers ----------
class _EmailValidator(BaseModel):
    email: EmailStr


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    try:
        # Validates & normalizes (lowercase) via pydantic
        valid = _EmailValidator(email=email.strip())
        return valid.email.lower()
    except ValidationError:
        logger.warning("Invalid email encountered while normalizing")
        return None


# ---------- CRUD: Vendor ----------
def get_all_vendors(db: Session) -> List[Vendor]:
    vendors = db.query(Vendor).order_by(Vendor.id.desc()).all()
    # Normalize/validate emails for outbound payload (does not persist changes)
    for v in vendors:
        v.email = _normalize_email(v.email)
    return vendors


def create_vendor(db: Session, vendor_data: VendorCreate) -> Vendor:
    payload = vendor_data.dict()
    payload["email"] = _normalize_email(payload.get("email"))

    # Optional: enforce uniqueness on email if present
    if payload.get("email"):
        dup = (
            db.query(Vendor)
            .filter(func.lower(Vendor.email) == payload["email"])
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Email already exists.")

    new_vendor = Vendor(**payload)
    db.add(new_vendor)
    try:
        db.commit()
        db.refresh(new_vendor)
        return new_vendor
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists.")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_vendor_handler(db: Session, vendor_id: int, update_data: VendorUpdate) -> Vendor:
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Normalize email if provided
    if "email" in fields:
        fields["email"] = _normalize_email(fields["email"])

        if fields["email"]:
            dup = (
                db.query(Vendor)
                .filter(func.lower(Vendor.email) == fields["email"], Vendor.id != vendor_id)
                .first()
            )
            if dup:
                raise HTTPException(status_code=400, detail="Email already exists.")

    try:
        for key, value in fields.items():
            setattr(vendor, key, value)
        db.commit()
        db.refresh(vendor)
        return vendor
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_vendor(db: Session, vendor_id: int) -> Dict[str, str]:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    try:
        db.delete(vendor)
        db.commit()
        return {"message": f"Vendor with ID {vendor_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


def delete_vendors_bulk(db: Session, vendor_ids: List[int]) -> int:
    try:
        deleted_count = db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Bulk delete failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")

