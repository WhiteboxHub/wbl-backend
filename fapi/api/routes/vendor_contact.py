

# backend/fapi/api/routes/vendor_contact_extracts.py
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    update_vendor_contact,
    insert_vendor_contact,
    move_all_contacts_to_vendor,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["VendorContactExtracts"])


@router.get("/vendor_contact_extracts/")
async def read_vendor_contact_extracts():
    try:
        return await get_all_vendor_contacts()
    except Exception as e:
        logger.error("Error fetching vendor contacts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vendor_contact_extracts/")
async def create_vendor_contact_handler(contact: dict):
    try:
        await insert_vendor_contact(contact)
        return JSONResponse(content={"message": "Created successfully"})
    except Exception as e:
        logger.error("Error creating contact: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/vendor_contact_extracts/{contact_id}/")
async def update_vendor_contact_handler(contact_id: int, request: Request):
    try:
        update_data = await request.json()
        excluded_fields = {"id", "created_at"}
        fields = {k: v for k, v in update_data.items() if k not in excluded_fields}

        if not fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        await update_vendor_contact(contact_id, fields)
        return {"message": "Contact updated successfully", "contact_id": contact_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating contact %s: %s", contact_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update contact: {str(e)}")


@router.put("/vendor_contact_extracts/bulk/move-all/")
async def move_all_vendor_contacts_handler():
    try:
        result = await move_all_contacts_to_vendor()
        return {
            "message": result.get("message", ""),
            "inserted": result.get("inserted", 0),
            "moved_count": result.get("moved_count", result.get("moved_count", 0)),
            "success": result.get("success", False),
        }
    except Exception as e:
        logger.error("Move all failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Move all operation failed: {str(e)}")





