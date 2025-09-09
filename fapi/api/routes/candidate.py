# fapi/api/routes/candidate.py
from sqlalchemy.orm import Session,selectinload
from sqlalchemy import or_
from fapi.utils.avatar_dashboard_utils import (
    get_placement_metrics,
    get_interview_metrics,
)
from fastapi import APIRouter, Query, Path, HTTPException,Depends
from fapi.utils import candidate_utils 
from fapi.db.schemas import CandidateBase, CandidateUpdate, PaginatedCandidateResponse, CandidatePlacement,  CandidateMarketing,CandidatePlacementCreate,CandidateMarketingCreate,CandidateInterviewOut, CandidateInterviewCreate, CandidateInterviewUpdate,CandidatePreparationCreate,CandidatePreparationUpdate,CandidatePreparationOut, PlacementMetrics, InterviewMetrics
from fapi.db.models import CandidateInterview,CandidateORM,CandidatePreparation, CandidateMarketingORM, CandidatePlacementORM, Batch,AuthUserORM

from sqlalchemy.orm import Session,joinedload
from fapi.db.database import get_db,SessionLocal


from typing import Dict



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
@router.get("/candidates/search", response_model=Dict)
def search_candidates(term: str):
    db: Session = SessionLocal()
    try:
        
        results = (
            db.query(CandidateORM)
            .filter(
                CandidateORM.full_name.ilike(f"%{term}%") |
                CandidateORM.email.ilike(f"%{term}%") |
                (CandidateORM.id == int(term)) if term.isdigit() else False
            )
            .all()
        )
        data = [r.__dict__ for r in results]
        for item in data:
            item.pop('_sa_instance_state', None)
        return {"data": data}
    finally:
        db.close()


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
        .options(joinedload(CandidateInterview.candidate)) 
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

##--------------------------------search----------------------------------

