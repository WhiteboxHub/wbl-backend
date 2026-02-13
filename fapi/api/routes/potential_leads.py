from fastapi import APIRouter, Query, Depends, HTTPException, Security, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import PotentialLeadCreate, PotentialLeadUpdate, PotentialLeadSchema
from fapi.utils.potential_lead_utils import (
    fetch_all_potential_leads,
    get_potential_lead_by_id,
    create_potential_lead,
    update_potential_lead,
    delete_potential_lead
)

router = APIRouter()
security = HTTPBearer()

@router.get("/potential-leads")
def get_potential_leads(
    search: str = None,
    search_by: str = "all",
    sort: str = Query("entry_date:desc"),
    filters: str = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return fetch_all_potential_leads(db, search, search_by, sort, filters)

@router.get("/potential-leads/{lead_id}", response_model=PotentialLeadSchema)
def get_lead(lead_id: int, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Security(security)):
    db_lead = get_potential_lead_by_id(db, lead_id)
    if db_lead is None:
        raise HTTPException(status_code=404, detail="Potential lead not found")
    return db_lead

@router.post("/potential-leads", response_model=PotentialLeadSchema)
def create_new_potential_lead(lead: PotentialLeadCreate, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Security(security)):
    return create_potential_lead(db, lead)

@router.put("/potential-leads/{lead_id}", response_model=PotentialLeadSchema)
def update_existing_potential_lead(lead_id: int, lead: PotentialLeadUpdate, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Security(security)):
    return update_potential_lead(db, lead_id, lead)

@router.delete("/potential-leads/{lead_id}")
def delete_existing_potential_lead(lead_id: int, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Security(security)):
    return delete_potential_lead(db, lead_id)