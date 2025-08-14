from sqlalchemy.orm import Session
from fapi.db.models import VendorORM
from fapi.db.schemas import VendorCreate
from fastapi import HTTPException

async def insert_vendor(db: Session, vendor_data: VendorCreate):
    try:
        # Check if the email already exists
        if vendor_data.email:
            existing_vendor = db.query(VendorORM).filter(VendorORM.email == vendor_data.email).first()
            if existing_vendor:
                raise HTTPException(status_code=400,detail="A request with this email already exists.")

        vendor = VendorORM(
            full_name=vendor_data.full_name,
            phone_number=vendor_data.phone_number,
            email=vendor_data.email,
            city=vendor_data.city,
            postal_code=vendor_data.postal_code,
            address=vendor_data.address,
            country=vendor_data.country,
            type="IP_REQUEST_DEMO"
        )
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor

    except HTTPException:
        
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to process your request at this time. Please try again later."
        )
