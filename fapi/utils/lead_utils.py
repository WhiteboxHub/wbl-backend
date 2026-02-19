
from sqlalchemy.orm import Session
from typing import Dict,Any
import json
from fapi.db.database import SessionLocal
from fapi.db.models import LeadORM
from fapi.db.schemas import LeadCreate, LeadUpdate
from fastapi import HTTPException
from sqlalchemy import or_, cast, String,func

def fetch_all_leads_paginated(db: Session, page: int, limit: int, search: str, search_by: str, sort: str):
    query = db.query(LeadORM)

    if search:
        if search_by == "id":
            if search.isdigit():
                query = query.filter(LeadORM.id == int(search))
            else:
                query = query.filter(False)  
        elif search_by == "full_name":
            query = query.filter(LeadORM.full_name.ilike(f"%{search}%"))
        elif search_by == "email":
            query = query.filter(LeadORM.email.ilike(f"%{search}%"))
        elif search_by == "phone":
            query = query.filter(cast(LeadORM.phone, String).ilike(f"%{search}%"))
        else:  # search_by == "all"
            query = query.filter(
                or_(
                    LeadORM.full_name.ilike(f"%{search}%"),
                    LeadORM.email.ilike(f"%{search}%"),
                    cast(LeadORM.phone, String).ilike(f"%{search}%"),
                )
            )

    if sort:
        sort_fields = sort.split(",")
        for field in sort_fields:
            col, direction = field.split(":")
            column = getattr(LeadORM, col)
            query = query.order_by(column.desc() if direction == "desc" else column.asc())

    total = query.count()
    leads = query.offset((page - 1) * limit).limit(limit).all()
    return {"data": leads, "total": total, "page": page, "limit": limit}

def fetch_all_leads(db: Session, search: str = None, search_by: str = "name", sort: str = None, filters: str = None):
    """Fetch all leads without pagination for AG Grid"""
    query = db.query(LeadORM)

    if search:
        if search_by == "id":
            if search.isdigit():
                query = query.filter(LeadORM.id == int(search))
            else:
                query = query.filter(False)  
        elif search_by == "full_name":
            query = query.filter(LeadORM.full_name.ilike(f"%{search}%"))
        elif search_by == "email":
            query = query.filter(LeadORM.email.ilike(f"%{search}%"))
        elif search_by == "phone":
            query = query.filter(cast(LeadORM.phone, String).ilike(f"%{search}%"))
        else:  
            query = query.filter(
                or_(
                    LeadORM.full_name.ilike(f"%{search}%"),
                    LeadORM.email.ilike(f"%{search}%"),
                    cast(LeadORM.phone, String).ilike(f"%{search}%"),
                )
            )

    if filters:
        try:
            filters_dict = json.loads(filters)
            for field, filter_config in filters_dict.items():
                if hasattr(LeadORM, field):
                    column = getattr(LeadORM, field)
                    filter_type = filter_config.get('type')
                    filter_value = filter_config.get('filter')
                    
                    if filter_type == 'contains':
                        query = query.filter(column.ilike(f"%{filter_value}%"))
                    elif filter_type == 'equals':
                        query = query.filter(column == filter_value)
                    elif filter_type == 'startsWith':
                        query = query.filter(column.ilike(f"{filter_value}%"))
                    elif filter_type == 'endsWith':
                        query = query.filter(column.ilike(f"%{filter_value}"))
        except (json.JSONDecodeError, KeyError):
           
            pass

    if sort:
        sort_fields = sort.split(",")
        for field in sort_fields:
            if ":" in field:
                col, direction = field.split(":")
                if hasattr(LeadORM, col):
                    column = getattr(LeadORM, col)
                    query = query.order_by(column.desc() if direction == "desc" else column.asc())

 
    leads = query.all()
    total = len(leads)
    
    return {"data": leads, "total": total}

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

def get_lead_suggestions(search_term: str, db: Session):
    """
    Get lead suggestions based on search term for name or email.
    """
    try:
        results = (
            db.query(LeadORM.id, LeadORM.full_name, LeadORM.email)
            .filter(
                or_(
                    LeadORM.full_name.ilike(f"%{search_term}%"),
                    LeadORM.email.ilike(f"%{search_term}%")
                )
            )
            .limit(10)
            .all()
        )
        return [{"id": r.id, "name": r.full_name, "email": r.email} for r in results]
    except Exception as e:
        print(f"Error fetching lead suggestions: {e}")
        return []
