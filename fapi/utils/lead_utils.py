from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict,Any
from fapi.db.database import SessionLocal
from fapi.db.models import LeadORM
from fapi.db.schemas import LeadCreate, LeadUpdate
from fastapi import HTTPException
from sqlalchemy import func, or_

def fetch_all_leads_paginated(db: Session, page: int, limit: int, search: str, search_by: str):
    query = db.query(LeadORM)

    if search:
        if search_by == "id":
            try:
                query = query.filter(LeadORM.id == int(search))
            except ValueError:
                # If search is not a valid integer, return empty results
                query = query.filter(LeadORM.id == -1)
        elif search_by == "full_name":
            query = query.filter(LeadORM.full_name.ilike(f"%{search}%"))
        elif search_by == "email":
            query = query.filter(LeadORM.email.ilike(f"%{search}%"))
        elif search_by == "phone":
            query = query.filter(LeadORM.phone.ilike(f"%{search}%"))
        else:  # search_by == "all"
            query = query.filter(
                or_(
                    LeadORM.full_name.ilike(f"%{search}%"),
                    LeadORM.email.ilike(f"%{search}%"),
                    LeadORM.phone.ilike(f"%{search}%"),
                )
            )

    total = query.count()
    leads = query.offset((page - 1) * limit).limit(limit).all()
    return {"data": leads, "total": total, "page": page, "limit": limit}

def get_lead_by_id(db: Session, lead_id: int):
    return db.query(LeadORM).filter(LeadORM.id == lead_id).first()


def create_lead(db: Session, lead: LeadCreate):
    db_lead = LeadORM(**lead.dict())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead


def update_lead(db: Session, lead_id: int, lead: LeadUpdate):
    db_lead = get_lead_by_id(db, lead_id)
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in lead.dict(exclude_unset=True).items():
        setattr(db_lead, key, value)
    db.commit()
    db.refresh(db_lead)
    return db_lead


def delete_lead(db: Session, lead_id: int):
    db_lead = get_lead_by_id(db, lead_id)
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(db_lead)
    db.commit()
    return {"detail": "Lead deleted successfully"}


def check_and_reset_moved_to_candidate(db: Session, lead_id: int):
    lead = db.query(LeadORM).filter(LeadORM.id == lead_id).first()
    if lead and lead.moved_to_candidate:
        lead.moved_to_candidate = False
        db.commit()
    return lead


def delete_candidate_by_email_and_phone(db: Session, email: str, phone: str):
    pass


def create_candidate_from_lead(db: Session, lead_id: int):
    lead = get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.moved_to_candidate = True
    db.commit()
    return {"detail": f"Lead {lead_id} moved to candidate"}


def get_lead_info_mark_move_to_candidate_true(db: Session, lead_id: int):
    lead = get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.moved_to_candidate = True
    db.commit()
    return lead

