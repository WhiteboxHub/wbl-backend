# # =================================Lead================================
# from fastapi import HTTPException
# from fapi.db import get_connection
# from typing import Dict, Any, List
# from datetime import datetime, date

# def fetch_all_leads_paginated(page: int, limit: int) -> Dict[str, Any]:
#     offset = (page - 1) * limit
#     conn = get_connection()
#     cursor = conn.cursor(dictionary=True)
#     try:
#         cursor.execute("SELECT COUNT(*) as total FROM leads_new")
#         total = cursor.fetchone()["total"]

#         cursor.execute(
#             "SELECT * FROM leads_new ORDER BY id DESC LIMIT %s OFFSET %s",
#             (limit, offset)
#         )
#         leads = cursor.fetchall()

#         for lead in leads:
#             for field in ["closed_date", "entry_date", "last_modified"]:
#                 if isinstance(lead.get(field), (datetime, date)):
#                     lead[field] = lead[field].isoformat()

#         return {"page": page, "limit": limit, "total": total, "data": leads}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()



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
# # def create_lead(data: Dict[str, Any]):
# #     conn = get_connection()
# #     cursor = conn.cursor(dictionary=True)
# #     try:
# #         columns = ", ".join(data.keys())
# #         placeholders = ", ".join(["%s"] * len(data))
# #         values = tuple(data.values())

# #         query = f"INSERT INTO leads_new ({columns}) VALUES ({placeholders})"
# #         cursor.execute(query, values)
# #         conn.commit()
# #         data["id"] = cursor.lastrowid
# #         return data
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))
# #     finally:
# #         cursor.close()
# #         conn.close()

# def update_lead(lead_id: int, data: Dict[str, Any]):
#     conn = get_connection()
#     cursor = conn.cursor(dictionary=True)
#     try:
#         set_clause = ", ".join([f"{key}=%s" for key in data])
#         values = list(data.values()) + [lead_id]

#         cursor.execute(f"UPDATE leads_new SET {set_clause} WHERE id=%s", values)
#         conn.commit()

#         return {"id": lead_id, **data}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()

# def delete_lead(lead_id: int):
#     conn = get_connection()
#     cursor = conn.cursor()
#     try:
#         cursor.execute("DELETE FROM leads_new WHERE id=%s", (lead_id,))
#         conn.commit()
#         return {"message": "Lead deleted successfully"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         cursor.close()
#         conn.close()



from sqlalchemy.orm import Session
from fapi.db import SessionLocal
from fapi.models import LeadCreate
from typing import Dict,Any
from fastapi import HTTPException
from sqlalchemy import func
from fapi.schemas import LeadORM
def fetch_all_leads_paginated(page: int, limit: int) -> Dict[str, any]:
    db: Session = SessionLocal()
    try:
        total = db.query(func.count(LeadORM.id)).scalar()
        offset = (page - 1) * limit

        leads = (
            db.query(LeadORM)
            .order_by(LeadORM.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Convert SQLAlchemy models to dict
        leads_data = [lead.__dict__ for lead in leads]
        for lead in leads_data:
            lead.pop('_sa_instance_state', None)  # remove SQLAlchemy internal data

        return {"page": page, "limit": limit, "total": total, "data": leads_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()




def get_lead_by_id(lead_id: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        lead_dict = lead.__dict__.copy()
        lead_dict.pop("_sa_instance_state", None)

        for field in ["entry_date", "closed_date", "last_modified"]:
            if lead_dict.get(field):
                lead_dict[field] = lead_dict[field].isoformat()

        return lead_dict
    finally:
        session.close()
def create_lead(lead_data: LeadCreate) -> LeadORM:
    session = SessionLocal()
    try:
        new_lead = LeadORM(**lead_data.dict())
        session.add(new_lead)
        session.commit()
        session.refresh(new_lead)
        return new_lead  # ✅ SQLAlchemy instance
    finally:
        session.close()
     


def update_lead(lead_id: int, lead_data: LeadCreate) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        for key, value in lead_data.dict(exclude_unset=True).items():
            setattr(lead, key, value)

        session.commit()
        session.refresh(lead)

        lead_dict = lead.__dict__.copy()
        lead_dict.pop("_sa_instance_state", None)
        return lead_dict
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
def delete_lead(lead_id: int) -> Dict[str, str]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        session.delete(lead)
        session.commit()
        return {"message": "Lead deleted successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()