import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import HRContactCreate, HRContactUpdate, HRContact
from fapi.utils import hr_contact_utils

logger = logging.getLogger(__name__)
router = APIRouter()

# Use HTTPBearer for Swagger auth
security = HTTPBearer()

@router.get("/hr-contacts", response_model=List[HRContact])
def read_hr_contacts(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return hr_contact_utils.get_all_hr_contacts(db)
    except Exception as e:
        logger.error(f"Error fetching HR contacts: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/hr-contacts", response_model=HRContact)
def create_hr_contact(
    contact: HRContactCreate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return hr_contact_utils.create_hr_contact(db, contact)
    except Exception as e:
        logger.error(f"Error creating HR contact: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.put("/hr-contacts/{contact_id}", response_model=HRContact)
def update_hr_contact_route(
    contact_id: int,
    update_data: HRContactUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return hr_contact_utils.update_hr_contact_handler(db, contact_id, update_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating HR contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/hr-contacts/{contact_id}")
def delete_hr_contact(
    contact_id: int = Path(...), 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        return hr_contact_utils.delete_hr_contact(db, contact_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting HR contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/hr-contacts/bulk-delete")
async def bulk_delete_hr_contacts(
    contact_ids: List[int],
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        if not contact_ids:
            raise HTTPException(status_code=400, detail="No HR contact IDs provided")
        
        logger.info(f"Bulk delete HR contacts request received with {len(contact_ids)} IDs")
        total_deleted = hr_contact_utils.delete_hr_contacts_bulk(db, contact_ids)
        logger.info(f"Successfully deleted {total_deleted} HR contacts")
        
        return {
            "deleted": total_deleted,
            "message": f"Successfully deleted {total_deleted} HR contacts"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete HR contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
