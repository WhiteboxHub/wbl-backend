
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
#     bulk_delete_vendor_contacts,
#     bulk_delete_moved_contacts,
#     move_contacts_to_vendor,
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

# @router.post("/vendor_contact_extracts")
# async def create_vendor_contact_handler(contact: VendorContactExtractCreate):
#     await insert_vendor_contact(contact)
#     return JSONResponse(content={"message": "Vendor contact inserted successfully"})


# @router.put("/vendor_contact_extracts/{contact_id}")
# async def update_vendor_contact_handler(contact_id: int, update_data: VendorContactExtractUpdate):
#     fields = update_data.dict(exclude_unset=True)
#     if not fields:
#         raise HTTPException(status_code=400, detail="No data to update")

#     await update_vendor_contact(contact_id, fields)
#     return {"message": f"Vendor contact with ID {contact_id} updated successfully"}


# @router.delete("/vendor_contact_extracts/{contact_id}")
# async def delete_vendor_contact_handler(contact_id: int):
#     await delete_vendor_contact(contact_id)
#     return {"message": f"Vendor contact {contact_id} deleted successfully"}



# @router.delete("/vendor_contact_extracts/bulk-delete/moved")
# async def bulk_delete_moved_contacts_handler():
#     """
#     Bulk delete all contacts where moved_to_vendor = 1 (Yes)
#     """
#     try:
#         deleted_count = await bulk_delete_moved_contacts()
#         return {"message": f"Successfully deleted {deleted_count} contacts that were moved to vendor", "deleted_count": deleted_count}
#     except Exception as e:
#         logger.error(f"Error in bulk delete moved contacts: {e}")
#         raise




# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from fapi.db.database import get_db
# from fapi.utils.vendor_contact_utils import (
#     get_all_vendor_contacts,
#     create_vendor_contact,
#     delete_vendor_contact,
#     update_vendor_contact,
#     get_vendor_contact_by_id,
#     bulk_delete_moved_contacts,
# )

# router = APIRouter(prefix="/vendor_contact_extracts", tags=["Vendor Contact Extracts"])

# @router.get("/")
# async def read_vendor_contacts(db: Session = Depends(get_db)):
#     return await get_all_vendor_contacts(db)

# @router.post("/")
# async def create_contact(contact_data, db: Session = Depends(get_db)):
#     return await create_vendor_contact(contact_data, db)

# @router.delete("/{contact_id}")
# async def delete_contact(contact_id: int, db: Session = Depends(get_db)):
#     return await delete_vendor_contact(contact_id, db)

# @router.put("/{contact_id}")
# async def update_contact(contact_id: int, contact_data, db: Session = Depends(get_db)):
#     return await update_vendor_contact(contact_id, contact_data, db)

# @router.delete("/bulk/moved")
# async def bulk_delete_moved(db: Session = Depends(get_db)):
#     return await bulk_delete_moved_contacts(db)








from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import VendorContactExtractCreate
from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    create_vendor_contact,
    delete_vendor_contact,
    update_vendor_contact,
    bulk_delete_moved_contacts,
)

router = APIRouter(
    prefix="/vendor_contact_extracts",
    tags=["Vendor Contact Extracts"]
)

@router.get("/")
async def read_vendor_contacts(db: Session = Depends(get_db)):
    return await get_all_vendor_contacts(db)


@router.post("/")
async def create_contact(contact_data: VendorContactExtractCreate, db: Session = Depends(get_db)):
    return await create_vendor_contact(contact_data, db)


@router.put("/{contact_id}")
async def update_contact(contact_id: int, contact_data: VendorContactExtractCreate, db: Session = Depends(get_db)):
    return await update_vendor_contact(contact_id, contact_data, db)


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    return await delete_vendor_contact(contact_id, db)


@router.delete("/bulk/moved")
async def bulk_delete_moved(db: Session = Depends(get_db)):
    return await bulk_delete_moved_contacts(db)