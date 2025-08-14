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
        logger.warning(f"Invalid email encountered while normalizing: {email!r}")
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


# ---------- Move: vendor_contact_extracts → vendor ----------
def get_contact_info_mark_move_to_vendor_true(db: Session, contact_id: int) -> Dict[str, Any]:
    """
    Fetch contact. If not already moved, set moved_to_vendor=1 (True) and return contact data.
    If already moved, return a signal so the API can short-circuit (same as your lead flow).
    """
    contact = (
        db.query(VendorContactExtractsORM)
        .filter(VendorContactExtractsORM.id == contact_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.moved_to_vendor:
        logger.info(f"Contact already moved: {contact.id}")
        return {"message": "Already moved to vendor", "contact_id": contact.id, "already_moved": True}

    contact.moved_to_vendor = True
    try:
        db.commit()
        db.refresh(contact)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark moved: {str(e)}")

    # Return a clean dict for the next step
    data = contact.__dict__.copy()
    data.pop("_sa_instance_state", None)
    return data


def create_vendor_from_contact(db: Session, contact: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a VendorORM row from a vendor_contact_extracts row dict.
    Duplicate prevention:
      - by normalized email (if present)
      - by linkedin_id (if present)
    """
    email_norm = _normalize_email(contact.get("email"))
    linkedin_id = contact.get("linkedin_id")

    # Duplicate check (email OR linkedin_id)
    q = db.query(VendorORM)
    if email_norm and linkedin_id:
        existing = q.filter(
            (func.lower(VendorORM.email) == email_norm) |
            (VendorORM.linkedin_id == linkedin_id)
        ).first()
    elif email_norm:
        existing = q.filter(func.lower(VendorORM.email) == email_norm).first()
    elif linkedin_id:
        existing = q.filter(VendorORM.linkedin_id == linkedin_id).first()
    else:
        existing = None

    if existing:
        return {
            "message": "Vendor already exists",
            "vendor_id": existing.id,
            "success": False
        }

    new_vendor = VendorORM(
        full_name=contact.get("full_name"),
        email=email_norm,
        phone_number=contact.get("phone"),
        secondary_phone=contact.get("secondary_phone"),
        linkedin_id=linkedin_id,
        company_name=contact.get("company_name"),
        location=contact.get("location"),
        # Defaults mirroring your trigger
        type="client",
        note=None,
        city=None,
        postal_code=None,
        address=None,
        country=None,
        # vendor_type="client",
        status="prospect",
        linkedin_connected="NO",
        intro_email_sent="NO",
        intro_call="NO",
        created_at=datetime.utcnow(),
    )

    db.add(new_vendor)
    try:
        db.commit()
        db.refresh(new_vendor)
        return {
            "message": "Vendor created successfully",
            "vendor_id": new_vendor.id,
            "success": True
        }
    except IntegrityError:
        db.rollback()
        # If DB unique constraints exist on email / linkedin_id, this captures races
        raise HTTPException(status_code=400, detail="Vendor with same email or LinkedIn ID already exists")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating vendor: {str(e)}")


def check_and_reset_moved_to_vendor(db: Session, contact_id: int) -> Dict[str, Any]:
    """
    Reset moved_to_vendor to 0 (False) for a contact (used when rolling back deletion).
    Returns the contact's email & phone so delete can target the right Vendor.
    """
    contact = (
        db.query(VendorContactExtractsORM)
        .filter(VendorContactExtractsORM.id == contact_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Always reset to False (even if already False, it's idempotent)
    contact.moved_to_vendor = False
    try:
        db.commit()
        db.refresh(contact)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset flag: {str(e)}")

    return {"email": contact.email, "phone": contact.phone}


def delete_vendor_by_email_and_phone(db: Session, email: str, phone: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete vendor(s) by email (case-insensitive).
    If multiple vendors share the same email, `phone` is required to disambiguate.
    """
    email_norm = _normalize_email(email)
    if not email_norm:
        raise HTTPException(status_code=400, detail="Invalid email")

    vendors = db.query(VendorORM).filter(func.lower(VendorORM.email) == email_norm).all()

    if not vendors:
        raise HTTPException(status_code=404, detail="No vendor found with the given email")

    if len(vendors) == 1:
        try:
            db.delete(vendors[0])
            db.commit()
            return {"message": "Vendor deleted successfully", "vendor_id": vendors[0].id, "success": True}
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    # Multiple found → need phone
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Multiple vendors found with this email. Provide phone to disambiguate."
        )

    match = next((v for v in vendors if v.phone_number == phone), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail="No vendor found with the provided email and phone combination."
        )

    try:
        db.delete(match)
        db.commit()
        return {"message": "Vendor deleted successfully", "vendor_id": match.id, "success": True}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")