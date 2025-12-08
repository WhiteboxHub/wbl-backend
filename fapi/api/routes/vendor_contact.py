# # vendor_contact.py
# import logging
# from typing import List, Optional
# from fastapi import APIRouter, HTTPException, Depends, Query
# from sqlalchemy.orm import Session
# from fastapi.responses import JSONResponse

# from fapi.db.database import get_db
# from fapi.db.schemas import (
#     VendorContactExtract,
#     VendorContactExtractCreate,
#     VendorContactExtractUpdate,
# )
# from fapi.utils.vendor_contact_utils import (
#     get_all_vendor_contacts,
#     get_vendor_contact_by_id,
#     insert_vendor_contact,
#     update_vendor_contact,
#     delete_vendor_contact,
# )

# logger = logging.getLogger(__name__)
# router = APIRouter()

# @router.get("/vendor_contact_extracts", response_model=List[VendorContactExtract])
# async def read_vendor_contact_extracts(db: Session = Depends(get_db)):

#     try:
#         return await get_all_vendor_contacts(db)
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error fetching vendor contacts: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")

# @router.get("/vendor_contact_extracts/{contact_id}", response_model=VendorContactExtract)
# async def read_vendor_contact_by_id(contact_id: int, db: Session = Depends(get_db)):
#     try:
#         return await get_vendor_contact_by_id(contact_id, db)
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error fetching vendor contact {contact_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")

# @router.post("/vendor_contact", response_model=VendorContactExtract)
# async def create_vendor_contact_handler(
#     contact: VendorContactExtractCreate, 
#     db: Session = Depends(get_db)
# ):
#     try:
#         result = await insert_vendor_contact(contact, db)
#         return result
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error creating vendor contact: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")

# @router.put("/vendor_contact/{contact_id}", response_model=VendorContactExtract)
# async def update_vendor_contact_handler(
#     contact_id: int, 
#     update_data: VendorContactExtractUpdate, 
#     db: Session = Depends(get_db)
# ):
#     """Update existing vendor contact"""
#     try:
#         return await update_vendor_contact(contact_id, update_data, db)
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating vendor contact {contact_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")

# @router.delete("/vendor_contact/{contact_id}")
# async def delete_vendor_contact_handler(contact_id: int, db: Session = Depends(get_db)):
#     try:
#         result = await delete_vendor_contact(contact_id, db)
#         return result
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting vendor contact {contact_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")










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





