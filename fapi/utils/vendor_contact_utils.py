
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










# # fapi/utils/vendor_contact_utils.py
# import asyncio
# import logging
# from typing import Optional, List, Dict, Any
# import mysql.connector
# from mysql.connector import Error
# from fastapi import HTTPException

# from fapi.db.database import db_config

# logger = logging.getLogger(__name__)

# # helper to get connection in threadpool
# async def _get_conn():
#     loop = asyncio.get_event_loop()
#     return await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))


# async def get_all_vendor_contacts() -> List[Dict[str, Any]]:
#     conn = await _get_conn()
#     cursor = conn.cursor(dictionary=True)
#     try:
#         cursor.execute("SELECT * FROM vendor_contact_extracts ORDER BY id DESC")
#         results = cursor.fetchall() or []
#         # normalize moved_to_vendor to boolean (0/1)
#         for row in results:
#             if "moved_to_vendor" in row:
#                 row["moved_to_vendor"] = bool(row["moved_to_vendor"])
#         return results
#     except Error as e:
#         logger.exception("DB fetch error")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()


# async def update_vendor_contact(contact_id: int, fields: dict):
#     if not fields:
#         raise HTTPException(status_code=400, detail="No data to update")

#     conn = await _get_conn()
#     cursor = conn.cursor()
#     try:
#         # allowed columns
#         valid_columns = {
#             "full_name",
#             "email",
#             "phone",
#             "linkedin_id",
#             "company_name",
#             "location",
#             "source_email",
#             "extraction_date",
#             "moved_to_vendor",
#             "internal_linkedin_id",
#         }

#         set_parts = []
#         values = []
#         for k, v in fields.items():
#             if k not in valid_columns:
#                 continue
#             if k == "moved_to_vendor":
#                 # accept boolean/string/number -> store 0/1
#                 if isinstance(v, bool):
#                     v = 1 if v else 0
#                 elif isinstance(v, str):
#                     v = 1 if v.lower() in ("1", "true", "yes") else 0
#                 else:
#                     v = 1 if v else 0
#             set_parts.append(f"{k} = %s")
#             values.append(v)
#         if not set_parts:
#             raise HTTPException(status_code=400, detail="No valid fields to update")
#         values.append(contact_id)
#         query = f"UPDATE vendor_contact_extracts SET {', '.join(set_parts)} WHERE id = %s"
#         cursor.execute(query, tuple(values))
#         conn.commit()
#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Contact not found")
#         return {"updated": cursor.rowcount}
#     except Error as e:
#         conn.rollback()
#         logger.exception("Update failed")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()


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
#         return {"inserted_id": cursor.lastrowid}
#     except Error as e:
#         conn.rollback()
#         logger.exception("Insert failed")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()


# # move specific ids to vendor: will check for duplicates and insert into vendor table, then mark moved.
# async def move_contacts_by_ids(ids: List[int]) -> Dict[str, Any]:
#     if not ids:
#         return {"inserted": 0, "moved_count": 0}

#     conn = await _get_conn()
#     cur_read = conn.cursor(dictionary=True)
#     cur_write = conn.cursor()
#     try:
#         placeholders = ",".join(["%s"] * len(ids))
#         cur_read.execute(f"SELECT * FROM vendor_contact_extracts WHERE id IN ({placeholders}) AND moved_to_vendor = 0", tuple(ids))
#         rows = cur_read.fetchall() or []
#         if not rows:
#             return {"inserted": 0, "moved_count": 0, "skipped": 0}

#         insert_query = """
#             INSERT IGNORE INTO vendor (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
#         """

#         moved_ids = []
#         inserted = 0
#         for r in rows:
#             values = (
#                 r.get("full_name"),
#                 r.get("phone"),
#                 r.get("email"),
#                 r.get("linkedin_id"),
#                 r.get("company_name"),
#                 r.get("location"),
#                 r.get("internal_linkedin_id"),
#             )
#             cur_write.execute(insert_query, values)
#             if getattr(cur_write, "rowcount", 0) > 0:
#                 inserted += 1
#             moved_ids.append(r.get("id"))

#         if moved_ids:
#             placeholders2 = ",".join(["%s"] * len(moved_ids))
#             cur_write.execute(f"UPDATE vendor_contact_extracts SET moved_to_vendor = 1 WHERE id IN ({placeholders2})", tuple(moved_ids))

#         conn.commit()
#         return {"inserted": inserted, "moved_count": len(moved_ids)}
#     except Error as e:
#         conn.rollback()
#         logger.exception("move_contacts_by_ids failed")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cur_read.close()
#         cur_write.close()
#         conn.close()


# # move all contacts not moved yet to vendor
# async def move_all_contacts_to_vendor() -> Dict[str, Any]:
#     conn = await _get_conn()
#     cur_read = conn.cursor(dictionary=True)
#     cur_write = conn.cursor()
#     try:
#         cur_read.execute("SELECT * FROM vendor_contact_extracts WHERE moved_to_vendor = 0")
#         rows = cur_read.fetchall() or []
#         if not rows:
#             return {"message": "All contacts already moved", "inserted": 0, "moved_count": 0, "success": True}

#         insert_query = """
#             INSERT IGNORE INTO vendor (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
#         """

#         moved_ids = []
#         inserted = 0
#         for r in rows:
#             values = (
#                 r.get("full_name"),
#                 r.get("phone"),
#                 r.get("email"),
#                 r.get("linkedin_id"),
#                 r.get("company_name"),
#                 r.get("location"),
#                 r.get("internal_linkedin_id"),
#             )
#             cur_write.execute(insert_query, values)
#             if getattr(cur_write, "rowcount", 0) > 0:
#                 inserted += 1
#             moved_ids.append(r.get("id"))

#         if moved_ids:
#             placeholders = ",".join(["%s"] * len(moved_ids))
#             cur_write.execute(f"UPDATE vendor_contact_extracts SET moved_to_vendor = 1 WHERE id IN ({placeholders})", tuple(moved_ids))

#         conn.commit()
#         return {"message": f"Moved {len(moved_ids)}", "inserted": inserted, "moved_count": len(moved_ids), "success": True}
#     except Error as e:
#         conn.rollback()
#         logger.exception("move_all failed")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cur_read.close()
#         cur_write.close()
#         conn.close()