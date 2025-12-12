# vendor_contact.py
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from fapi.db.database import get_db
from fapi.db.schemas import (
    VendorContactExtract,
    VendorContactExtractCreate,
    VendorContactExtractUpdate,
)
from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    get_vendor_contact_by_id,
    insert_vendor_contact,
    update_vendor_contact,
    delete_vendor_contact,
    move_all_vendor_contacts_to_vendor,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/vendor_contact_extracts", response_model=List[VendorContactExtract])
async def read_vendor_contact_extracts(db: Session = Depends(get_db)):

    try:
        return await get_all_vendor_contacts(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor contacts: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/vendor_contact_extracts/", response_model=List[VendorContactExtract], include_in_schema=False)
async def read_vendor_contact_extracts_slash(db: Session = Depends(get_db)):
    """Get all vendor contact extracts (trailing slash support)"""
    return await read_vendor_contact_extracts(db)

@router.get("/vendor_contact_extracts/{contact_id}", response_model=VendorContactExtract)
async def read_vendor_contact_by_id_handler(contact_id: int, db: Session = Depends(get_db)):
    try:
        return await get_vendor_contact_by_id(contact_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/vendor_contact_extracts", response_model=VendorContactExtract)
async def create_vendor_contact_handler(
    contact: VendorContactExtractCreate, 
    db: Session = Depends(get_db)
):
    try:
        result = await insert_vendor_contact(contact, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor contact: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.put("/vendor_contact_extracts/bulk/move-all", status_code=200)
async def move_all_vendor_contacts_handler(db: Session = Depends(get_db)):
    """Move all vendor contact extracts to vendor table"""
    try:
        return await move_all_vendor_contacts_to_vendor(db)
    except Exception as e:
        logger.error(f"Error migrating vendor contacts: {e}")
        raise HTTPException(status_code=500, detail="Error migrating vendor contacts")

@router.put("/vendor_contact_extracts/bulk/move-all/", status_code=200, include_in_schema=False)
async def move_all_vendor_contacts_handler_slash(db: Session = Depends(get_db)):
    """Move all vendor contact extracts to vendor table (trailing slash support)"""
    return await move_all_vendor_contacts_handler(db)

@router.put("/vendor_contact_extracts/{contact_id}", response_model=VendorContactExtract)
async def update_vendor_contact_handler(
    contact_id: int, 
    update_data: VendorContactExtractUpdate, 
    db: Session = Depends(get_db)
):
    """Update existing vendor contact"""
    try:
        return await update_vendor_contact(contact_id, update_data, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vendor contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.put("/vendor_contact_extracts/{contact_id}/", response_model=VendorContactExtract, include_in_schema=False)
async def update_vendor_contact_handler_slash(
    contact_id: int, 
    update_data: VendorContactExtractUpdate, 
    db: Session = Depends(get_db)
):
    """Update existing vendor contact (trailing slash support)"""
    return await update_vendor_contact_handler(contact_id, update_data, db)

@router.delete("/vendor_contact_extracts/{contact_id}")
async def delete_vendor_contact_handler(contact_id: int, db: Session = Depends(get_db)):
    try:
        result = await delete_vendor_contact(contact_id, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vendor contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

