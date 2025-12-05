# vendor.py
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import VendorCreate, VendorUpdate, Vendor
from fapi.utils import vendor_utils
from fapi.utils.avatar_dashboard_utils import get_vendor_stats
logger = logging.getLogger(__name__)
router = APIRouter()

# Use HTTPBearer for Swagger auth
security = HTTPBearer()


# ---------- CRUD: Vendor ----------
@router.get("/vendors", response_model=List[Vendor])
def read_vendors(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return vendor_utils.get_all_vendors(db)

@router.get("/vendors/metrics")
def get_vendor_metrics_endpoint(
    db: Session = Depends(get_db),
):
    return get_vendor_stats(db)

@router.post("/vendors", response_model=Vendor)
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    return vendor_utils.create_vendor(db, vendor)


@router.put("/vendors/{vendor_id}", response_model=Vendor)
def update_vendor_route(
    vendor_id: int,
    update_data: VendorUpdate,
    db: Session = Depends(get_db),
):
    logger.info("Update schema received: %s", update_data.dict(exclude_unset=True))
    return vendor_utils.update_vendor_handler(db, vendor_id, update_data)


@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int = Path(...), db: Session = Depends(get_db)):
    return vendor_utils.delete_vendor(db, vendor_id)

