import logging
import re
from typing import Dict, Any, List
from fastapi import APIRouter, Query, Path, HTTPException, Depends, Security, Response, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils import candidate_utils
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.schemas import (
    CandidateUpdate, PaginatedCandidateResponse, CandidatePlacement,
    CandidateMarketing, CandidatePlacementCreate, CandidateMarketingCreate,
    CandidateInterviewOut, CandidateCreate, CandidateInterviewCreate,
    CandidateInterviewUpdate, CandidatePreparationCreate, CandidatePreparationUpdate,
    CandidatePreparationOut, PlacementMetrics, InterviewMetrics, CandidateMarketingUpdate,
    CandidateInterviewUpdate, CandidatePreparationCreate, CandidatePreparationUpdate,
    CandidatePreparationOut, PlacementMetrics, InterviewMetrics,
    CandidateInterviewPerformanceResponse, CandidatePreparationMetrics
)
from fapi.db.models import CandidateORM, AuthUserORM, CandidateInterview, JobLinkClicksORM, JobListingORM
from sqlalchemy import func, or_
from fapi.utils.avatar_dashboard_utils import (
    get_placement_metrics,
    get_interview_metrics,
    candidate_interview_performance,
    get_candidate_preparation_metrics
)
from fapi.utils import google_calendar_utils

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()


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
    return candidate_utils.get_all_candidates_paginated(db, page, limit, search, search_by, sort)

@router.head("/candidates")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_candidates_version(db)

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

            # Extract job link clicks tracking for the candidate
            authuser = db.query(AuthUserORM).filter(func.lower(AuthUserORM.uname) == func.lower(r.email)).first() if r.email else None
            job_listings_tracking = []
            if authuser:
                clicks = (
                    db.query(
                        JobListingORM.title.label("job_title"),
                        JobListingORM.company_name,
                        JobLinkClicksORM.click_count,
                        JobLinkClicksORM.last_clicked_at
                    )
                    .join(JobListingORM, JobLinkClicksORM.job_listing_id == JobListingORM.id)
                    .filter(JobLinkClicksORM.authuser_id == authuser.id)
                    .all()
                )
                for click in clicks:
                    job_listings_tracking.append({
                        "job_title": click.job_title,
                        "company_name": click.company_name,
                        "activity": f"{click.click_count} clicks",
                        "last_clicked_at": click.last_clicked_at.isoformat() if click.last_clicked_at else None
                    })
            item['job_listings_tracking'] = job_listings_tracking

            data.append(item)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/credentials")
def list_candidate_credentials(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_candidate_credentials_paginated(db, page, limit, search)


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
async def update_candidate_endpoint(candidate_id: int, candidate: CandidateUpdate, db: Session = Depends(get_db)):
    # Retrieve the candidate from the database to check the old agreement status
    db_candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    old_agreement = db_candidate.agreement
    candidate_email = db_candidate.email
    candidate_name = db_candidate.full_name

    # 1. Perform the update
    candidate_dict = candidate.dict(exclude_unset=True)
    candidate_utils.update_candidate(candidate_id, candidate_dict)
    
    # Check if agreement has transitioned to "Y"
    new_agreement = candidate_dict.get("agreement")
    if new_agreement == "Y" and old_agreement != "Y":
        if candidate_email:
            try:
                from fapi.utils.email_utils import send_document_approval_email
                await send_document_approval_email(candidate_email, candidate_name or "Candidate")
                logger.info(f"Sent document approval email to candidate {candidate_id} at {candidate_email}")
            except Exception as e:
                logger.error(f"Failed to send document approval email to candidate {candidate_id}: {str(e)}")
        else:
            logger.warning(f"Candidate {candidate_id} has no email address configured, skipping approval email")

    # 2. Invalidate dashboard cache
    try:
        from fapi.core.cache import invalidate_cache
        invalidate_cache("candidates")
    except Exception as e:
        logger.error(f"Cache invalidation failed for update: {e}")

    return {"message": "Candidate updated successfully"}

@router.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: int):
    candidate_utils.delete_candidate(candidate_id)
    return {"message": "Candidate deleted successfully"}



