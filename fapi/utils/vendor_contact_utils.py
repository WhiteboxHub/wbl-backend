
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








# import asyncio
# import mysql.connector
# from mysql.connector import Error
# from fastapi import HTTPException
# from typing import Optional, List, Dict, Any
# import logging

# from fapi.db.database import db_config

# logger = logging.getLogger(__name__)


# # ---------------------------------------------------------
# # MYSQL CONNECTION
# # ---------------------------------------------------------
# async def _get_conn():
#     loop = asyncio.get_event_loop()
#     return await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))


# # ---------------------------------------------------------
# # GET ALL CONTACTS
# # ---------------------------------------------------------
# async def get_all_vendor_contacts():
#     conn = await _get_conn()
#     cursor = conn.cursor(dictionary=True)
#     try:
#         cursor.execute("SELECT * FROM vendor_contact_extracts ORDER BY id DESC")
#         return cursor.fetchall()
#     except Error as e:
#         logger.error(f"Failed to fetch contacts: {e}")
#         raise HTTPException(500, f"Database error: {e}")
#     finally:
#         cursor.close()
#         conn.close()


# # ---------------------------------------------------------
# # INSERT ONE (Optional)
# # ---------------------------------------------------------
# async def insert_vendor_contact(contact: dict):
#     conn = await _get_conn()
#     cursor = conn.cursor()
#     try:
#         cursor.execute(
#             """
#             INSERT INTO vendor_contact_extracts 
#             (full_name, email, phone, linkedin_id, company_name, location, source_email, extraction_date, moved_to_vendor)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,CURDATE(),0)
#             """,
#             (
#                 contact.get("full_name"),
#                 contact.get("email"),
#                 contact.get("phone"),
#                 contact.get("linkedin_id"),
#                 contact.get("company_name"),
#                 contact.get("location"),
#                 contact.get("source_email"),
#             ),
#         )
#         conn.commit()
#     except Error as e:
#         conn.rollback()
#         logger.error(f"Failed to insert contact: {e}")
#         raise HTTPException(500, f"Insert error: {e}")
#     finally:
#         cursor.close()
#         conn.close()


# # ---------------------------------------------------------
# # UPDATE ONE CONTACT - FIXED VERSION
# # ---------------------------------------------------------
# async def update_vendor_contact(contact_id: int, fields: dict):
#     """Update a vendor contact with proper field validation"""
#     conn = await _get_conn()
#     cursor = conn.cursor()
    
#     try:
#         # Valid columns in the vendor_contact_extracts table
#         valid_columns = {
#             'full_name', 'email', 'phone', 'linkedin_id', 
#             'company_name', 'location', 'source_email', 
#             'extraction_date', 'moved_to_vendor', 'internal_linkedin_id'
#         }
        
#         # Filter out invalid fields and None values
#         filtered_fields = {
#             k: v for k, v in fields.items() 
#             if k in valid_columns and v is not None
#         }
        
#         if not filtered_fields:
#             logger.warning(f"No valid fields to update for contact {contact_id}")
#             raise HTTPException(400, "No valid fields to update")
        
#         # Build the SET clause
#         set_clause = ", ".join([f"{k}=%s" for k in filtered_fields.keys()])
#         values = list(filtered_fields.values()) + [contact_id]
        
#         # Execute update
#         query = f"UPDATE vendor_contact_extracts SET {set_clause} WHERE id=%s"
#         logger.info(f"Executing update query: {query} with values: {values}")
        
#         cursor.execute(query, values)
#         conn.commit()

#         if cursor.rowcount == 0:
#             logger.warning(f"Contact {contact_id} not found")
#             raise HTTPException(404, "Contact not found")
        
#         logger.info(f"Successfully updated contact {contact_id}")

#     except HTTPException:
#         raise
#     except Error as e:
#         conn.rollback()
#         logger.error(f"Failed to update contact {contact_id}: {e}")
#         raise HTTPException(500, f"Update error: {e}")
#     except Exception as e:
#         conn.rollback()
#         logger.error(f"Unexpected error updating contact {contact_id}: {e}")
#         raise HTTPException(500, f"Unexpected error: {e}")
#     finally:
#         cursor.close()
#         conn.close()


