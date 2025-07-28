# =================================Lead================================
from fastapi import HTTPException
from fapi.db import get_connection
from typing import Dict, Any, List
from datetime import datetime, date

def fetch_all_leads_paginated(page: int, limit: int) -> Dict[str, Any]:
    offset = (page - 1) * limit
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as total FROM leads_new")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT * FROM leads_new ORDER BY id DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        leads = cursor.fetchall()

        for lead in leads:
            for field in ["closed_date", "entry_date", "last_modified"]:
                if isinstance(lead.get(field), (datetime, date)):
                    lead[field] = lead[field].isoformat()

        return {"page": page, "limit": limit, "total": total, "data": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()



def create_lead(data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())

        query = f"INSERT INTO leads_new ({columns}) VALUES ({placeholders})"
        cursor.execute(query, values)
        conn.commit()
        data["id"] = cursor.lastrowid
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
# def create_lead(data: Dict[str, Any]):
#     conn = get_connection()
#     cursor = conn.cursor(dictionary=True)
#     try:
#         columns = ", ".join(data.keys())
#         placeholders = ", ".join(["%s"] * len(data))
#         values = tuple(data.values())

#         query = f"INSERT INTO leads_new ({columns}) VALUES ({placeholders})"
#         cursor.execute(query, values)
#         conn.commit()
#         data["id"] = cursor.lastrowid
#         return data
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()

def update_lead(lead_id: int, data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        set_clause = ", ".join([f"{key}=%s" for key in data])
        values = list(data.values()) + [lead_id]

        cursor.execute(f"UPDATE leads_new SET {set_clause} WHERE id=%s", values)
        conn.commit()

        return {"id": lead_id, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

def delete_lead(lead_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM leads_new WHERE id=%s", (lead_id,))
        conn.commit()
        return {"message": "Lead deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
