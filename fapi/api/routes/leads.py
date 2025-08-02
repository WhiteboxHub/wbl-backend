# fapi/api/routes/leads.py

from fastapi import APIRouter, Query, Path
from typing import Dict, Any
from fapi.db.models import Lead, LeadCreate
from fapi.utils.lead_utils import fetch_all_leads_paginated, get_lead_by_id, create_lead, update_lead, delete_lead

router = APIRouter()

@router.get("/leads_new", summary="Get all leads (paginated)")
def get_all_leads(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    return fetch_all_leads_paginated(page, limit)

@router.get("/leads_new/{lead_id}")
def read_lead(lead_id: int = Path(...)) -> Dict[str, Any]:
    return get_lead_by_id(lead_id)

@router.post("/leads_new", response_model=Lead)
def create_new_lead(lead: LeadCreate):
    return create_lead(lead)

@router.put("/leads_new/{lead_id}")
def update_existing_lead(lead_id: int, lead: LeadCreate) -> Dict[str, Any]:
    return update_lead(lead_id, lead)

@router.delete("/leads_new/{lead_id}")
def delete_existing_lead(lead_id: int) -> Dict[str, str]:
    return delete_lead(lead_id)