@router.get("/candidate/marketing", summary="Get all candidate marketing records")
def read_all_marketing(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_all_marketing_records( page, limit)

@router.head("/candidate/marketing")
def check_version_marketing(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_marketing_version(db)


@router.get("/candidate/marketing/{record_id}", summary="Get marketing record by ID")
def read_marketing_record(record_id: int = Path(...)):
    return candidate_utils.get_marketing_by_id(record_id)

@router.post("/candidate/marketing", response_model=CandidateMarketing)
def create_marketing_record(record: CandidateMarketingCreate):
    return candidate_utils.create_marketing(record)

@router.put("/candidate/marketing/{record_id}", response_model=CandidateMarketing)
def update_marketing_record(record_id: int, record: CandidateMarketingUpdate):
    return candidate_utils.update_marketing(record_id, record)

@router.delete("/candidate/marketing/{record_id}")
def delete_marketing_record(record_id: int):
    return candidate_utils.delete_marketing(record_id)



@router.get("/candidate/placements")
def read_all_placements(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_all_placements(page, limit)

@router.head("/candidate/placements")
def check_version_placements(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_placements_version(db)


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

@router.get("/candidate/active-dropdown", summary="Get unique candidates from marketing and placements for dropdown")
def get_active_dropdown_candidates(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_active_dropdown_candidates(db)
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

@router.head("/interviews")
def check_interviews_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return candidate_utils.get_interviews_version(db)

@router.post("/interviews", response_model=CandidateInterviewOut)
def create_interview(
    interview: CandidateInterviewCreate,
    db: Session = Depends(get_db),
):
    db_obj = candidate_utils.create_candidate_interview(db, interview)

    # Fetch with relationships for proper serialization
    full_obj = candidate_utils.get_candidate_interview_with_instructors(db, db_obj.id)
    return candidate_utils.serialize_interview(full_obj or db_obj)



@router.get("/interviews/{interview_id}", response_model=CandidateInterviewOut)
def read_candidate_interview(interview_id: int, db: Session = Depends(get_db)):
    db_obj = candidate_utils.get_candidate_interview_with_instructors(db, interview_id)

    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")
    return candidate_utils.serialize_interview(db_obj)

@router.post("/interviews/{interview_id}/generate-meet")
def generate_meet_for_interview(
    interview_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user)
):
    try:
        result = candidate_utils.generate_interview_meet(db, interview_id, background_tasks)
        return result
    except Exception as e:
        logger.error(f"Failed to generate meet link for interview {interview_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interviews", response_model=List[CandidateInterviewOut])
def list_interviews(db: Session = Depends(get_db)):
    interviews = candidate_utils.list_interviews_with_instructors(db)
    return [candidate_utils.serialize_interview(i) for i in interviews]


@router.put("/interviews/{interview_id}", response_model=CandidateInterviewOut)
def update_interview(
    interview_id: int,
    updates: CandidateInterviewUpdate,
    db: Session = Depends(get_db),
):
    db_obj = candidate_utils.update_candidate_interview(db, interview_id, updates)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Fetch with relationships for proper serialization
    full_obj = candidate_utils.get_candidate_interview_with_instructors(db, db_obj.id)
    return candidate_utils.serialize_interview(full_obj or db_obj)


@router.delete("/interviews/{interview_id}")
def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    # Fetch before deleting so we have the gcal_event_id
    db_obj = db.query(CandidateInterview).filter(CandidateInterview.id == interview_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Interview not found")

    # --- Google Calendar Sync: delete event first ---
    try:
        if db_obj.gcal_event_id:
            google_calendar_utils.delete_calendar_event(db_obj.gcal_event_id)
    except Exception as e:
        logger.error(f"[Google Calendar] Sync failed on delete for interview {interview_id}: {e}")
    # --- End Google Calendar Sync ---

    deleted = candidate_utils.delete_candidate_interview(db, interview_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Interview not found")
    return {"detail": "Interview deleted successfully"}


# -------------------Candidate_Preparation -------------------

@router.post("/candidate_preparation", response_model=CandidatePreparationOut)
def create_prep(prep: CandidatePreparationCreate, db: Session = Depends(get_db)):
    return candidate_utils.create_candidate_preparation(db, prep)

@router.get("/candidate_preparation/{prep_id}", response_model=CandidatePreparationOut)
def get_prep(prep_id: int, db: Session = Depends(get_db)):
    prep = candidate_utils.get_preparation_by_id(db, prep_id)
    if not prep:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return prep


@router.head("/candidate_preparations")
def check_prep_version(db: Session = Depends(get_db)):
    return candidate_utils.get_preparations_version(db)

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




@router.delete("/candidate_preparation/{prep_id}")
def delete_prep(
    prep_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    deleted = candidate_utils.delete_candidate_preparation(db, prep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidate preparation not found")
    return deleted


@router.get("/candidate/preparation/metrics", response_model=CandidatePreparationMetrics)
def read_candidate_preparation_metrics(db: Session = Depends(get_db)):
    return get_candidate_preparation_metrics(db)

##--------------------------------search----------------------------------


@router.get("/candidates/search-names/{search_term}")
def get_candidate_suggestions(
    search_term: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    token = credentials.credentials

    try:
        results = candidate_utils.get_candidate_suggestions(search_term, db)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/details/{candidate_id}")
def get_candidate_details(candidate_id: int, db: Session = Depends(get_db)):
    return candidate_utils.get_candidate_details(candidate_id, db)


@router.get("/candidates/sessions/{candidate_id}")
def get_candidate_sessions_route(candidate_id: int, db: Session = Depends(get_db)):
    return candidate_utils.get_candidate_sessions(candidate_id, db)


@router.get("/candidates-with-interviews")
def get_candidates_with_interviews(db: Session = Depends(get_db)):
    """Get all candidates who have at least one interview record"""
    try:
        candidates = (
            db.query(CandidateORM)
            .join(CandidateInterview)
            .distinct()
            .all()
        )
        return [{"id": c.id, "full_name": c.full_name} for c in candidates]
    except Exception as e:
        logger.error(f"Failed to fetch candidates with interviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
