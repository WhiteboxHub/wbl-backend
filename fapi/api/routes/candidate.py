from typing import List
from fastapi import APIRouter, Query, Path, HTTPException
from fapi.db.models import (
    CandidateBase, CandidateUpdate,
    CandidatePlacement, CandidatePlacementCreate,
    CandidateMarketing, CandidateMarketingCreate, PaginatedCandidateResponse
)
from fapi.utils import candidate_utils
from fapi.utils.candidate_utils import (
    get_all_marketing_records, get_marketing_by_id, create_marketing, update_marketing, delete_marketing,
    get_all_placements, get_placement_by_id, create_placement, update_placement, delete_placement
)

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
    return get_all_marketing_records(page, limit)

@router.get("/candidate/marketing/{record_id}", summary="Get marketing record by ID")
def read_marketing_record(record_id: int = Path(...)):
    return get_marketing_by_id(record_id)

@router.post("/candidate/marketing", response_model=CandidateMarketing)
def create_marketing_record(record: CandidateMarketingCreate):
    return create_marketing(record)

@router.put("/candidate/marketing/{record_id}", response_model=CandidateMarketing)
def update_marketing_record(record_id: int, record: CandidateMarketingCreate):
    return update_marketing(record_id, record)

@router.delete("/candidate/marketing/{record_id}")
def delete_marketing_record(record_id: int):
    return delete_marketing(record_id)

# ------------------- Placements -------------------
@router.get("/candidate/placements")
def read_all_placements(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return get_all_placements(page, limit)

@router.get("/candidate/placements/{placement_id}")
def read_placement(placement_id: int = Path(...)):
    return get_placement_by_id(placement_id)

@router.post("/candidate/placements", response_model=CandidatePlacement)
def create_new_placement(placement: CandidatePlacementCreate):
    return create_placement(placement)

@router.put("/candidate/placements/{placement_id}", response_model=CandidatePlacement)
def update_existing_placement(placement_id: int, placement: CandidatePlacementCreate):
    return update_placement(placement_id, placement)

@router.delete("/candidate/placements/{placement_id}")
def delete_existing_placement(placement_id: int):
    return delete_placement(placement_id)
