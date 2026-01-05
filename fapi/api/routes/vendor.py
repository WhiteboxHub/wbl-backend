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
    try:
        return vendor_utils.get_all_vendors(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendors: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/vendors/metrics")
def get_vendor_metrics_endpoint(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return get_vendor_stats(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/vendors", response_model=Vendor)
def create_vendor(
    vendor: VendorCreate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return vendor_utils.create_vendor(db, vendor)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/vendors/{vendor_id}", response_model=Vendor)
def update_vendor_route(
    vendor_id: int,
    update_data: VendorUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return vendor_utils.update_vendor_handler(db, vendor_id, update_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vendor {vendor_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/vendors/{vendor_id}")
def delete_vendor(
    vendor_id: int = Path(...), 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return vendor_utils.delete_vendor(db, vendor_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vendor {vendor_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/vendors/bulk-delete")
async def bulk_delete_vendors(
    vendor_ids: List[int],
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Bulk delete vendors by IDs
    
    Uses POST with request body to avoid URL length limits for large batches.
    Processes in batches of 500 to avoid database locks and timeouts.
    """
    try:
        if not vendor_ids:
            raise HTTPException(status_code=400, detail="No vendor IDs provided")
        
        logger.info(f"Bulk delete request received with {len(vendor_ids)} vendor IDs")
        
        total_deleted = 0
        batch_size = 500
        
        # Process in batches to avoid database locks and timeouts
        for i in range(0, len(vendor_ids), batch_size):
            batch = vendor_ids[i:i + batch_size]
            deleted_count = vendor_utils.delete_vendors_bulk(db, batch)
            total_deleted += deleted_count
        
        logger.info(f"Successfully deleted {total_deleted} vendors")
        
        return {
            "deleted": total_deleted,
            "message": f"Successfully deleted {total_deleted} vendors"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

