import asyncio
import mysql.connector
from mysql.connector import Error
from fastapi import HTTPException
from fapi.db.database import db_config
from fapi.db.schemas import VendorContactExtractCreate
from typing import List, Optional

async def get_all_vendor_contacts():
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM vendor_contact_extracts ORDER BY id DESC"

        await loop.run_in_executor(None, cursor.execute, query)
        rows = cursor.fetchall()
        return rows
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error fetching vendor contacts: {e}")
    finally:
        cursor.close()
        conn.close()

async def insert_vendor_contact(contact: VendorContactExtractCreate):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()

        query = """
            INSERT INTO vendor_contact_extracts (
                full_name, source_email, email, phone,
                linkedin_id, company_name, location,
                extraction_date, moved_to_vendor
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), 0)
        """
        values = (
            contact.full_name,
            contact.source_email,
            contact.email,
            contact.phone,
            contact.linkedin_id,
            contact.company_name,
            contact.location
        )

        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Insert error: {e}")
    finally:
        cursor.close()
        conn.close()

async def update_vendor_contact(contact_id: int, fields: dict):
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        set_clause = ", ".join([f"{key} = %s" for key in fields])
        values = list(fields.values())
        values.append(contact_id)

        query = f"""
            UPDATE vendor_contact_extracts
            SET {set_clause}
            WHERE id = %s
        """
        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vendor contact not found")

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Update error: {e}")
    finally:
        cursor.close()
        conn.close()

async def delete_vendor_contact(contact_id: int):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = "DELETE FROM vendor_contact_extracts WHERE id = %s"
        await loop.run_in_executor(None, cursor.execute, query, (contact_id,))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vendor contact not found")

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Delete error: {e}")
    finally:
        cursor.close()
        conn.close()

async def bulk_delete_vendor_contacts(contact_ids: List[int]):
    """
    Bulk delete vendor contacts by IDs
    """
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")
    
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        
        # Create placeholders for the IN clause
        placeholders = ','.join(['%s'] * len(contact_ids))
        query = f"DELETE FROM vendor_contact_extracts WHERE id IN ({placeholders})"
        
        await loop.run_in_executor(None, cursor.execute, query, tuple(contact_ids))
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count
        
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk delete error: {e}")
    finally:
        cursor.close()
        conn.close()

async def bulk_delete_moved_contacts():
    """
    Bulk delete all contacts where moved_to_vendor = 1 (Yes)
    """
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        
        query = "DELETE FROM vendor_contact_extracts WHERE moved_to_vendor = 1"
        
        await loop.run_in_executor(None, cursor.execute, query)
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count
        
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk delete moved contacts error: {e}")
    finally:
        cursor.close()
        conn.close()

async def move_contacts_to_vendor(contact_ids: Optional[List[int]] = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    cur_select = None
    cur_exec = None
    try:

        skipped_already_moved = 0
        if contact_ids:

            where_clause = f"id IN ({','.join(['%s'] * len(contact_ids))}) AND moved_to_vendor = 0"
            where_params = tuple(contact_ids)

            cur_check = conn.cursor()
            check_query = f"SELECT id FROM vendor_contact_extracts WHERE id IN ({','.join(['%s'] * len(contact_ids))}) AND moved_to_vendor = 1"
            await loop.run_in_executor(None, cur_check.execute, check_query, tuple(contact_ids))
            skipped_already_moved = len(cur_check.fetchall() or [])
            cur_check.close()
        else:
            where_clause = "moved_to_vendor = 0"
            where_params = tuple()

        cur_select = conn.cursor(dictionary=True)
        select_query = f"""
            SELECT id, full_name, email, phone, linkedin_id, company_name, location, linkedin_internal_id
            FROM vendor_contact_extracts
            WHERE {where_clause}
        """
        await loop.run_in_executor(None, cur_select.execute, select_query, where_params)
        rows = cur_select.fetchall()
        if not rows:
            return {"inserted": 0, "skipped_already_moved": skipped_already_moved, "count": 0}

        cur_exec = conn.cursor()
        insert_query = (
            """
            INSERT IGNORE INTO vendor (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
        )
        exist_query = "SELECT id FROM vendor WHERE (email = %s) OR (linkedin_id = %s) LIMIT 1"

        inserted = 0
        moved_ids: List[int] = []

        for r in rows:
            email = r.get("email")
            linkedin = r.get("linkedin_id")
            await loop.run_in_executor(None, cur_exec.execute, exist_query, (email, linkedin))
            exists = cur_exec.fetchone()
            if exists:
                continue

            values = (
                r.get("full_name"),
                r.get("phone"),
                email,
                linkedin,
                r.get("company_name"),
                r.get("location"),
                r.get("linkedin_internal_id"),
            )
            await loop.run_in_executor(None, cur_exec.execute, insert_query, values)
            if getattr(cur_exec, "rowcount", 0) > 0:
                inserted += 1
                moved_ids.append(r.get("id"))

        if moved_ids:
            fmt = ",".join(["%s"] * len(moved_ids))
            update_query = f"UPDATE vendor_contact_extracts SET moved_to_vendor = 1 WHERE id IN ({fmt})"
            await loop.run_in_executor(None, cur_exec.execute, update_query, tuple(moved_ids))

        conn.commit()
        return {
            "inserted": inserted,
            "skipped_already_moved": skipped_already_moved,
            "count": len(moved_ids),
        }

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Move error: {e}")
    finally:
        if cur_select:
            cur_select.close()
        if cur_exec:
            cur_exec.close()
        conn.close()


