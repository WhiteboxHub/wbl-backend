from sqlalchemy.orm import Session
from fastapi import HTTPException
from fapi.db.models import Vendor, VendorTypeEnum
from fapi.db.schemas import VendorCreate

async def insert_vendor(db: Session, vendor_data: VendorCreate):
    try:
        if vendor_data.email:
            existing = db.query(Vendor).filter(Vendor.email == vendor_data.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="A request with this email already exists.")

        vendor = Vendor(
            full_name=vendor_data.full_name,
            phone_number=vendor_data.phone_number,
            email=vendor_data.email,
            city=vendor_data.city,
            postal_code=vendor_data.postal_code,
            address=vendor_data.address,
            country=vendor_data.country,
            type=VendorTypeEnum.contact_from_ip
        )
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to process your request. Internal Error")
