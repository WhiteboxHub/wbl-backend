import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import VendorContactExtractsORM, Vendor
from fapi.db.schemas import VendorContactExtractCreate, VendorContactExtractUpdate

logger = logging.getLogger(__name__)

async def get_all_vendor_contacts(db: Session) -> List[VendorContactExtractsORM]:

    try:
        contacts = db.query(VendorContactExtractsORM).order_by(VendorContactExtractsORM.id.desc()).all()
        return contacts
    except SQLAlchemyError as e:
        logger.error(f"Error fetching vendor contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching vendor contacts: {str(e)}")

async def get_vendor_contact_by_id(contact_id: int, db: Session) -> VendorContactExtractsORM:
 
    contact = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Vendor contact not found")
    return contact

async def insert_vendor_contact(contact: VendorContactExtractCreate, db: Session) -> VendorContactExtractsORM:
    
    try:
       
        db_contact = VendorContactExtractsORM(
            full_name=contact.full_name,
            source_email=contact.source_email,
            email=contact.email,
            phone=contact.phone,
            linkedin_id=contact.linkedin_id,
            company_name=contact.company_name,
            location=contact.location,
            moved_to_vendor=False,
            extraction_date=contact.extraction_date,
            linkedin_internal_id=contact.linkedin_internal_id,
            notes=contact.notes,
            job_source=contact.job_source
        )
        
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        return db_contact
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate entry or integrity error")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Insert error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Insert error: {str(e)}")

async def update_vendor_contact(contact_id: int, update_data: VendorContactExtractUpdate, db: Session) -> VendorContactExtractsORM:
    """Update vendor contact using SQLAlchemy ORM"""
    if not update_data.dict(exclude_unset=True):
        raise HTTPException(status_code=400, detail="No data to update")


    db_contact = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Vendor contact not found")

    try:
      
        update_fields = update_data.dict(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(db_contact, field, value)
        
        db.commit()
        db.refresh(db_contact)
        return db_contact
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate entry or integrity error")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Update error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

async def delete_vendor_contact(contact_id: int, db: Session) -> dict:
    """Delete vendor contact using SQLAlchemy ORM"""
    db_contact = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Vendor contact not found")

    try:
        db.delete(db_contact)
        db.commit()
        return {"message": f"Vendor contact with ID {contact_id} deleted successfully"}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")

async def move_contacts_to_vendor(contact_ids: Optional[List[int]] = None, db: Session = None) -> dict:
    """Move vendor contacts to main vendor table using SQLAlchemy ORM"""
    try:
    
        query = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.moved_to_vendor == False)
        
        if contact_ids:
            query = query.filter(VendorContactExtractsORM.id.in_(contact_ids))
        
        contacts_to_move = query.all()
        
        if not contacts_to_move:
            return {
                "inserted": 0,
                "skipped_already_moved": 0,
                "count": 0,
                "message": "No contacts to move or all selected contacts are already moved"
            }

        inserted = 0
        skipped_already_moved = 0
        moved_ids = []

        for contact in contacts_to_move:
          
            existing_vendor = db.query(Vendor).filter(
                or_(
                    Vendor.email == contact.email,
                    Vendor.linkedin_id == contact.linkedin_id
                )
            ).first()

            if existing_vendor:
                skipped_already_moved += 1
                continue

            new_vendor = Vendor(
                full_name=contact.full_name,
                phone_number=contact.phone,
                email=contact.email,
                linkedin_id=contact.linkedin_id,
                company_name=contact.company_name,
                location=contact.location,
                linkedin_internal_id=contact.linkedin_internal_id,
                type="client",  
                
                status="prospect" 
                
            )

            db.add(new_vendor)
            moved_ids.append(contact.id)
            inserted += 1

       
       
        if moved_ids:
            db.query(VendorContactExtractsORM).filter(
                VendorContactExtractsORM.id.in_(moved_ids)
            ).update({"moved_to_vendor": True}, synchronize_session=False)

        db.commit()

        return {
            "inserted": inserted,
            "skipped_already_moved": skipped_already_moved,
            "count": len(moved_ids),
            "message": f"Successfully moved {inserted} contacts to vendors"
        }

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Move error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Move error: {str(e)}")
    