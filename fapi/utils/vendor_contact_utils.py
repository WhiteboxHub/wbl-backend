# vendor_contact_utils.py
import logging
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from fapi.db.models import VendorContactExtractsORM
from fapi.db.schemas import (
    VendorContactExtract,
    VendorContactExtractCreate,
    VendorContactExtractUpdate,
)

logger = logging.getLogger(__name__)


async def get_all_vendor_contacts(db: Session) -> List[VendorContactExtract]:
    """Fetch all vendor contacts"""
    try:
        result = db.query(VendorContactExtractsORM).all()
        return result
    except Exception as e:
        logger.error(f"Error fetching all vendor contacts: {e}")
        raise HTTPException(status_code=500, detail="Error fetching vendor contacts")


async def get_vendor_contact_by_id(contact_id: int, db: Session) -> VendorContactExtract:
    """Fetch a specific vendor contact by ID"""
    try:
        contact = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id == contact_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Vendor contact not found")
        return contact
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor contact by ID: {e}")
        raise HTTPException(status_code=500, detail="Error fetching vendor contact")


async def insert_vendor_contact(contact: VendorContactExtractCreate, db: Session) -> VendorContactExtract:
    """Create a new vendor contact"""
    try:
        new_contact = VendorContactExtractsORM(**contact.dict())
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        return new_contact
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating vendor contact: {e}")
        raise HTTPException(status_code=500, detail="Error creating vendor contact")


async def update_vendor_contact(
    contact_id: int, 
    update_data: VendorContactExtractUpdate, 
    db: Session
) -> VendorContactExtract:
    """Update an existing vendor contact"""
    try:
        contact = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id == contact_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Vendor contact not found")
        
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(contact, key, value)
        
        db.commit()
        db.refresh(contact)
        return contact
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating vendor contact: {e}")
        raise HTTPException(status_code=500, detail="Error updating vendor contact")


async def delete_vendor_contact(contact_id: int, db: Session) -> dict:
    """Delete a vendor contact"""
    try:
        contact = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id == contact_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Vendor contact not found")
        
        db.delete(contact)
        db.commit()
        return {"message": "Vendor contact deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting vendor contact: {e}")
        raise HTTPException(status_code=500, detail="Error deleting vendor contact")

