# # =================================Lead================================

from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.schemas import LeadCreate
from typing import Dict,Any
from fastapi import HTTPException
from sqlalchemy import func
from fapi.db.models import LeadORM
from datetime import datetime

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

        leads_data = [lead.__dict__ for lead in leads]
        for lead in leads_data:
            lead.pop('_sa_instance_state', None) 

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
        lead_dict = lead_data.dict()

        
        if not lead_dict.get("entry_date"):
            lead_dict["entry_date"] = datetime.utcnow()
        if not lead_dict.get("last_modified"):
            lead_dict["last_modified"] = datetime.utcnow()

        new_lead = LeadORM(**lead_dict)
        session.add(new_lead)
        session.commit()
        session.refresh(new_lead)
        return new_lead
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