from fastapi import APIRouter, Query, Depends, HTTPException, Security, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import LeadCreate, LeadUpdate, LeadMetricsResponse
from fapi.utils.lead_utils import (
    fetch_all_leads_paginated,
    fetch_all_leads,
    get_lead_by_id,
    create_lead,
    update_lead,
    delete_lead,
    create_candidate_from_lead,
    get_lead_suggestions,
    get_leads_version
)
from fapi.utils.avatar_dashboard_utils import get_lead_metrics

router = APIRouter()

security = HTTPBearer()

@router.get("/leads/paginated")
def get_leads_paginated(
    page: int = 1,
    limit: int = 100,
    search: str = None,
    search_by: str = "name",
    sort: str = Query("entry_date:desc"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return fetch_all_leads_paginated(db, page, limit, search, search_by, sort)

@router.get("/leads")
def get_all_leads(
    search: str = None,
    search_by: str = "name",
    sort: str = Query("entry_date:desc"),
    filters: str = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return fetch_all_leads(db, search, search_by, sort, filters)


@router.head("/leads")
def check_leads_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_leads_version(db)



@router.get("/leads/metrics", response_model=LeadMetricsResponse)
def get_lead_metrics_endpoint(db: Session = Depends(get_db)):
    metrics_data = get_lead_metrics(db)
    return {
        "success": True,
        "data": metrics_data,
        "message": "Lead metrics retrieved successfully"
    }


@router.get("/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    db_lead = get_lead_by_id(db, lead_id)
    if db_lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return db_lead


@router.post("/leads")
def create_new_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    return create_lead(db, lead)


@router.put("/leads/{lead_id}")
def update_existing_lead(lead_id: int, lead: LeadUpdate, db: Session = Depends(get_db)):
    return update_lead(db, lead_id, lead)


@router.delete("/leads/{lead_id}")
def delete_existing_lead(lead_id: int, db: Session = Depends(get_db)):
    return delete_lead(db, lead_id)


@router.post("/leads/{lead_id}/move-to-candidate")  
def move_lead_to_candidate(lead_id: int, db: Session = Depends(get_db)):
    return create_candidate_from_lead(db, lead_id)

@router.delete("/leads/movetocandidate/{lead_id}")
def remove_lead_from_candidate(lead_id: int, db: Session = Depends(get_db)):
    lead = get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.moved_to_candidate = False
    db.commit()
    return {"detail": f"Lead {lead_id} removed from candidate"}

@router.get("/leads/search-names/{search_term}")
def get_lead_suggestions_endpoint(
    search_term: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        results = get_lead_suggestions(search_term, db)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
