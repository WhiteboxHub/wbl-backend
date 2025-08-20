# fapi/api/routes/candidate.py
from fastapi import APIRouter, Query, Path, HTTPException,Depends
from fapi.utils import candidate_utils 
from fapi.db.schemas import CandidateBase, CandidateUpdate, PaginatedCandidateResponse, CandidatePlacement,  CandidateMarketing,CandidatePlacementCreate,CandidateMarketingCreate, CandidateInterviewOut, CandidateInterviewCreate, CandidateInterviewUpdate
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import CandidateInterview
from typing import List




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
    return db.query(CandidateInterview).offset(skip).limit(limit).all()


@router.get("/{interview_id}", response_model=CandidateInterviewOut)
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

