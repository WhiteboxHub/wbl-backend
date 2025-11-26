"""
Candidate Dashboard API Routes
Handles all dashboard-related endpoints for candidate management
"""

import logging
from fastapi import APIRouter, Query, Path, HTTPException, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import date
from fapi.db.models import CandidateORM, AuthUserORM
from fapi.api.routes import login
from datetime import datetime
from sqlalchemy import func
from fapi.db.database import get_db
from fapi.db.schemas import (
    CandidateInterviewOut,
    CandidatePreparationOut,
    CandidateMarketing,
    CandidatePlacement,
)
from fapi.utils.candidate_dashboard_utils import (
    get_dashboard_overview,
    get_candidate_journey_timeline,
    get_preparation_phase_details,
    get_marketing_phase_details,
    get_placement_phase_details,
    get_candidate_interview_analytics,
    get_candidate_interviews_with_filters,
    get_candidate_full_profile,
    get_candidate_phase_summary,
    get_candidate_team_members,
    update_candidate_phase_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/candidates", tags=["Candidate Dashboard"])
security = HTTPBearer()


# ==================== DASHBOARD OVERVIEW ====================

@router.get("/{candidate_id}/dashboard/overview", response_model=Dict[str, Any])
def get_candidate_dashboard_overview_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get comprehensive dashboard overview for a candidate**
    
    Returns:
    - Basic candidate information
    - Journey timeline (enrolled → prep → marketing → placement)
    - Phase metrics (duration, ratings, counts)
    - Team information (instructors, managers)
    - Interview statistics
    - Recent interviews (last 5)
    - Quick notes and alerts
    """
    try:
        return get_dashboard_overview(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard overview for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard overview: {str(e)}")


@router.get("/{candidate_id}/journey", response_model=Dict[str, Any])
def get_candidate_journey_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get candidate journey/timeline across all phases**
    
    Returns progression status:
    - Enrolled (date, batch, status)
    - Preparation (status, dates, completion)
    - Marketing (status, dates, activity)
    - Placement (status, date, company)
    """
    try:
        return get_candidate_journey_timeline(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching journey for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch journey: {str(e)}")


@router.get("/{candidate_id}/profile", response_model=Dict[str, Any])
def get_candidate_full_profile_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get complete candidate profile with all details**
    
    Comprehensive profile including:
    - Personal information
    - Contact details
    - Emergency contacts
    - Education & experience
    - All phase records
    - Financial information
    """
    try:
        return get_candidate_full_profile(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


# ==================== PREPARATION PHASE ====================

@router.get("/{candidate_id}/preparation", response_model=Dict[str, Any])
def get_candidate_preparation_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    include_inactive: bool = Query(False, description="Include inactive preparation records"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get preparation phase details for candidate**
    
    Returns:
    - Current/latest preparation record
    - Assigned instructors (with contact info)
    - Ratings (technical, communication)
    - Topics completed and in-progress
    - Duration and target dates
    - Resources (LinkedIn, GitHub, Resume)
    - Move to marketing flag
    """
    try:
        return get_preparation_phase_details(db, candidate_id, include_inactive)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching preparation for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch preparation details: {str(e)}")


# ==================== MARKETING PHASE ====================

@router.get("/{candidate_id}/marketing", response_model=Dict[str, Any])
def get_candidate_marketing_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    include_inactive: bool = Query(False, description="Include inactive marketing records"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get marketing phase details for candidate**
    
    Returns:
    - Current/latest marketing record
    - Marketing manager and team
    - Marketing credentials (email, password, Google Voice)
    - Interview statistics and breakdown
    - Resume versions
    - Top companies interviewed
    - Move to placement flag
    """
    try:
        return get_marketing_phase_details(db, candidate_id, include_inactive)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching marketing for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch marketing details: {str(e)}")


# ==================== PLACEMENT PHASE ====================

@router.get("/{candidate_id}/placement", response_model=Dict[str, Any])
def get_candidate_placement_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    include_inactive: bool = Query(False, description="Include inactive placements"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get placement phase details for candidate**
    
    Returns:
    - Active/all placement records
    - Company and position details
    - Compensation package (salary, benefits, bonuses)
    - Placement fees
    - Placement type and status
    - Other offers (accepted/declined)
    - Follow-up schedule
    """
    try:
        return get_placement_phase_details(db, candidate_id, include_inactive)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching placement for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch placement details: {str(e)}")


# ==================== INTERVIEWS ====================

@router.get("/{candidate_id}/interviews", response_model=List[CandidateInterviewOut])
def get_candidate_interviews_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    company_type: Optional[str] = Query(None, description="Filter by company type"),
    feedback: Optional[str] = Query(None, description="Filter by feedback status"),
    interview_type: Optional[str] = Query(None, description="Filter by interview type"),
    mode: Optional[str] = Query(None, description="Filter by mode of interview"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    start_date: Optional[date] = Query(None, description="Filter from this date"),
    end_date: Optional[date] = Query(None, description="Filter until this date"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get all interviews for a candidate with optional filters**
    
    Supports filtering by:
    - Company type (client, vendor, etc.)
    - Feedback status (Positive, Negative, Pending)
    - Interview type (Technical, HR, etc.)
    - Mode (Virtual, In Person, Phone)
    - Company name (partial match)
    - Date range
    
    Returns paginated results with interviewer details and recordings
    """
    try:
        return get_candidate_interviews_with_filters(
            db=db,
            candidate_id=candidate_id,
            company_type=company_type,
            feedback=feedback,
            interview_type=interview_type,
            mode=mode,
            company=company,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interviews for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch interviews: {str(e)}")


@router.get("/{candidate_id}/interviews/analytics", response_model=Dict[str, Any])
def get_candidate_interview_analytics_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get comprehensive interview analytics for a candidate**
    
    Returns:
    - Total interview count
    - Feedback distribution (positive, negative, pending)
    - Success rates by company type
    - Success rates by interview type
    - Success rates by mode
    - Weekly/monthly activity trends
    - Top companies (by interview count)
    - Average time between interviews
    - Conversion funnel (recruiter → technical → HR → offer)
    """
    try:
        return get_candidate_interview_analytics(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interview analytics for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


# ==================== PHASE SUMMARY ====================

@router.get("/{candidate_id}/phase-summary", response_model=Dict[str, Any])
def get_candidate_phase_summary_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get summary of all phases for quick metrics cards**
    
    Returns condensed metrics for:
    - Enrolled phase (date, batch, fee)
    - Preparation phase (duration, ratings, status)
    - Marketing phase (duration, interview counts)
    - Placement phase (company, salary, date)
    """
    try:
        return get_candidate_phase_summary(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching phase summary for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch phase summary: {str(e)}")


# ==================== TEAM INFORMATION ====================

@router.get("/{candidate_id}/team", response_model=Dict[str, Any])
def get_candidate_team_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get all team members assigned to candidate**
    
    Returns:
    - Preparation instructors (1, 2, 3) with contact info
    - Marketing manager with contact info
    - Marketing support team
    - Batch coordinator (if applicable)
    """
    try:
        return get_candidate_team_members(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching team for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch team: {str(e)}")


# ==================== PHASE TRANSITIONS ====================

@router.post("/{candidate_id}/move-to-preparation", response_model=Dict[str, Any])
def move_candidate_to_preparation_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Move candidate from enrolled to preparation phase**
    
    Creates a new preparation record with status 'active'
    """
    try:
        return update_candidate_phase_status(
            db=db,
            candidate_id=candidate_id,
            phase="preparation",
            action="activate"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving candidate {candidate_id} to preparation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to move to preparation: {str(e)}")


@router.post("/{candidate_id}/move-to-marketing", response_model=Dict[str, Any])
def move_candidate_to_marketing_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Move candidate from preparation to marketing phase**
    
    - Marks preparation as inactive
    - Creates new marketing record with status 'active'
    """
    try:
        return update_candidate_phase_status(
            db=db,
            candidate_id=candidate_id,
            phase="marketing",
            action="activate"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving candidate {candidate_id} to marketing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to move to marketing: {str(e)}")


@router.post("/{candidate_id}/move-to-placement", response_model=Dict[str, Any])
def move_candidate_to_placement_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Move candidate from marketing to placement phase**
    
    - Marks marketing as inactive
    - Creates new placement record with status 'Active'
    """
    try:
        return update_candidate_phase_status(
            db=db,
            candidate_id=candidate_id,
            phase="placement",
            action="activate"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving candidate {candidate_id} to placement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to move to placement: {str(e)}")


# ==================== STATISTICS & METRICS ====================

@router.get("/{candidate_id}/statistics", response_model=Dict[str, Any])
def get_candidate_statistics_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    **Get comprehensive statistics for candidate**
    
    Returns:
    - Total days in system
    - Days in each phase
    - Interview conversion rates
    - Response time metrics
    - Progress indicators
    """
    try:
        from fapi.utils.candidate_dashboard_utils import get_candidate_statistics
        return get_candidate_statistics(db, candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching statistics for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")
    




@router.get("/{candidate_id}/test-basic")
def test_basic_candidate_data(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
):
    """
    Simple test endpoint to check basic candidate data without complex joins
    """
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        
        if not candidate:
            return {"error": "Candidate not found"}
            
        # Test basic data
        basic_data = {
            "success": True,
            "candidate_id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "status": candidate.status,
            "batch_id": candidate.batchid,
        }
        
        # Test relationships one by one
        try:
            preparations = candidate.preparations
            basic_data["preparations_count"] = len(preparations)
        except Exception as e:
            basic_data["preparations_error"] = str(e)
            
        try:
            marketing_records = candidate.marketing_records
            basic_data["marketing_count"] = len(marketing_records)
        except Exception as e:
            basic_data["marketing_error"] = str(e)
            
        try:
            placements = candidate.placements
            basic_data["placements_count"] = len(placements)
        except Exception as e:
            basic_data["placements_error"] = str(e)
            
        try:
            interviews = candidate.interviews
            basic_data["interviews_count"] = len(interviews)
        except Exception as e:
            basic_data["interviews_error"] = str(e)
            
        return basic_data
        
    except Exception as e:
        logger.error(f"Test endpoint error: {str(e)}", exc_info=True)
        return {"error": str(e)}
    
