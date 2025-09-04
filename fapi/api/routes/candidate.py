# fapi/api/routes/candidate.py
from fapi.utils.avatar_dashboard_utils import (
    get_placement_metrics,
    get_interview_metrics,
)
from fastapi import APIRouter, Query, Path, HTTPException,Depends
from fapi.utils import candidate_utils 
from fapi.db.schemas import CandidateBase, CandidateUpdate, PaginatedCandidateResponse, CandidatePlacement,  CandidateMarketing,CandidatePlacementCreate,CandidateMarketingCreate,CandidateInterviewOut, CandidateInterviewCreate, CandidateInterviewUpdate,CandidatePreparationCreate,CandidatePreparationUpdate,CandidatePreparationOut, PlacementMetrics, InterviewMetrics
from fapi.db.models import CandidateInterview,CandidateORM,CandidatePreparation, CandidateMarketingORM, CandidatePlacementORM, Batch , AuthUserORM
from sqlalchemy.orm import Session,joinedload
from fapi.db.database import get_db,SessionLocal
from fapi.db import schemas
from typing import Dict, Any, List
from sqlalchemy import or_, func
import re
router = APIRouter()



# ------------------------Candidate------------------------------------

@router.get("/candidates", response_model=PaginatedCandidateResponse)
def list_candidates(page: int = 1, limit: int = 100):
    return candidate_utils.get_all_candidates_paginated(page, limit)


@router.get("/candidates/search", response_model=Dict[str, Any])
def search_candidates(term: str, db: Session = Depends(get_db)):
    try:
        filters = [
            CandidateORM.full_name.ilike(f"%{term}%"),
            CandidateORM.email.ilike(f"%{term}%"),
        ]


        normalized_term = re.sub(r"\D", "", term)
        if normalized_term:
            # Also strip non-digits in DB phone
            filters.append(func.replace(func.replace(CandidateORM.phone, "-", ""), " ", "").ilike(f"%{normalized_term}%"))

        # --- ID handling ---
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


@router.get("/candidates/search", response_model=Dict[str, Any])
def search_candidates(term: str, db: Session = Depends(get_db)):
    try:
        filters = []

        # Search by full_name, email, or phone (case-insensitive)
        filters.append(CandidateORM.full_name.ilike(f"%{term}%"))
        filters.append(CandidateORM.email.ilike(f"%{term}%"))
        filters.append(CandidateORM.phone.ilike(f"%{term}%"))

        # If term is a digit, also search by id
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


@router.get("/interviews", response_model=schemas.PaginatedInterviews)
def list_interviews(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(CandidateInterview).options(joinedload(CandidateInterview.candidate))

    total = query.count()

    interviews = (
        query.order_by(CandidateInterview.interview_date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": interviews,
        "total": total,
        "page": page,
        "per_page": per_page,
    }

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

##--------------------------------search----------------------------------



@router.get("/candidates/search-names/{search_term}")
def get_candidate_suggestions(search_term: str, db: Session = Depends(get_db)):
    """Get candidate name suggestions for dropdown"""
    if not search_term or len(search_term.strip()) < 2:
        return []
    
    try:
        candidates = (
            db.query(CandidateORM.id, CandidateORM.full_name, CandidateORM.email)
            .filter(CandidateORM.full_name.ilike(f"%{search_term}%"))
            .limit(10)
            .all()
        )
        
        return [
            {
                "id": candidate.id,
                "name": candidate.full_name,
                "email": candidate.email or "No email"
            }
            for candidate in candidates
        ]
    except Exception as e:
        return {"error": str(e)}
@router.get("/candidates/details/{candidate_id}")
def get_candidate_details(candidate_id: int, db: Session = Depends(get_db)):
    """Get full candidate details for accordion"""
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            return {"error": "Candidate not found"}
        
        # Get batch name
        batch_name = f"Batch ID: {candidate.batchid}"
        try:
            batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
            if batch:
                batch_name = batch.batchname
        except:
            pass
        
        # Get preparation records
        preparation_records = []
        try:
            prep_data = db.query(CandidatePreparation).filter(CandidatePreparation.candidate_id == candidate.id).all()
            for prep in prep_data:
                preparation_records.append({
                    "start_date": prep.start_date.isoformat() if prep.start_date else None,
                    "status": prep.status or "Unknown",
                    "rating": prep.rating,
                    "tech_rating": prep.tech_rating,
                    "communication": prep.communication,
                    "notes": prep.notes
                })
        except:
            pass
        
        # Get marketing records
        marketing_records = []
        try:
            marketing_data = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == candidate.id).all()
            for marketing in marketing_data:
                marketing_records.append({
                    "start_date": marketing.start_date.isoformat() if marketing.start_date else None,
                    "status": marketing.status or "Unknown",
                    "notes": marketing.notes
                })
        except:
            pass
        
        # Get interview records
        interview_records = []
        try:
            interview_data = db.query(CandidateInterview).filter(CandidateInterview.candidate_id == candidate.id).all()
            for interview in interview_data:
                interview_records.append({
                    "company": interview.company,
                    "interview_date": interview.interview_date.isoformat() if interview.interview_date else None,
                    "interview_type": interview.interview_type,
                    "status": interview.status,
                    "feedback": interview.feedback,
                    "notes": interview.notes
                })
        except:
            pass
        
        # Get placement records
        placement_records = []
        try:
            placement_data = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.candidate_id == candidate.id).all()
            for placement in placement_data:
                placement_records.append({
                    "position": placement.position,
                    "company": placement.company,
                    "placement_date": placement.placement_date.isoformat() if placement.placement_date else None,
                    "status": placement.status,
                    "base_salary_offered": float(placement.base_salary_offered) if placement.base_salary_offered else None,
                    "notes": placement.notes
                })
        except:
            pass
        
        return {
            "candidate_id": candidate.id,
            "basic_info": {
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "status": candidate.status,
                "workstatus": candidate.workstatus,
                "education": candidate.education,
                "workexperience": candidate.workexperience,
                "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                "batch_name": batch_name,
                "agreement": candidate.agreement
            },
            "emergency_contact": {
                "emergcontactname": candidate.emergcontactname,
                "emergcontactphone": candidate.emergcontactphone,
                "emergcontactemail": candidate.emergcontactemail
            },
            "fee_financials": {
                "fee_paid": candidate.fee_paid,
                "payment_status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending"
            },
            "preparation_records": preparation_records,
            "marketing_records": marketing_records,
            "interview_records": interview_records,
            "placement_records": placement_records,
            "login_access": {
                "status": "No login data available"
            },
            "miscellaneous": {
                "notes": candidate.notes
            }
        }
        
    except Exception as e:
        return {"error": str(e)}
    
