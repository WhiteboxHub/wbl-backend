#vendor.py
import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from fapi.db.database import SessionLocal, get_db
from fapi.db.schemas import VendorCreate, VendorUpdate, Vendor
from fapi.utils import vendor_utils

logger = logging.getLogger(__name__)
router = APIRouter()




# ---------- CRUD: Vendor ----------
@router.get("/vendors", response_model=List[Vendor])
def read_vendors(db: Session = Depends(get_db)):
    return vendor_utils.get_all_vendors(db)


@router.post("/vendors", response_model=Vendor)
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    return vendor_utils.create_vendor(db, vendor)


@router.put("/vendors/{vendor_id}", response_model=Vendor)
def update_vendor_route(
    vendor_id: int,
    update_data: VendorUpdate,
    db: Session = Depends(get_db),
):
    logger.info("Update schema received: %s", update_data.dict(exclude_unset=True))
    return vendor_utils.update_vendor_handler(db, vendor_id, update_data)


@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int = Path(...), db: Session = Depends(get_db)):
    return vendor_utils.delete_vendor(db, vendor_id)


# ---------- Move: vendor_contact_extracts → vendor ----------
@router.post("/vendor/movetovendor/{contact_id}")
def move_to_vendor_endpoint(contact_id: int, db: Session = Depends(get_db)):
    """
    Mirrors your leads→candidates flow:
    1) Mark vendor_contact_extracts.moved_to_vendor = 1 (if not already moved).
    2) Create vendor from contact with duplicate checks on email/linkedin_id.
    """
    logger.info("Starting move_to_vendor for contact_id: %s", contact_id)

    try:
        contact_data = vendor_utils.get_contact_info_mark_move_to_vendor_true(db, contact_id)

        if contact_data.get("already_moved", False):
            logger.info("Contact already moved: contact_id=%s", contact_data["contact_id"])
            raise HTTPException(status_code=400, detail=contact_data["message"])

        creation = vendor_utils.create_vendor_from_contact(db, contact_data)

        if creation.get("success"):
            logger.info("Vendor created successfully: vendor_id=%s", creation["vendor_id"])
            return {"message": "Contact moved to vendor successfully", "vendor_id": creation["vendor_id"]}

        # Duplicate case (vendor already exists)
        return {"message": creation["message"], "vendor_id": creation.get("vendor_id")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in move_to_vendor: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/vendor/movetovendor/{contact_id}")
def delete_vendor_move(contact_id: int, db: Session = Depends(get_db)):
    """
    Rollback helper:
    - Reset moved_to_vendor to 0 on the contact.
    - Delete the vendor by email (and phone if needed).
    """
    try:
        contact_info = vendor_utils.check_and_reset_moved_to_vendor(db, contact_id)
        res = vendor_utils.delete_vendor_by_email_and_phone(
            db,
            email=contact_info["email"],
            phone=contact_info.get("phone"),
        )
        if res.get("success"):
            return {"message": "Vendor deleted successfully", "vendor_id": res["vendor_id"]}
        raise HTTPException(status_code=500, detail="Failed to delete vendor")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in delete_vendor_move: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")