import logging
from typing import List, Optional, Dict
from datetime import datetime
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
    
    processed_identifiers = set()
    
    try:
        for contact in contacts:
            try:
                # 1. Check for duplicates within the current batch
                identifier = f"{contact.email if contact.email else ''}-{contact.linkedin_id if contact.linkedin_id else ''}"
                if identifier in processed_identifiers and (contact.email or contact.linkedin_id):
                    duplicates += 1
                    duplicate_contacts.append({
                        "full_name": contact.full_name,
                        "email": contact.email,
                        "reason": "Duplicate in the same batch"
                    })
                    continue

                # 2. Check for duplicates in the database
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
                        "reason": "Duplicate email or LinkedIn ID in database"
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
                db.flush()  # Flush so subsequent checks see it, and unique constraint is checked early
                
                # Mark as processed in this batch
                if contact.email or contact.linkedin_id:
                    processed_identifiers.add(identifier)
                
                inserted += 1
                
            except IntegrityError:
                db.rollback() # Rollback the flush
                duplicates += 1
                duplicate_contacts.append({
                    "full_name": contact.full_name,
                    "email": contact.email,
                    "reason": "IntegrityError (Conflict detected by database)"
                })
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


async def move_contacts_to_vendor(contact_ids: List[int], db: Session) -> Dict:
    """Move vendor contacts to vendor table with deduplication using ORM
    
    Args:
        contact_ids: List of vendor contact extract IDs to move
        db: Database session
        
    Returns:
        Dict with processed count and message
        
    Raises:
        HTTPException: If validation fails or database error occurs
    """
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")
    
    # Safety limit to prevent API timeouts
    MAX_RECORDS_PER_REQUEST = 5000
    if len(contact_ids) > MAX_RECORDS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many records. Maximum {MAX_RECORDS_PER_REQUEST} per request. "
                   f"Please split into smaller batches or use background processing."
        )
    
    batch_size = 200
    total_updated = 0
    
    try:
        for i in range(0, len(contact_ids), batch_size):
            batch = contact_ids[i:i + batch_size]
            
            # Get extracts that haven't been moved yet
            extracts = db.query(VendorContactExtractsORM).filter(
                VendorContactExtractsORM.id.in_(batch),
                VendorContactExtractsORM.moved_to_vendor == 0
            ).all()
            
            for extract in extracts:
                # Check for existing vendor
                vendor = find_existing_vendor(db, extract)
                
                if vendor:
                    # Duplicate found - append notes using ORM
                    notes = build_duplicate_notes(vendor, extract)
                    combined_notes = ((vendor.notes or "") + "\n" + notes)[:255]
                    vendor.notes = combined_notes
                    vendor_id = vendor.id
                else:
                    # Create new vendor using ORM
                    new_vendor = Vendor(
                        full_name=extract.full_name,
                        email=extract.email,
                        linkedin_id=extract.linkedin_id,
                        linkedin_internal_id=extract.linkedin_internal_id,
                        company_name=extract.company_name or '',
                        location=extract.location or '',
                        type='third-party-vendor',
                        status='prospect',
                        notes=f'Created from extract ID: {extract.id}'[:255],
                        linkedin_connected='NO',
                        intro_email_sent='NO',
                        intro_call='NO',
                        phone_number=extract.phone
                    )
                    
                    # Append extra info to notes
                    extra_notes = []
                    if extract.source_email:
                        extra_notes.append(f"Source Email: {extract.source_email}")
                    if extract.job_source:
                        extra_notes.append(f"Job Source: {extract.job_source}")
                    if extract.notes:
                        extra_notes.append(f"Original Notes: {extract.notes}")
                        
                    if extra_notes:
                        current_notes = new_vendor.notes or ""
                        new_vendor.notes = (current_notes + "\n" + "\n".join(extra_notes))[:65535] # Text type is large enough, but keeping safe
                    db.add(new_vendor)
                    db.flush()  # Get the ID without committing
                    vendor_id = new_vendor.id
                
                # Update extract using ORM
                extract.moved_to_vendor = 1
                extract.vendor_id = vendor_id
                extract.moved_at = datetime.now()
                
                total_updated += 1
            
            db.commit()
            
            # Log progress every batch (no sensitive data)
            logger.info(f"Batch {i//batch_size + 1}: Processed {total_updated} records")
        
        logger.info(f"Successfully processed {total_updated} vendor contacts")
        return {
            "processed": total_updated,
            "message": f"Successfully moved {total_updated} contacts to vendor"
        }
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error moving contacts to vendor: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

