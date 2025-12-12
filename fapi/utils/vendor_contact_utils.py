# vendor_contact_utils.py
import logging
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from fapi.db.models import VendorContactExtractsORM, Vendor, VendorTypeEnum
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


async def move_all_vendor_contacts_to_vendor(db: Session) -> dict:
    """
    Move all non-moved vendor contacts to the Vendor table.
    Checks for existing emails to avoid duplicates.
    """
    try:
        # Get all extracts that haven't been moved
        extracts = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.moved_to_vendor == False
        ).all()

        moved_count = 0
        updated_count = 0

        for extract in extracts:
            # Check if vendor with this email already exists
            existing_vendor = None
            if extract.email:
                existing_vendor = db.query(Vendor).filter(Vendor.email == extract.email).first()

            if existing_vendor:
                # Optional: Update existing vendor or just skip?
                # For now, let's skip creation but mark extract as moved to avoid re-processing
                extract.moved_to_vendor = True
                updated_count += 1
            else:
                # Create new Vendor
                new_vendor = Vendor(
                    full_name=extract.full_name,
                    email=extract.email,
                    phone_number=extract.phone,
                    company_name=extract.company_name,
                    location=extract.location,
                    linkedin_id=extract.linkedin_id,
                    linkedin_internal_id=extract.linkedin_internal_id,
                    type=VendorTypeEnum.client,  # Default type
                    status="prospect",          # Default status
                    # Map other fields as needed
                )
                db.add(new_vendor)
                extract.moved_to_vendor = True
                moved_count += 1
        
        db.commit()
        return {"moved_count": moved_count, "updated_count": updated_count}

    except Exception as e:
        db.rollback()
        logger.error(f"Error moving vendor contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Error moving vendor contacts: {str(e)}")
