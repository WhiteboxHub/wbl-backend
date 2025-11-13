
# import asyncio
# import mysql.connector
# from mysql.connector import Error
# from fastapi import HTTPException
# from fapi.db.database import db_config
# from fapi.db.schemas import VendorContactExtractCreate
# from typing import List, Optional

# async def get_all_vendor_contacts():
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM vendor_contact_extracts ORDER BY id DESC"

#         await loop.run_in_executor(None, cursor.execute, query)
#         rows = cursor.fetchall()
#         return rows
#     except Error as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching vendor contacts: {e}")
#     finally:
#         cursor.close()
#         conn.close()

# async def get_vendor_contact_by_id(contact_id: int, db: Session) -> VendorContactExtractsORM:
 
#     contact = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.id == contact_id).first()
#     if not contact:
#         raise HTTPException(status_code=404, detail="Vendor contact not found")
#     return contact

# async def insert_vendor_contact(contact: VendorContactExtractCreate, db: Session) -> VendorContactExtractsORM:
    
#     try:
       
#         db_contact = VendorContactExtractsORM(
#             full_name=contact.full_name,
#             source_email=contact.source_email,
#             email=contact.email,
#             phone=contact.phone,
#             linkedin_id=contact.linkedin_id,
#             company_name=contact.company_name,
#             location=contact.location,
#             moved_to_vendor=False
#         )
        
#         db.add(db_contact)
#         db.commit()
#         db.refresh(db_contact)
#         return db_contact
        
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=400, detail="Duplicate entry or integrity error")
#     except SQLAlchemyError as e:
#         db.rollback()
#         logger.error(f"Insert error: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Insert error: {str(e)}")

# async def update_vendor_contact(contact_id: int, update_data: VendorContactExtractUpdate, db: Session) -> VendorContactExtractsORM:
#     """Update vendor contact using SQLAlchemy ORM"""
#     if not update_data.dict(exclude_unset=True):
#         raise HTTPException(status_code=400, detail="No data to update")


#     db_contact = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.id == contact_id).first()
#     if not db_contact:
#         raise HTTPException(status_code=404, detail="Vendor contact not found")

#     try:
      
#         update_fields = update_data.dict(exclude_unset=True)
#         for field, value in update_fields.items():
#             setattr(db_contact, field, value)
        
#         db.commit()
#         db.refresh(db_contact)
#         return db_contact
        
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=400, detail="Duplicate entry or integrity error")
#     except SQLAlchemyError as e:
#         db.rollback()
#         logger.error(f"Update error: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

# async def delete_vendor_contact(contact_id: int):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = "DELETE FROM vendor_contact_extracts WHERE id = %s"
#         await loop.run_in_executor(None, cursor.execute, query, (contact_id,))
#         conn.commit()

#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")

#     except Error as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Delete error: {e}")
#     finally:
#         cursor.close()
#         conn.close()


# async def delete_vendor_contact(contact_id: int):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = "DELETE FROM vendor_contact_extracts WHERE id = %s"
#         await loop.run_in_executor(None, cursor.execute, query, (contact_id,))
#         conn.commit()

#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")

#     except Error as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Delete error: {e}")
#     finally:
#         cursor.close()
#         conn.close()

# async def bulk_delete_vendor_contacts(contact_ids: List[int]):
#     """
#     Bulk delete vendor contacts by IDs
#     """
#     if not contact_ids:
#         raise HTTPException(status_code=400, detail="No contact IDs provided")
    
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
        
#         # Create placeholders for the IN clause
#         placeholders = ','.join(['%s'] * len(contact_ids))
#         query = f"DELETE FROM vendor_contact_extracts WHERE id IN ({placeholders})"
        
#         await loop.run_in_executor(None, cursor.execute, query, tuple(contact_ids))
#         deleted_count = cursor.rowcount
#         conn.commit()
        
#         return deleted_count
        
#     except Error as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Bulk delete error: {e}")
#     finally:
#         cursor.close()
#         conn.close()

# async def bulk_delete_moved_contacts():
#     """
#     Bulk delete all contacts where moved_to_vendor = 1 (Yes)
#     """
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
        
#         query = "DELETE FROM vendor_contact_extracts WHERE moved_to_vendor = 1"
        
#         await loop.run_in_executor(None, cursor.execute, query)
#         deleted_count = cursor.rowcount
#         conn.commit()
        
#         return deleted_count
        
#     except Error as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Bulk delete moved contacts error: {e}")
#     finally:
#         cursor.close()
#         conn.close()

# async def move_contacts_to_vendor(contact_ids: Optional[List[int]] = None, db: Session = None) -> dict:
#     """Move vendor contacts to main vendor table using SQLAlchemy ORM"""
#     try:
    
#         query = db.query(VendorContactExtractsORM).filter(VendorContactExtractsORM.moved_to_vendor == False)
        
#         if contact_ids:
#             query = query.filter(VendorContactExtractsORM.id.in_(contact_ids))
        
#         contacts_to_move = query.all()
        
#         if not contacts_to_move:
#             return {
#                 "inserted": 0,
#                 "skipped_already_moved": 0,
#                 "count": 0,
#                 "message": "No contacts to move or all selected contacts are already moved"
#             }

#         inserted = 0
#         skipped_already_moved = 0
#         moved_ids = []

#         for contact in contacts_to_move:
          
#             existing_vendor = db.query(Vendor).filter(
#                 or_(
#                     Vendor.email == contact.email,
#                     Vendor.linkedin_id == contact.linkedin_id
#                 )
#             ).first()

#             if existing_vendor:
#                 skipped_already_moved += 1
#                 continue

