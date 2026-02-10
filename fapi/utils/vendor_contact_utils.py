import logging
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import VendorContactExtractsORM, Vendor, VendorTypeEnum
from fapi.db.schemas import VendorContactExtractCreate, VendorContactExtractUpdate, VendorBase

logger = logging.getLogger(__name__)

def _clean_id_field(val: Optional[str]) -> Optional[str]:
    """Clean identity fields by removing common placeholders and whitespace."""
    if val is None:
        return None
    v = str(val).strip()
    if not v or v.lower() in ["none", "null", "undefined"]:
        return None
    return v


def find_existing_vendor(db: Session, extract: VendorContactExtractsORM) -> Optional[Vendor]:
    """Find existing vendor by identity, prioritizing email uniqueness."""
    ext_email = _clean_id_field(extract.email)
    
    # 1. ALWAYS check email first. If this email exists, we MUST merge to this record.
    if ext_email:
        v_by_email = db.query(Vendor).filter(Vendor.email == ext_email).first()
        if v_by_email:
            return v_by_email
            
    # 2. No email match, check LinkedIn identity
    ext_internal_id = _clean_id_field(extract.linkedin_internal_id)
    ext_linkedin_id = _clean_id_field(extract.linkedin_id)
    
    filters = []
    if ext_internal_id:
        filters.append(Vendor.linkedin_internal_id == ext_internal_id)
    if ext_linkedin_id:
        filters.append(Vendor.linkedin_id == ext_linkedin_id)
    
    if not filters:
        return None
        
    return db.query(Vendor).filter(or_(*filters)).first()


def build_duplicate_notes(vendor: Vendor, extract: VendorContactExtractsORM) -> str:
    """Build notes for duplicate vendor detection dynamically"""
    notes = ["Duplicate detected via identity match"]

    field_map = {
        'full_name': ('full_name', 'Alt name'),
        'email': ('email', 'Alt email'),
        'phone': ('phone_number', 'Alt phone'),
        'company_name': ('company_name', 'Alt company'),
        'location': ('location', 'Alt location'),
        'linkedin_id': ('linkedin_id', 'Alt LinkedIn ID'),
        'linkedin_internal_id': ('linkedin_internal_id', 'Alt LinkedIn Internal ID')
    }
    
    for ex_field, (ven_field, label) in field_map.items():
        ex_val = getattr(extract, ex_field, None)
        ven_val = getattr(vendor, ven_field, None)
        
        # Only add if we have a real value that is different from existing
        if ex_val and str(ex_val).strip() and str(ex_val).lower() != "none" and ex_val != ven_val:
            notes.append(f"{label}: {str(ex_val).strip()}")

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
       
        db_contact = VendorContactExtractsORM(**contact.dict())
        db_contact.moved_to_vendor = False
        
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
                # Use begin_nested to allow individual row rollback on failure
                # Database unique constraints handle all duplicate checks (email, linkedin_id)
                with db.begin_nested():
                    db_contact = VendorContactExtractsORM(**contact.dict())
                    db_contact.moved_to_vendor = False
                    db.add(db_contact)
                    db.flush()
                
                inserted += 1
                
            except IntegrityError:
                # Savepoint is automatically rolled back on IntegrityError
                duplicates += 1
                duplicate_contacts.append({
                    "full_name": contact.full_name,
                    "email": contact.email,
                    "reason": "Duplicate entry (Database constraint violated)"
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
                # Clean fields for robust logic
                ex_email = _clean_id_field(extract.email)
                ex_linkedin_id = _clean_id_field(extract.linkedin_id)
                ex_internal_id = _clean_id_field(extract.linkedin_internal_id)
                
                # 1. Find a potential vendor match (Email priority or LinkedIn ID fallback)
                vendor = find_existing_vendor(db, extract)
                
                if vendor:
                    # Identity match found - append ALL differences to notes
                    notes = build_duplicate_notes(vendor, extract)
                    # Note: Using 255 limit as per database schema varchar(255)
                    combined_notes = ((vendor.notes or "") + "\n" + notes).strip()[:255]
                    vendor.notes = combined_notes
                    
                    # If existing vendor is missing contact info, enrich it
                    # But ONLY if we aren't creating a conflict (handled by priority search)
                    if not vendor.email and ex_email:
                        vendor.email = ex_email
                    if not vendor.phone_number and extract.phone:
                        vendor.phone_number = extract.phone
                    if not vendor.linkedin_id and ex_linkedin_id:
                        vendor.linkedin_id = ex_linkedin_id
                    if not vendor.linkedin_internal_id and ex_internal_id:
                        vendor.linkedin_internal_id = ex_internal_id
                        
                    vendor_id = vendor.id
                else:
                    # Create new vendor using ORM with explicit mapping to prevent data loss
                    new_vendor = Vendor(
                        full_name=extract.full_name,
                        email=ex_email,
                        linkedin_id=ex_linkedin_id,
                        linkedin_internal_id=ex_internal_id,
                        company_name=extract.company_name or '',
                        location=extract.location or '',
                        phone_number=extract.phone,
                        type=VendorTypeEnum.third_party_vendor,
                        status='prospect',
                        notes=f'Created from extract ID: {extract.id}'[:255],
                        linkedin_connected='NO',
                        intro_email_sent='NO',
                        intro_call='NO'
                    )
                    
                    # Dynamically append extra info to notes from unique extract fields
                    extra_notes = []
                    for f in ['source_email', 'job_source', 'notes']:
                        val = getattr(extract, f, None)
                        if val:
                             label = f.replace('_', ' ').title()
                             extra_notes.append(f"{label}: {val}")
                        
                    if extra_notes:
                        current_notes = new_vendor.notes or ""
                        new_vendor.notes = (current_notes + "\n" + "\n".join(extra_notes))[:65535]
                    
                    db.add(new_vendor)
                    db.flush()
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

