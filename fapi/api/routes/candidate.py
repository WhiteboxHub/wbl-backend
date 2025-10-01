import logging
from fastapi import APIRouter, Query, Path, HTTPException, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fapi.utils.avatar_dashboard_utils import (
    get_placement_metrics,
    get_interview_metrics,
    candidate_interview_performance,
)

from fastapi import APIRouter, Query, Path, HTTPException,Depends
from fapi.utils import candidate_utils                                         
from fapi.db.schemas import CandidateBase, CandidateUpdate, PaginatedCandidateResponse,CandidatePlacementUpdate,CandidatePlacement,  CandidateMarketing,CandidatePlacementCreate,CandidateMarketingCreate,CandidateInterviewOut, CandidateCreate,CandidateInterviewCreate, CandidateInterviewUpdate,CandidatePreparationCreate,CandidatePreparationUpdate,CandidatePreparationOut, PlacementMetrics, InterviewMetrics, CandidateInterviewPerformanceResponse
from fapi.db.models import CandidateInterview,CandidateORM,CandidatePreparation, CandidateMarketingORM, CandidatePlacementORM, Batch , AuthUserORM

from sqlalchemy.orm import Session,joinedload,selectinload

from fapi.db.database import get_db,SessionLocal 
from fapi.utils.candidate_utils import get_all_candidates_paginated, serialize_interview 
from fapi.db import schemas
from typing import Dict, Any, List
from sqlalchemy import or_, func
import re

router = APIRouter()



logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# ------------------------Candidate------------------------------------