@router.get("/candidates/search-names/{search_term}")
def get_candidate_suggestions(search_term: str, db: Session = Depends(get_db)):
    """Optimized candidate name suggestions with caching"""
    if not search_term or len(search_term.strip()) < 2:
        return []
    
    try:
        # Add LIMIT for better performance
        candidates = (
            db.query(CandidateORM.id, CandidateORM.full_name, CandidateORM.email)
            .filter(
                or_(
                    CandidateORM.full_name.ilike(f"%{search_term}%"),
                    CandidateORM.email.ilike(f"%{search_term}%")
                )
            )
            .order_by(CandidateORM.full_name)
            .limit(10)  # ADD THIS LINE for performance
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
# REPLACE the existing details function in candidate_utils.py
@router.get("/candidates/details/{candidate_id}")
def get_candidate_details(candidate_id: int, db: Session = Depends(get_db)):
    """Optimized single query for candidate details"""
    try:
        # Use eager loading for better performance
        candidate = (
            db.query(CandidateORM)
            .options(
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor1_employee),
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor2_employee),
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor3_employee),
                selectinload(CandidateORM.marketing_records).joinedload(CandidateMarketingORM.marketing_manager_employee),
                selectinload(CandidateORM.interview_records),
                selectinload(CandidateORM.placement_records)
            )
            .filter(CandidateORM.id == candidate_id)
            .first()
        )
        
        if not candidate:
            return {"error": "Candidate not found"}
        
        # Get batch and authuser info
        batch_name = f"Batch ID: {candidate.batchid}"
        try:
            batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
            if batch:
                batch_name = batch.batchname
        except:
            pass
        
        authuser = None
        if candidate.email:
            try:
                authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(candidate.email)).first()
            except:
                pass
        
        # Build optimized response using relationships
        return {
            "candidate_id": candidate.id,
            "basic_info": {
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "secondaryemail": candidate.secondaryemail,
                "secondaryphone": candidate.secondaryphone,
                "linkedin_id": candidate.linkedin_id,
                "status": candidate.status,
                "workstatus": candidate.workstatus,
                "education": candidate.education,
                "workexperience": candidate.workexperience,
                "ssn": "***-**-" + str(candidate.ssn)[-4:] if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
                "dob": candidate.dob.isoformat() if candidate.dob else None,
                "address": candidate.address,
                "agreement": candidate.agreement,
                "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                "batch_name": batch_name,
                "candidate_folder": candidate.candidate_folder if hasattr(candidate, 'candidate_folder') else None
            },
            "emergency_contact": {
                "emergcontactname": candidate.emergcontactname,
                "emergcontactphone": candidate.emergcontactphone,
                "emergcontactemail": candidate.emergcontactemail,
                "emergcontactaddrs": candidate.emergcontactaddrs
            },
            "fee_financials": {
                "fee_paid": candidate.fee_paid,
                "payment_status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
                "notes": candidate.notes
            },
            "preparation_records": [
                {
                    "start_date": prep.start_date.isoformat() if prep.start_date else None,
                    "status": prep.status,
                    "instructor1_name": prep.instructor1_employee.name if prep.instructor1_employee else None,
                    "instructor2_name": prep.instructor2_employee.name if prep.instructor2_employee else None,
                    "instructor3_name": prep.instructor3_employee.name if prep.instructor3_employee else None,
                    "rating": prep.rating,
                    "tech_rating": prep.tech_rating,
                    "communication": prep.communication,
                    "years_of_experience": prep.years_of_experience,
                    "topics_finished": prep.topics_finished,
                    "current_topics": prep.current_topics,
                    "target_date_of_marketing": prep.target_date_of_marketing.isoformat() if prep.target_date_of_marketing else None,
                    "notes": prep.notes

                }
                for prep in candidate.preparation_records
            ],
            "marketing_records": [
                {
                    "start_date": marketing.start_date.isoformat() if marketing.start_date else None,
                    "status": marketing.status,
                    "marketing_manager_name": marketing.marketing_manager_employee.name if marketing.marketing_manager_employee else None,
                    "notes": marketing.notes
                }
                for marketing in candidate.marketing_records
            ],
            "interview_records": [
                {
                    "company": interview.company,
                    "interview_date": interview.interview_date.isoformat() if interview.interview_date else None,
                    "interview_type": interview.interview_type,
                    "status": interview.status,
                    "feedback": interview.feedback,
                    "recording_link": interview.recording_link,
                    "interviewer_emails": interview.interviewer_emails,
                    "notes": interview.notes
                }
                for interview in candidate.interview_records
            ],
            "placement_records": [
                {
                    "position": placement.position,
                    "company": placement.company,
                    "placement_date": placement.placement_date.isoformat() if placement.placement_date else None,
                    "status": placement.status,
                    "type": placement.type,
                    "base_salary_offered": float(placement.base_salary_offered) if placement.base_salary_offered else None,
                    "benefits": placement.benefits,
                    "fee_paid": float(placement.fee_paid) if placement.fee_paid else None,
                    "notes": placement.notes
                }
                for placement in candidate.placement_records
            ],
            "login_access": {
                "logincount": authuser.logincount if authuser else 0,
                "lastlogin": authuser.lastlogin.isoformat() if authuser and hasattr(authuser, 'lastlogin') and authuser.lastlogin else None,
                "registereddate": authuser.registereddate.isoformat() if authuser and authuser.registereddate else None,
                "status": authuser.status if authuser else "No Account",
                "reset_token": "Set" if authuser and hasattr(authuser, 'reset_token') and authuser.reset_token else "Not Set",
                "googleId": authuser.googleId if authuser else None
            },
            "miscellaneous": {
                "notes": candidate.notes,
                "preparation_active": len(candidate.preparation_records) > 0,
                "marketing_active": len(candidate.marketing_records) > 0,
                "placement_active": len(candidate.placement_records) > 0
            }
        }
        
    except Exception as e:
        return {"error": str(e)}
