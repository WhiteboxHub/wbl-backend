from fastapi import APIRouter, Query, Depends, HTTPException, Security,Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from sqlalchemy import text, func
import hashlib
from fapi.db.schemas import LeadCreate, LeadUpdate, LeadMetricsResponse
from fapi.db.models import LeadORM
from fapi.utils.lead_utils import (
    fetch_all_leads_paginated,
    fetch_all_leads,
    get_lead_by_id,
    create_lead,
    update_lead,
    delete_lead,
    check_and_reset_moved_to_candidate,
    delete_candidate_by_email_and_phone,
    create_candidate_from_lead,
    get_lead_info_mark_move_to_candidate_true,
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
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(LeadORM.id).label("max_id"),
            func.date_format(func.max(LeadORM.entry_date), '%Y-%m-%d %H:%i:%s').label("max_entry"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        LeadORM.id,
                        func.coalesce(LeadORM.full_name, ''),
                        func.coalesce(LeadORM.email, ''),
                        func.coalesce(LeadORM.phone, ''),
                        func.coalesce(LeadORM.status, '')
                    )
                )
            ).label("checksum")
        ).first()
        
        response = Response(status_code=200)
        if result:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.max_entry}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["X-Total-Count"] = str(result.cnt)
            response.headers["X-Max-ID"] = str(result.max_id)
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"
        
        return response
        
    except Exception as e:
        print(f"[ERROR] HEAD /leads failed: {e}")
        import traceback
        traceback.print_exc()
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


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