#             new_vendor = Vendor(
#                 full_name=contact.full_name,
#                 phone_number=contact.phone,
#                 email=contact.email,
#                 linkedin_id=contact.linkedin_id,
#                 company_name=contact.company_name,
#                 location=contact.location,
#                 linkedin_internal_id=contact.linkedin_internal_id,
#                 type="client",  
                
#                 status="prospect" 
                
#             )

#             db.add(new_vendor)
#             moved_ids.append(contact.id)
#             inserted += 1

       
       
#         if moved_ids:
#             db.query(VendorContactExtractsORM).filter(
#                 VendorContactExtractsORM.id.in_(moved_ids)
#             ).update({"moved_to_vendor": True}, synchronize_session=False)

#         db.commit()

#         return {
#             "inserted": inserted,
#             "skipped_already_moved": skipped_already_moved,
#             "count": len(moved_ids),
#             "message": f"Successfully moved {inserted} contacts to vendors"
#         }

#     except Error as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Move error: {e}")
#     finally:
#         if cur_select:
#             cur_select.close()
#         if cur_exec:
#             cur_exec.close()
#         conn.close()







# from fastapi import HTTPException
# from sqlalchemy.orm import Session
# from sqlalchemy.exc import SQLAlchemyError
# from fapi.db.models import VendorContactExtractsORM
# from fapi.db.schemas import VendorContactExtractCreate


# async def create_vendor_contact(contact_data: VendorContactExtractCreate, db: Session):
#     """Create a new vendor contact"""
#     try:
#         new_contact = VendorContactExtractsORM(**contact_data.dict())
#         db.add(new_contact)
#         db.commit()
#         db.refresh(new_contact)
#         return new_contact
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# async def get_all_vendor_contacts(db: Session):
#     """Get all vendor contacts"""
#     try:
#         contacts = db.query(VendorContactExtractsORM).all()
#         return contacts
#     except SQLAlchemyError as e:
#         raise HTTPException(status_code=500, detail=f"Fetch error: {str(e)}")


# async def get_vendor_contact_by_id(contact_id: int, db: Session):
#     """Get a specific vendor contact by ID"""
#     try:
#         contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
        
#         if not contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")
        
#         return contact
#     except HTTPException:
#         raise
#     except SQLAlchemyError as e:
#         raise HTTPException(status_code=500, detail=f"Fetch error: {str(e)}")


# async def update_vendor_contact(
#     contact_id: int, 
#     updated_data: VendorContactExtractCreate, 
#     db: Session
# ):
#     """Update an existing vendor contact"""
#     try:
#         db_contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
        
#         if not db_contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")

#         for key, value in updated_data.dict(exclude_unset=True).items():
#             setattr(db_contact, key, value)

#         db.commit()
#         db.refresh(db_contact)
#         return db_contact
#     except HTTPException:
#         raise
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")


# async def delete_vendor_contact(contact_id: int, db: Session):
#     """Delete a single vendor contact"""
#     try:
#         db_contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
        
#         if not db_contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")

#         db.delete(db_contact)
#         db.commit()
#         return {
#             "message": "Vendor contact deleted successfully",
#             "id": contact_id
#         }
#     except HTTPException:
#         raise
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")


# async def bulk_delete_moved_contacts(db: Session):
#     """Delete all vendor contacts where moved_to_vendor == True"""
#     try:
#         moved_contacts = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.moved_to_vendor == True
#         ).all()

#         if not moved_contacts:
#             return {
#                 "message": "No moved contacts to delete",
#                 "deleted_count": 0
#             }

#         deleted_count = len(moved_contacts)
        
#         for contact in moved_contacts:
#             db.delete(contact)

#         db.commit()
        
#         return {
#             "message": f"Successfully deleted {deleted_count} moved contact{'s' if deleted_count > 1 else ''}",
#             "deleted_count": deleted_count
#         }
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Bulk delete error: {str(e)}")








from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fapi.db.models import VendorContactExtractsORM
from fapi.db.schemas import VendorContactExtractCreate


async def create_vendor_contact(contact_data: VendorContactExtractCreate, db: Session):
    try:
        new_contact = VendorContactExtractsORM(**contact_data.dict())
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        return new_contact
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


async def get_all_vendor_contacts(db: Session):
    try:
        return db.query(VendorContactExtractsORM).all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Fetch error: {str(e)}")


async def get_vendor_contact_by_id(contact_id: int, db: Session):
    contact = db.query(VendorContactExtractsORM).filter(
        VendorContactExtractsORM.id == contact_id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Vendor contact not found")

    return contact


async def update_vendor_contact(contact_id: int, updated_data: VendorContactExtractCreate, db: Session):
    try:
        contact = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id == contact_id
        ).first()

        if not contact:
            raise HTTPException(status_code=404, detail="Vendor contact not found")

        for key, value in updated_data.dict(exclude_unset=True).items():
            setattr(contact, key, value)

        db.commit()
        db.refresh(contact)
        return contact

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")


async def delete_vendor_contact(contact_id: int, db: Session):
    try:
        contact = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.id == contact_id
        ).first()

        if not contact:
            raise HTTPException(status_code=404, detail="Vendor contact not found")

        db.delete(contact)
        db.commit()

        return {"message": "Vendor contact deleted", "id": contact_id}

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")


async def bulk_delete_moved_contacts(db: Session):
    """Delete all vendor contacts where moved_to_vendor == True"""
    try:
        deleted = db.query(VendorContactExtractsORM).filter(
            VendorContactExtractsORM.moved_to_vendor == True
        ).delete(synchronize_session=False)

        db.commit()

        return {
            "message": f"Deleted {deleted} moved contacts",
            "deleted_count": deleted,
        }

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk delete error: {str(e)}")