# # ---------------------------------------------------------
# # MOVE ALL CONTACTS TO VENDOR TABLE
# # ---------------------------------------------------------
# async def move_all_contacts_to_vendor() -> Dict[str, Any]:
#     """
#     Move all contacts from vendor_contact_extracts to vendor table
#     and mark them as moved_to_vendor = 1
#     """
#     conn = await _get_conn()
#     cursor = conn.cursor(dictionary=True)
#     cursor_write = conn.cursor()

#     try:
#         # Get all contacts that haven't been moved yet
#         cursor.execute("SELECT * FROM vendor_contact_extracts WHERE moved_to_vendor = 0")
#         rows = cursor.fetchall()

#         if not rows:
#             return {
#                 "message": "All contacts are already moved to vendor",
#                 "inserted": 0,
#                 "moved_count": 0,
#                 "success": True
#             }

#         # Insert query for vendor table
#         insert_query = """
#             INSERT IGNORE INTO vendor
#             (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
#         """

#         moved_ids = []
#         inserted = 0

#         # Insert each contact into vendor table
#         for r in rows:
#             cursor_write.execute(
#                 insert_query,
#                 (
#                     r.get("full_name"),
#                     r.get("phone"),
#                     r.get("email"),
#                     r.get("linkedin_id"),
#                     r.get("company_name"),
#                     r.get("location"),
#                     r.get("internal_linkedin_id"),
#                 ),
#             )

#             if cursor_write.rowcount > 0:
#                 inserted += 1
            
#             # Track all IDs to mark as moved
#             moved_ids.append(r["id"])

#         # Mark all contacts as moved
#         if moved_ids:
#             placeholders = ",".join(["%s"] * len(moved_ids))
#             cursor_write.execute(
#                 f"UPDATE vendor_contact_extracts SET moved_to_vendor=1 WHERE id IN ({placeholders})",
#                 moved_ids,
#             )

#         conn.commit()

#         return {
#             "message": f"Successfully moved {len(moved_ids)} contacts to vendor",
#             "inserted": inserted,
#             "moved_count": len(moved_ids),
#             "success": True
#         }

#     except Error as e:
#         conn.rollback()
#         logger.error(f"Failed to move contacts: {e}")
#         raise HTTPException(500, f"Move error: {e}")
#     finally:
#         cursor.close()
#         cursor_write.close()
#         conn.close()




import asyncio
import mysql.connector
from mysql.connector import Error
from fastapi import HTTPException
from typing import Optional, List, Dict, Any
import logging

from fapi.db.database import db_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# MYSQL CONNECTION
# ---------------------------------------------------------
async def _get_conn():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))


