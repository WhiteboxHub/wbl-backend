import logging
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fapi.db.schemas import (
    VendorContactExtract,
    VendorContactExtractCreate,
    VendorContactExtractUpdate,
)
from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    insert_vendor_contact,
    update_vendor_contact,
    delete_vendor_contact,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/vendor_contact_extracts", response_model=List[VendorContactExtract])
async def read_vendor_contact_extracts():
    """
    Public endpoint to fetch all vendor contact extracts.
    Authorization removed.
    """
    try:
        return await get_all_vendor_contacts()
    except Exception as e:
        logger.error(f"Error fetching vendor contacts: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/vendor_contact")
async def create_vendor_contact_handler(contact: VendorContactExtractCreate):
    await insert_vendor_contact(contact)
    return JSONResponse(content={"message": "Vendor contact inserted successfully"})


@router.put("/vendor_contact/{contact_id}")
async def update_vendor_contact_handler(contact_id: int, update_data: VendorContactExtractUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    await update_vendor_contact(contact_id, fields)
    return {"message": f"Vendor contact with ID {contact_id} updated successfully"}


@router.delete("/vendor_contact/{contact_id}")
async def delete_vendor_contact_handler(contact_id: int):
    await delete_vendor_contact(contact_id)
    return {"message": f"Vendor contact {contact_id} deleted successfully"}
 