@router.get("/candidates", response_model=PaginatedCandidateResponse)
def list_candidates(
    page: int = 1,
    limit: int = 100,
    search: str = None,
    search_by: str = "all",
    sort: str = Query("enrolled_date:desc", description="Sort by field:direction (e.g., 'enrolled_date:desc')"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_all_candidates_paginated(db, page, limit, search, search_by, sort)

@router.get("/candidates/search", response_model=Dict[str, Any])
def search_candidates(
    term: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        filters = [
            CandidateORM.full_name.ilike(f"%{term}%"),
            CandidateORM.email.ilike(f"%{term}%"),
        ]
        normalized_term = re.sub(r"\D", "", term)
        if normalized_term:
            filters.append(func.replace(func.replace(CandidateORM.phone, "-", ""), " ", "").ilike(f"%{normalized_term}%"))
        if term.isdigit():
            filters.append(CandidateORM.id == int(term))
        results = db.query(CandidateORM).filter(or_(*filters)).all()
        data: List[Dict[str, Any]] = []
        for r in results:
            item = r.__dict__.copy()
            item.pop("_sa_instance_state", None)
            data.append(item)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/candidates/{candidate_id}", response_model=dict)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    candidate = candidate_utils.get_candidate_by_id(db, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.post("/candidates", response_model=int)
def create_candidate(candidate: CandidateCreate):
    return candidate_utils.create_candidate(candidate.dict(exclude_unset=True))

@router.put("/candidates/{candidate_id}")
def update_candidate(candidate_id: int, candidate: CandidateUpdate):
    candidate_utils.update_candidate(candidate_id, candidate.dict(exclude_unset=True))
    return {"message": "Candidate updated successfully"}

@router.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: int):
    candidate_utils.delete_candidate(candidate_id)
    return {"message": "Candidate deleted successfully"}



# ------------------- Marketing -------------------



@router.get("/candidate/marketing", summary="Get all candidate marketing records")
def read_all_marketing(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_all_marketing_records( page, limit)





@router.get("/candidate/marketing/{record_id}", summary="Get marketing record by ID")
def read_marketing_record(record_id: int = Path(...)):
    return candidate_utils.get_marketing_by_id(record_id)

@router.post("/candidate/marketing", response_model=CandidateMarketing)
def create_marketing_record(record: CandidateMarketingCreate):
    return candidate_utils.create_marketing(record)

@router.put("/candidate/marketing/{record_id}", response_model=CandidateMarketing)
def update_marketing_record(record_id: int, record: CandidateMarketingCreate):
    return candidate_utils.update_marketing(record_id, record)

@router.delete("/candidate/marketing/{record_id}")
def delete_marketing_record(record_id: int):
    return candidate_utils.delete_marketing(record_id)

# -------------------Candidate_Placements -------------------

@router.get("/candidate/placements")
def read_all_placements(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_all_placements(page, limit)


@router.get("/candidate/placements/metrics", response_model=PlacementMetrics)
def get_placement_metrics_endpoint(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_placement_metrics(db)


@router.get("/candidate/placements/{placement_id}", response_model=dict)
def read_placement(
    placement_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    placement = candidate_utils.get_placement_by_id(db, placement_id)
    if not placement:
        raise HTTPException(status_code=404, detail="Placement not found")
    return placement


@router.post("/candidate/placements", response_model=CandidatePlacement)
def create_new_placement(placement: CandidatePlacementCreate):
    return candidate_utils.create_placement(placement)


@router.put("/candidate/placements/{placement_id}", response_model=CandidatePlacement)
def update_existing_placement(placement_id: int, placement: CandidatePlacementCreate):
    return candidate_utils.update_placement(placement_id, placement)


@router.delete("/candidate/placements/{placement_id}")
def delete_existing_placement(placement_id: int):
    return candidate_utils.delete_placement(placement_id)


# -----------candidate interview metrics-------------


@router.get("/candidate/interviews/metrics", response_model=InterviewMetrics)
def get_interview_metrics_endpoint(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_interview_metrics(db)

@router.get("/interview/performance", response_model=CandidateInterviewPerformanceResponse)
def get_candidate_interview_performance(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    data = candidate_interview_performance(db)
    return {
        "success": True,
        "data": data,
        "message": "Candidate interview performance fetched successfully"
    }

# -------------------Candidate_interview -------------------
@router.post("/interviews", response_model=CandidateInterviewOut)
def create_interview(
    interview: CandidateInterviewCreate,
    db: Session = Depends(get_db),
):
    return candidate_utils.create_candidate_interview(db, interview)



@router.get("/interviews/{interview_id}", response_model=CandidateInterviewOut)
def read_candidate_interview(interview_id: int, db: Session = Depends(get_db)):
    db_obj = candidate_utils.get_candidate_interview_with_instructors(db, interview_id)

    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return serialize_interview(db_obj)


@router.get("/interviews", response_model=List[CandidateInterviewOut])
def list_interviews(db: Session = Depends(get_db)):
    interviews = candidate_utils.list_interviews_with_instructors(db)
    return [serialize_interview(i) for i in interviews]


@router.put("/interviews/{interview_id}", response_model=CandidateInterviewOut)
def update_interview(
    interview_id: int,
    updates: CandidateInterviewUpdate,
    db: Session = Depends(get_db),
):
    db_obj = candidate_utils.update_candidate_interview(db, interview_id, updates)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return db_obj


@router.delete("/interviews/{interview_id}")
def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    db_obj = candidate_utils.delete_candidate_interview(db, interview_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return {"detail": "Interview deleted successfully"}


# -------------------Candidate_Preparation -------------------

@router.post("/candidate_preparation", response_model=CandidatePreparationOut)
def create_prep(prep: CandidatePreparationCreate, db: Session = Depends(get_db)):
    return candidate_utils.create_candidate_preparation(db, prep)


@router.get("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def get_prep(prep_id: int, db: Session = Depends(get_db)):
    prep = candidate_utils.get_candidate_preparation(db, prep_id)
    if not prep:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return prep


@router.get("/candidate_preparations", response_model=list[CandidatePreparationOut])
def list_preps(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_all_preparations(db)

@router.put("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def update_prep(
    prep_id: int,
    updates: CandidatePreparationUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    updated = candidate_utils.update_candidate_preparation(db, prep_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return updated

@router.delete("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def delete_prep(
    prep_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    deleted = candidate_utils.delete_candidate_preparation(db, prep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return deleted

##--------------------------------search----------------------------------



@router.get("/candidates/search-names/{search_term}")
def get_candidate_suggestions(search_term: str, db: Session = Depends(get_db)):
    return candidate_utils.get_candidate_suggestions(search_term, db)



@router.get("/candidates/details/{candidate_id}")
def get_candidate_details(candidate_id: int, db: Session = Depends(get_db)):
    return candidate_utils.get_candidate_details(candidate_id, db)



@router.get("/candidates/sessions/{candidate_id}")
def get_candidate_sessions_route(candidate_id: int, db: Session = Depends(get_db)):
    return candidate_utils.get_candidate_sessions(candidate_id, db)
