from fapi.db import get_all_vendor_contacts,insert_vendor_contact, update_vendor_contact,delete_vendor_contact , get_all_vendors ,insert_vendor , update_vendor , delete_vendor_by_id_sync , get_all_daily_vendor_activities, insert_daily_vendor_activity ,update_daily_vendor_activity, delete_daily_vendor_activity
from fapi.models import VendorContactExtractCreate,VendorContactExtractCreate,VendorContactExtractCreate,VendorContactExtractUpdate,VendorCreate , Vendor ,VendorUpdate,DailyVendorActivityCreate,DailyVendorActivityUpdate
from fastapi import HTTPException
import asyncio

#vendor_contact_extract
async def get_vendor_contacts_handler():
    return await get_all_vendor_contacts()


async def insert_vendor_contact_handler(contact: VendorContactExtractCreate):
    await insert_vendor_contact(contact)


async def update_vendor_contact_handler(contact_id: int, update_data: VendorContactExtractUpdate):
    fields = update_data.dict(exclude_unset=True)
    await update_vendor_contact(contact_id, fields)


async def delete_vendor_contact_handler(contact_id: int):
    await delete_vendor_contact(contact_id)

#vendor-table
async def get_vendors_handler():
    return await get_all_vendors()

async def create_vendor_handler(vendor: VendorCreate) -> Vendor:
    vendor_data = vendor.dict(exclude_unset=True)
    inserted_row = await insert_vendor(vendor_data)
    return Vendor(**inserted_row) 


async def update_vendor_handler(vendor_id: int, update_data: VendorUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    try:
        await update_vendor(vendor_id, fields)
        return {"message": f"Vendor with ID {vendor_id} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    

async def delete_vendor_handler(vendor_id: int):
    print(f"Attempting to delete vendor with ID: {vendor_id}")
    try:
        deleted = await asyncio.to_thread(delete_vendor_by_id_sync, vendor_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Vendor not found")
        return {"message": f"Vendor with ID {vendor_id} deleted successfully"}
    except Exception as e:
        print("Internal Server Error in handler:", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

async def fetch_all_daily_vendor_activities():
    try:
        return await get_all_daily_vendor_activities()
    except Exception as e:
        print("Actual DB error:", e)  # <-- Add this line
        raise HTTPException(status_code=500, detail="Failed to fetch daily vendor activities")


async def add_daily_vendor_activity(activity: DailyVendorActivityCreate):
    try:
        await insert_daily_vendor_activity(activity)
    except Exception as e:
        print("Insert Error:", e)
        raise HTTPException(status_code=500, detail="Failed to insert daily vendor activity")
    
async def modify_daily_vendor_activity(activity_id: int, data: DailyVendorActivityUpdate):
    try:
        fields = {k: v for k, v in data.dict().items() if v is not None}
        if not fields:
            raise HTTPException(status_code=400, detail="No data provided for update")
        await update_daily_vendor_activity(activity_id, fields)
    except Exception as e:
        print("Update error:", e)
        raise HTTPException(status_code=500, detail="Failed to update daily vendor activity")

async def remove_daily_vendor_activity(activity_id: int):
    try:
        await delete_daily_vendor_activity(activity_id)
    except Exception as e:
        print("Delete error:", e)
        raise HTTPException(status_code=500, detail="Failed to delete daily vendor activity")