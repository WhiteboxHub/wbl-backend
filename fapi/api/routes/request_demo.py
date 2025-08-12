# wbl-backend/fapi/api/routes/request_demo.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.schemas import VendorCreate, VendorResponse
from fapi.utils.request_demo_utils import insert_vendor
from fapi.utils.email_utils import send_request_demo_emails  

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/request-demo", response_model=VendorResponse)
async def create_vendor_request_demo(vendor: VendorCreate, db: Session = Depends(get_db)):
    saved_vendor = await insert_vendor(db, vendor)
    
    # Use your already implemented async email sender
    await send_request_demo_emails(
        name=saved_vendor.full_name,
        email=saved_vendor.email,
        phone=saved_vendor.phone_number or "N/A",
        address=saved_vendor.address or ""
    )

    return {"message": "Vendor added successfully from request demo"}
