import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import VendorContactExtractsORM, Vendor
from fapi.db.schemas import VendorContactExtractCreate, VendorContactExtractUpdate

logger = logging.getLogger(__name__)


def find_existing_vendor(db: Session, extract: VendorContactExtractsORM) -> Optional[Vendor]:
    """Find existing vendor by linkedin_internal_id, linkedin_id, or email"""
    if extract.linkedin_internal_id:
        vendor = db.query(Vendor).filter(
            Vendor.linkedin_internal_id == extract.linkedin_internal_id
        ).first()
        if vendor:
            return vendor

    if extract.linkedin_id:
        vendor = db.query(Vendor).filter(
            Vendor.linkedin_id == extract.linkedin_id
        ).first()
        if vendor:
            return vendor

    if extract.email:
        vendor = db.query(Vendor).filter(
            Vendor.email == extract.email
        ).first()
        if vendor:
            return vendor

    return None


def build_duplicate_notes(vendor: Vendor, extract: VendorContactExtractsORM) -> str:
    """Build notes for duplicate vendor detection"""
    notes = ["Duplicate detected via identity match"]

    if extract.full_name and extract.full_name != vendor.full_name:
        notes.append(f"Alt name: {extract.full_name}")

    if extract.email and extract.email != vendor.email:
        notes.append(f"Alt email: {extract.email}")

    if extract.phone and extract.phone != vendor.phone_number:
        notes.append(f"Alt phone: {extract.phone}")

    if extract.company_name and extract.company_name != vendor.company_name:
        notes.append(f"Alt company: {extract.company_name}")

    if extract.location and extract.location != vendor.location:
        notes.append(f"Alt location: {extract.location}")

    notes.append(f"Source extract ID: {extract.id}")

    return "\n".join(notes)

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
            moved_to_vendor=False
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



async def insert_vendor_contacts_bulk(contacts: List[VendorContactExtractCreate], db: Session) -> dict:
    """Bulk insert vendor contacts with duplicate handling"""
    inserted = 0
    failed = 0
    duplicates = 0
    failed_contacts = []
    duplicate_contacts = []
    
    try:
        for contact in contacts:
            try:
                # Check for duplicates by email or linkedin_id
                existing = None
                if contact.email or contact.linkedin_id:
                    existing = db.query(VendorContactExtractsORM).filter(
                        or_(
                            VendorContactExtractsORM.email == contact.email if contact.email else False,
                            VendorContactExtractsORM.linkedin_id == contact.linkedin_id if contact.linkedin_id else False
                        )
                    ).first()
                
                if existing:
                    duplicates += 1
                    duplicate_contacts.append({
                        "full_name": contact.full_name,
                        "email": contact.email,
                        "reason": "Duplicate email or LinkedIn ID"
                    })
                    continue
                
                # Insert new contact
                db_contact = VendorContactExtractsORM(
                    full_name=contact.full_name,
                    source_email=contact.source_email,
                    email=contact.email,
                    phone=contact.phone,
                    linkedin_id=contact.linkedin_id,
                    company_name=contact.company_name,
                    location=contact.location,
                    moved_to_vendor=False
                )
                
                db.add(db_contact)
                inserted += 1
                
            except Exception as e:
                failed += 1
                failed_contacts.append({
                    "full_name": contact.full_name,
                    "email": contact.email,
                    "reason": str(e)
                })
                logger.error(f"Failed to insert contact {contact.full_name}: {str(e)}")
        
        # Commit all successful inserts
        db.commit()
        
        return {
            "inserted": inserted,
            "failed": failed,
            "duplicates": duplicates,
            "total": len(contacts),
            "failed_contacts": failed_contacts,
            "duplicate_contacts": duplicate_contacts
        }
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Bulk insert error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk insert error: {str(e)}")


async def delete_vendor_contacts_bulk(contact_ids: List[int], db: Session) -> dict:
    """Bulk delete vendor contacts"""
    try:
        deleted_count = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id.in_(contact_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "deleted": deleted_count,
            "message": f"Successfully deleted {deleted_count} contacts"
        }
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Bulk delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk delete error: {str(e)}")
