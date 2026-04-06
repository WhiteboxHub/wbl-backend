from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from fapi.db.models import PotentialLeadORM
from fapi.db.schemas import PotentialLeadCreate, PotentialLeadUpdate
from fastapi import HTTPException, Response
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.core.cache import cache_result, invalidate_cache
import json

@cache_result(ttl=300, prefix="potential_leads")
def fetch_all_potential_leads(db: Session, search: str = None, search_by: str = "all", sort: str = None, filters: str = None):
    query = db.query(PotentialLeadORM)

    if search:
        if search_by == "id":
            if search.isdigit():
                query = query.filter(PotentialLeadORM.id == int(search))
            else:
                query = query.filter(False)
        elif search_by == "full_name":
            query = query.filter(PotentialLeadORM.full_name.ilike(f"%{search}%"))
        elif search_by == "email":
            query = query.filter(PotentialLeadORM.email.ilike(f"%{search}%"))
        elif search_by == "phone":
            query = query.filter(PotentialLeadORM.phone.ilike(f"%{search}%"))
        else:  # search_by == "all"
            query = query.filter(
                or_(
                    PotentialLeadORM.full_name.ilike(f"%{search}%"),
                    PotentialLeadORM.email.ilike(f"%{search}%"),
                    PotentialLeadORM.phone.ilike(f"%{search}%"),
                    PotentialLeadORM.profession.ilike(f"%{search}%"),
                    PotentialLeadORM.linkedin_id.ilike(f"%{search}%"),
                    PotentialLeadORM.location.ilike(f"%{search}%"),
                    PotentialLeadORM.outreach_connection_status.ilike(f"%{search}%"),
                    PotentialLeadORM.outreach_message_status.ilike(f"%{search}%"),
                )
            )

    if filters:
        try:
            filters_dict = json.loads(filters)
            for field, filter_config in filters_dict.items():
                if hasattr(PotentialLeadORM, field):
                    column = getattr(PotentialLeadORM, field)
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
                if hasattr(PotentialLeadORM, col):
                    column = getattr(PotentialLeadORM, col)
                    query = query.order_by(column.desc() if direction == "desc" else column.asc())

    leads = query.all()
    return {"data": leads, "total": len(leads)}

@cache_result(ttl=300, prefix="potential_leads")
def get_potential_lead_by_id(db: Session, lead_id: int):
    return db.query(PotentialLeadORM).filter(PotentialLeadORM.id == lead_id).first()

def create_potential_lead(db: Session, lead: PotentialLeadCreate):
    invalidate_cache("potential_leads")
    invalidate_cache("metrics")
    db_lead = PotentialLeadORM(**lead.model_dump())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead

def update_potential_lead(db: Session, lead_id: int, lead: PotentialLeadUpdate):
    invalidate_cache("potential_leads")
    invalidate_cache("metrics")
    db_lead = get_potential_lead_by_id(db, lead_id)
    if not db_lead:
        raise HTTPException(status_code=404, detail="Potential lead not found")
    for key, value in lead.model_dump(exclude_unset=True).items():
        setattr(db_lead, key, value)
    db.commit()
    db.refresh(db_lead)
    return db_lead
def delete_potential_lead(db: Session, lead_id: int):
    invalidate_cache("potential_leads")
    invalidate_cache("metrics")
    db_lead = get_potential_lead_by_id(db, lead_id)
    if not db_lead:
        raise HTTPException(status_code=404, detail="Potential lead not found")
    db.delete(db_lead)
    db.commit()
    return {"detail": "Potential lead deleted successfully"}

def get_potential_leads_version(db: Session) -> Response:
    return generate_version_for_model(db, PotentialLeadORM)
