# fapi/api/routes/candidate.py
from fapi.utils.avatar_dashboard_utils import (
    get_placement_metrics,
    get_interview_metrics,
)
from fastapi import APIRouter, Query, Path, HTTPException,Depends
from fapi.utils import candidate_utils 
from fapi.db.schemas import CandidateBase, CandidateUpdate, PaginatedCandidateResponse, CandidatePlacement,  CandidateMarketing,CandidatePlacementCreate,CandidateMarketingCreate,CandidateInterviewOut, CandidateInterviewCreate, CandidateInterviewUpdate,CandidatePreparationCreate,CandidatePreparationUpdate,CandidatePreparationOut, PlacementMetrics, InterviewMetrics
from fapi.db.models import CandidateInterview,CandidateStatus
from sqlalchemy.orm import Session
from fapi.db.database import get_db

router = APIRouter()



# ------------------------Candidate------------------------------------

@router.get("/candidates", response_model=PaginatedCandidateResponse)
def list_candidates(page: int = 1, limit: int = 100):
    return candidate_utils.get_all_candidates_paginated(page, limit)


@router.get("/candidates/{candidate_id}", response_model=dict)
def get_candidate(candidate_id: int):
    candidate = candidate_utils.get_candidate_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.post("/candidates", response_model=int)
def create_candidate(candidate: CandidateBase):
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
def read_all_marketing(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return candidate_utils.get_all_marketing_records(page, limit)


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
def read_all_placements(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return candidate_utils.get_all_placements(page, limit)


@router.get("/candidate/placements/metrics", response_model=PlacementMetrics)
def get_placement_metrics_endpoint(db: Session = Depends(get_db)):
    return get_placement_metrics(db)

@router.get("/candidate/placements/{placement_id}")
def read_placement(placement_id: int = Path(...)):
    return candidate_utils.get_placement_by_id(placement_id)

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
def get_interview_metrics_endpoint(db: Session = Depends(get_db)):
    return get_interview_metrics(db)


# -------------------Candidate_interview -------------------

@router.post("/", response_model=CandidateInterviewOut)
def create_interview(interview: CandidateInterviewCreate, db: Session = Depends(get_db)):
    return candidate_utils.create_candidate_interview(db, interview)



@router.get("/interviews", response_model=list[CandidateInterviewOut])
def list_interviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    # Sort interviews by date descending to get recent interviews first
    return (
        db.query(CandidateInterview)
        .order_by(CandidateInterview.interview_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

@router.get("/interview/{interview_id}", response_model=CandidateInterviewOut)
def read_candidate_interview(interview_id: int, db: Session = Depends(get_db)):
    db_obj = candidate_utils.get_candidate_interview(db, interview_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return db_obj



@router.put("/{interview_id}", response_model=CandidateInterviewOut)
def update_interview(interview_id: int, updates: CandidateInterviewUpdate, db: Session = Depends(get_db)):
    db_obj = candidate_utils.update_candidate_interview(db, interview_id, updates)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return db_obj

@router.delete("/{interview_id}")
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
def list_preps(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return candidate_utils.get_all_preparations(db, skip, limit)

@router.put("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def update_prep(prep_id: int, updates: CandidatePreparationUpdate, db: Session = Depends(get_db)):
    updated = candidate_utils.update_candidate_preparation(db, prep_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return updated

@router.delete("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def delete_prep(prep_id: int, db: Session = Depends(get_db)):
    deleted = candidate_utils.delete_candidate_preparation(db, prep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return deleted

