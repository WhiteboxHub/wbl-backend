# vendor_contact.py
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from fapi.db.database import get_db
from fapi.db.models import VendorContactExtractsORM
from fapi.db.schemas import (
    VendorContactExtract,
    VendorContactExtractCreate,
    VendorContactExtractUpdate,
    VendorContactBulkCreate,
    VendorContactBulkResponse,
    MoveToVendorRequest,
)
from fapi.utils.vendor_contact_utils import (
    get_all_vendor_contacts,
    get_vendor_contact_by_id,
    insert_vendor_contact,
    insert_vendor_contacts_bulk,
    update_vendor_contact,
    delete_vendor_contact,
    delete_vendor_contacts_bulk,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/vendor_contact_extracts", response_model=List[VendorContactExtract])
async def read_vendor_contact_extracts(db: Session = Depends(get_db)):
    try:
        return await get_all_vendor_contacts(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor contacts: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/vendor_contact_extracts/{contact_id}", response_model=VendorContactExtract)
async def read_vendor_contact_by_id(contact_id: int, db: Session = Depends(get_db)):
    try:
        return await get_vendor_contact_by_id(contact_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching vendor contact: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/vendor_contact", response_model=VendorContactExtract)
async def create_vendor_contact_handler(
    contact: VendorContactExtractCreate, 
    db: Session = Depends(get_db)
):
    try:
        result = await insert_vendor_contact(contact, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor contact: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/vendor_contact/bulk", response_model=VendorContactBulkResponse)
async def create_vendor_contacts_bulk_handler(
    bulk_data: VendorContactBulkCreate,
    db: Session = Depends(get_db)
):
    """Bulk insert vendor contacts"""
    try:
        result = await insert_vendor_contacts_bulk(bulk_data.contacts, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk insert: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/vendor_contact/move-to-vendor")
async def move_contacts_to_vendor_handler(
    request: MoveToVendorRequest,
    db: Session = Depends(get_db)
):
    """Move vendor contacts to vendor table, creating vendor records with deduplication
    
    Uses POST with request body to avoid URL length limits for large batches.
    Processes in batches of 200 to avoid database locks and timeouts.
    Handles duplicate detection via linkedin_internal_id, linkedin_id, or email.
    """
    if not request.contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")
    
    # Safety limit to prevent API timeouts
    MAX_RECORDS_PER_REQUEST = 5000
    if len(request.contact_ids) > MAX_RECORDS_PER_REQUEST:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many records. Maximum {MAX_RECORDS_PER_REQUEST} per request. "
                   f"Please split into smaller batches or use background processing."
        )

    batch_size = 200  # Reduced for better performance
    total_updated = 0

    try:
        from sqlalchemy import text
        from datetime import datetime
        from fapi.utils.vendor_contact_utils import find_existing_vendor, build_duplicate_notes
        
        for i in range(0, len(request.contact_ids), batch_size):
            batch = request.contact_ids[i:i + batch_size]
            
            # Get extracts that haven't been moved yet
            extracts = db.query(VendorContactExtractsORM).filter(
                VendorContactExtractsORM.id.in_(batch),
                VendorContactExtractsORM.moved_to_vendor == 0
            ).all()
            
            for extract in extracts:
                # Check for existing vendor
                from fapi.db.models import Vendor
                vendor = find_existing_vendor(db, extract)
                
                if vendor:
                    # Duplicate found - append notes
                    notes = build_duplicate_notes(vendor, extract)
                    combined_notes = ((vendor.notes or "") + "\n" + notes)[:255]
                    
                    # Update vendor notes using raw SQL
                    db.execute(text("""
                        UPDATE vendor 
                        SET notes = :notes
                        WHERE id = :vendor_id
                    """), {'notes': combined_notes, 'vendor_id': vendor.id})
                    
                    vendor_id = vendor.id
                else:
                    # Create new vendor using raw SQL
                    insert_result = db.execute(text("""
                        INSERT INTO vendor 
                        (full_name, email, linkedin_id, linkedin_internal_id, 
                         company_name, location, type, status, notes, 
                         linkedin_connected, intro_email_sent, intro_call)
                        VALUES 
                        (:full_name, :email, :linkedin_id, :linkedin_internal_id,
                         :company_name, :location, :type, :status, :notes,
                         :linkedin_connected, :intro_email_sent, :intro_call)
                    """), {
                        'full_name': extract.full_name,
                        'email': extract.email,
                        'linkedin_id': extract.linkedin_id,
                        'linkedin_internal_id': extract.linkedin_internal_id,
                        'company_name': extract.company_name or '',
                        'location': extract.location or '',
                        'type': 'third-party-vendor',
                        'status': 'prospect',
                        'notes': f'Created from extract ID: {extract.id}'[:255],
                        'linkedin_connected': 'NO',
                        'intro_email_sent': 'NO',
                        'intro_call': 'NO'
                    })
                    vendor_id = insert_result.lastrowid
                
                # Update extract using raw SQL to avoid triggers
                db.execute(text("""
                    UPDATE vendor_contact_extracts 
                    SET moved_to_vendor = 1,
                        vendor_id = :vendor_id,
                        moved_at = :moved_at
                    WHERE id = :extract_id
                """), {
                    'vendor_id': vendor_id,
                    'moved_at': datetime.now(),
                    'extract_id': extract.id
                })
                
                total_updated += 1
            
            db.commit()
            
            # Log progress every batch (no sensitive data)
            logger.info(f"Batch {i//batch_size + 1}: Processed {total_updated} records")
        
        logger.info(f"Successfully processed {total_updated} vendor contacts")
        return {
            "processed": total_updated,
            "message": f"Successfully moved {total_updated} contacts to vendor"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error moving contacts to vendor: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.put("/vendor_contact/{contact_id}", response_model=VendorContactExtract)
async def update_vendor_contact_handler(
    contact_id: int, 
    update_data: VendorContactExtractUpdate, 
    db: Session = Depends(get_db)
):
    """Update existing vendor contact"""
    try:
        return await update_vendor_contact(contact_id, update_data, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vendor contact: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/vendor_contact/bulk")
async def delete_vendor_contacts_bulk_handler(
    contact_ids: List[int] = Query(...),
    db: Session = Depends(get_db)
):
    """Bulk delete vendor contacts"""
    try:
        result = await delete_vendor_contacts_bulk(contact_ids, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/vendor_contact/{contact_id}")
async def delete_vendor_contact_handler(contact_id: int, db: Session = Depends(get_db)):
    try:
        result = await delete_vendor_contact(contact_id, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vendor contact: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")