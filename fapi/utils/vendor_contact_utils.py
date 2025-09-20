import asyncio
import mysql.connector
from mysql.connector import Error
from fastapi import HTTPException
from fapi.db.database import db_config
from fapi.db.schemas import VendorContactExtractCreate

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

from typing import List, Optional

async def move_contacts_to_vendor(contact_ids: Optional[List[int]] = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    cur_select = None
    cur_exec = None
    try:
        # Determine selection criteria
        skipped_already_moved = 0
        skipped_already_moved_ids: List[int] = []
        if contact_ids and len(contact_ids) > 0:
            # Enforce only records with moved_to_vendor = 0 are processed
            where_clause = f"id IN ({','.join(['%s'] * len(contact_ids))}) AND moved_to_vendor = 0"
            where_params = tuple(contact_ids)
            # Precompute how many of the provided IDs are already marked as moved (to report back)
            cur_check = conn.cursor()
            check_query = f"SELECT id FROM vendor_contact_extracts WHERE id IN ({','.join(['%s'] * len(contact_ids))}) AND moved_to_vendor = 1"
            await loop.run_in_executor(None, cur_check.execute, check_query, tuple(contact_ids))
            skipped_already_moved_ids = [row[0] for row in (cur_check.fetchall() or [])]
            skipped_already_moved = len(skipped_already_moved_ids)
            cur_check.close()
        else:
            where_clause = "moved_to_vendor = 0"
            where_params = tuple()

        # Fetch contacts to move
        cur_select = conn.cursor(dictionary=True)
        select_query = f"""
            SELECT id, full_name, email, phone, linkedin_id, company_name, location, linkedin_internal_id
            FROM vendor_contact_extracts
            WHERE {where_clause}
        """
        await loop.run_in_executor(None, cur_select.execute, select_query, where_params)
        rows = cur_select.fetchall()
        if not rows:
            return {"message": "No contacts to move", "inserted": 0, "skipped_already_moved": skipped_already_moved, "count": 0}

        # Prepare cursors and statements
        cur_exec = conn.cursor()
        insert_query = (
            """
            INSERT IGNORE INTO vendor (full_name, phone_number, email, linkedin_id, company_name, location, linkedin_internal_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
        )

        inserted = 0
        moved_ids: List[int] = []

        for r in rows:
            email = r.get("email")

            values = (
                r.get("full_name"),
                r.get("phone"),
                email,
                r.get("linkedin_id"),
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
        total_attempted = len(rows)
        message = f"Inserted {inserted}, skipped {skipped_already_moved} already moved"
        return {
            "message": message,
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