# ---------------------------------------------------------
# GET ALL CONTACTS
# ---------------------------------------------------------
async def get_all_vendor_contacts():
    conn = await _get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vendor_contact_extracts ORDER BY id DESC")
        results = cursor.fetchall()
        
        # Convert moved_to_vendor to proper boolean
        for row in results:
            if 'moved_to_vendor' in row:
                row['moved_to_vendor'] = bool(row['moved_to_vendor'])
                
        return results
    except Error as e:
        logger.error(f"Failed to fetch contacts: {e}")
        raise HTTPException(500, f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------
# UPDATE ONE CONTACT - FIXED VERSION
# ---------------------------------------------------------
async def update_vendor_contact(contact_id: int, fields: dict):
    """Update a vendor contact with proper boolean handling"""
    conn = await _get_conn()
    cursor = conn.cursor()
    
    try:
        # Valid columns in the vendor_contact_extracts table
        valid_columns = {
            'full_name', 'email', 'phone', 'linkedin_id', 
            'company_name', 'location', 'source_email', 
            'extraction_date', 'moved_to_vendor', 'internal_linkedin_id'
        }
        
        # Filter out invalid fields and None values
        filtered_fields = {}
        for k, v in fields.items():
            if k in valid_columns and v is not None:
                # Convert moved_to_vendor to proper MySQL boolean (0/1)
                if k == 'moved_to_vendor':
                    if isinstance(v, str):
                        # Handle string values: 'true', 'false', 'yes', 'no'
                        filtered_fields[k] = 1 if v.lower() in ['true', 'yes', '1'] else 0
                    elif isinstance(v, bool):
                        filtered_fields[k] = 1 if v else 0
                    else:
                        filtered_fields[k] = 1 if v else 0
                else:
                    filtered_fields[k] = v
        
        if not filtered_fields:
            logger.warning(f"No valid fields to update for contact {contact_id}")
            raise HTTPException(400, "No valid fields to update")
        
        # Build the SET clause
        set_clause = ", ".join([f"{k}=%s" for k in filtered_fields.keys()])
        values = list(filtered_fields.values()) + [contact_id]
        
        # Execute update
        query = f"UPDATE vendor_contact_extracts SET {set_clause} WHERE id=%s"
        logger.info(f"Executing update query: {query} with values: {values}")
        
        cursor.execute(query, values)
        conn.commit()

        if cursor.rowcount == 0:
            logger.warning(f"Contact {contact_id} not found")
            raise HTTPException(404, "Contact not found")
        
        logger.info(f"Successfully updated contact {contact_id}")

    except HTTPException:
        raise
    except Error as e:
        conn.rollback()
        logger.error(f"Failed to update contact {contact_id}: {e}")
        raise HTTPException(500, f"Update error: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error updating contact {contact_id}: {e}")
        raise HTTPException(500, f"Unexpected error: {e}")
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------
# INSERT ONE (Optional - keep existing)
# ---------------------------------------------------------
async def insert_vendor_contact(contact: dict):
    conn = await _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO vendor_contact_extracts 
            (full_name, email, phone, linkedin_id, company_name, location, source_email, extraction_date, moved_to_vendor)
            VALUES (%s,%s,%s,%s,%s,%s,%s,CURDATE(),0)
            """,
            (
                contact.get("full_name"),
                contact.get("email"),
                contact.get("phone"),
                contact.get("linkedin_id"),
                contact.get("company_name"),
                contact.get("location"),
                contact.get("source_email"),
            ),
        )
        conn.commit()
    except Error as e:
        conn.rollback()
        logger.error(f"Failed to insert contact: {e}")
        raise HTTPException(500, f"Insert error: {e}")
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------
# MOVE ALL CONTACTS TO VENDOR TABLE (keep existing)
# ---------------------------------------------------------
async def move_all_contacts_to_vendor() -> Dict[str, Any]:
    """
    Move all contacts from vendor_contact_extracts to vendor table
    and mark them as moved_to_vendor = 1
    """
    conn = await _get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor_write = conn.cursor()

    try:
        # Get all contacts that haven't been moved yet
        cursor.execute("SELECT * FROM vendor_contact_extracts WHERE moved_to_vendor = 0")
        rows = cursor.fetchall()

        if not rows:
            return {
                "message": "All contacts are already moved to vendor",
                "inserted": 0,
                "moved_count": 0,
                "success": True
            }

        # Insert query for vendor table
        insert_query = """
            INSERT IGNORE INTO vendor
            (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
        """

        moved_ids = []
        inserted = 0

        # Insert each contact into vendor table
        for r in rows:
            cursor_write.execute(
                insert_query,
                (
                    r.get("full_name"),
                    r.get("phone"),
                    r.get("email"),
                    r.get("linkedin_id"),
                    r.get("company_name"),
                    r.get("location"),
                    r.get("internal_linkedin_id"),
                ),
            )

            if cursor_write.rowcount > 0:
                inserted += 1
            
            # Track all IDs to mark as moved
            moved_ids.append(r["id"])

        # Mark all contacts as moved
        if moved_ids:
            placeholders = ",".join(["%s"] * len(moved_ids))
            cursor_write.execute(
                f"UPDATE vendor_contact_extracts SET moved_to_vendor=1 WHERE id IN ({placeholders})",
                moved_ids,
            )

        conn.commit()

        return {
            "message": f"Successfully moved {len(moved_ids)} contacts to vendor",
            "inserted": inserted,
            "moved_count": len(moved_ids),
            "success": True
        }

    except Error as e:
        conn.rollback()
        logger.error(f"Failed to move contacts: {e}")
        raise HTTPException(500, f"Move error: {e}")
    finally:
        cursor.close()
        cursor_write.close()
        conn.close()