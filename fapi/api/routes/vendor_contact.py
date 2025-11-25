

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    update_vendor_contact,
    insert_vendor_contact,
    move_all_contacts_to_vendor,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------
# GET ALL CONTACTS
# ---------------------------------------------------------
@router.get("/vendor_contact_extracts")
async def read_vendor_contact_extracts():
    """Get all vendor contact extracts"""
    try:
        return await get_all_vendor_contacts()
    except Exception as e:
        logger.error(f"Error fetching vendor contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# CREATE ONE CONTACT
# ---------------------------------------------------------
@router.post("/vendor_contact_extracts")
async def create_vendor_contact_handler(contact: dict):
    """Create a new vendor contact"""
    try:
        await insert_vendor_contact(contact)
        return JSONResponse(content={"message": "Created successfully"})
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# UPDATE ONE CONTACT - IMPROVED
# ---------------------------------------------------------
@router.put("/vendor_contact_extracts/{contact_id}")
async def update_vendor_contact_handler(contact_id: int, request: Request):
    """Update a vendor contact"""
    try:
        # Get the JSON body
        update_data = await request.json()
        
        logger.info(f"Received update request for contact {contact_id}: {update_data}")
        
        # Filter out fields that shouldn't be updated
        excluded_fields = {'id', 'created_at'}
        fields = {
            k: v for k, v in update_data.items() 
            if k not in excluded_fields
        }

        if not fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        await update_vendor_contact(contact_id, fields)

        return {
            "message": "Contact updated successfully",
            "contact_id": contact_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact {contact_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update contact: {str(e)}")


# ---------------------------------------------------------
# MOVE ALL CONTACTS TO VENDOR
# ---------------------------------------------------------
@router.put("/vendor_contact_extracts/bulk/move-all")
async def move_all_vendor_contacts_handler():
    """
    Move ALL contacts to vendor table where moved_to_vendor = 0
    and mark them as moved_to_vendor = 1
    """
    try:
        result = await move_all_contacts_to_vendor()
        return {
            "message": result["message"],
            "inserted": result["inserted"],
            "updated_count": result["moved_count"],
            "success": result["success"]
        }
    except Exception as e:
        logger.error(f"Move all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Move all operation failed: {str(e)}")