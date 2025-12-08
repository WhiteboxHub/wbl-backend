# # vendor_contact_utils.py
# import logging
# from typing import List, Optional
# from fastapi import HTTPException
# from sqlalchemy.orm import Session
# from sqlalchemy import select
# from fapi.db.models import VendorContactExtractsORM
# from fapi.db.schemas import (
#     VendorContactExtract,
#     VendorContactExtractCreate,
#     VendorContactExtractUpdate,
# )

# logger = logging.getLogger(__name__)


# async def get_all_vendor_contacts(db: Session) -> List[VendorContactExtract]:
#     """Fetch all vendor contacts"""
#     try:
#         result = db.query(VendorContactExtractsORM).all()
#         return result
#     except Exception as e:
#         logger.error(f"Error fetching all vendor contacts: {e}")
#         raise HTTPException(status_code=500, detail="Error fetching vendor contacts")


# async def get_vendor_contact_by_id(contact_id: int, db: Session) -> VendorContactExtract:
#     """Fetch a specific vendor contact by ID"""
#     try:
#         contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
#         if not contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")
#         return contact
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error fetching vendor contact by ID: {e}")
#         raise HTTPException(status_code=500, detail="Error fetching vendor contact")


# async def insert_vendor_contact(contact: VendorContactExtractCreate, db: Session) -> VendorContactExtract:
#     """Create a new vendor contact"""
#     try:
#         new_contact = VendorContactExtractsORM(**contact.dict())
#         db.add(new_contact)
#         db.commit()
#         db.refresh(new_contact)
#         return new_contact
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Error creating vendor contact: {e}")
#         raise HTTPException(status_code=500, detail="Error creating vendor contact")


# async def update_vendor_contact(
#     contact_id: int, 
#     update_data: VendorContactExtractUpdate, 
#     db: Session
# ) -> VendorContactExtract:
#     """Update an existing vendor contact"""
#     try:
#         contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
#         if not contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")
        
#         for key, value in update_data.dict(exclude_unset=True).items():
#             setattr(contact, key, value)
        
#         db.commit()
#         db.refresh(contact)
#         return contact
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Error updating vendor contact: {e}")
#         raise HTTPException(status_code=500, detail="Error updating vendor contact")


# async def delete_vendor_contact(contact_id: int, db: Session) -> dict:
#     """Delete a vendor contact"""
#     try:
#         contact = db.query(VendorContactExtractsORM).filter(
#             VendorContactExtractsORM.id == contact_id
#         ).first()
#         if not contact:
#             raise HTTPException(status_code=404, detail="Vendor contact not found")
        
#         db.delete(contact)
#         db.commit()
#         return {"message": "Vendor contact deleted successfully"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Error deleting vendor contact: {e}")
#         raise HTTPException(status_code=500, detail="Error deleting vendor contact")










# backend/fapi/utils/vendor_contact_utils.py
import asyncio
import mysql.connector
from mysql.connector import Error
from fastapi import HTTPException
from typing import Dict, Any
import logging

from fapi.db.database import db_config

logger = logging.getLogger(__name__)


async def _get_conn():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))


async def get_all_vendor_contacts():
    conn = await _get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vendor_contact_extracts ORDER BY id DESC")
        results = cursor.fetchall() or []
        for row in results:
            if "moved_to_vendor" in row:
                row["moved_to_vendor"] = bool(row["moved_to_vendor"])
        return results
    except Error as e:
        logger.error("Failed to fetch contacts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


async def update_vendor_contact(contact_id: int, fields: dict):
    conn = await _get_conn()
    cursor = conn.cursor()
    try:
        valid_cols = {
            "full_name",
            "email",
            "phone",
            "linkedin_id",
            "company_name",
            "location",
            "source_email",
            "extraction_date",
            "moved_to_vendor",
            "internal_linkedin_id",
        }

        filtered = {}
        for k, v in fields.items():
            if k in valid_cols and v is not None:
                if k == "moved_to_vendor":
                    if isinstance(v, str):
                        filtered[k] = 1 if v.lower() in ["true", "1", "yes"] else 0
                    elif isinstance(v, bool):
                        filtered[k] = 1 if v else 0
                    else:
                        filtered[k] = 1 if int(v) == 1 else 0
                else:
                    filtered[k] = v

        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        set_clause = ", ".join([f"{k}=%s" for k in filtered.keys()])
        values = list(filtered.values()) + [contact_id]
        query = f"UPDATE vendor_contact_extracts SET {set_clause} WHERE id=%s"
        cursor.execute(query, values)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
    except HTTPException:
        raise
    except Error as e:
        conn.rollback()
        logger.error("Failed to update contact %s: %s", contact_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update error: {e}")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


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
        logger.error("Failed to insert contact: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Insert error: {e}")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


async def move_all_contacts_to_vendor() -> Dict[str, Any]:
    conn = await _get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor_write = conn.cursor()
    try:
        cursor.execute("SELECT * FROM vendor_contact_extracts WHERE moved_to_vendor = 0")
        rows = cursor.fetchall() or []
        if not rows:
            return {"message": "All contacts already moved", "inserted": 0, "moved_count": 0, "success": True}

        insert_query = """
            INSERT IGNORE INTO vendor
            (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
        """

        moved_ids = []
        inserted = 0
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
            moved_ids.append(r["id"])

        if moved_ids:
            placeholders = ",".join(["%s"] * len(moved_ids))
            cursor_write.execute(f"UPDATE vendor_contact_extracts SET moved_to_vendor=1 WHERE id IN ({placeholders})", moved_ids)

        conn.commit()
        return {"message": f"Moved {len(moved_ids)} contacts", "inserted": inserted, "moved_count": len(moved_ids), "success": True}
    except Error as e:
        conn.rollback()
        logger.error("Failed to move contacts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Move error: {e}")
    finally:
        try:
            cursor.close()
            cursor_write.close()
            conn.close()
        except Exception:
            pass



