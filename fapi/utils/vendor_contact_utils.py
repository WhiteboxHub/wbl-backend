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
