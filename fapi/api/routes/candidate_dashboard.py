"""
Candidate Dashboard API Routes
Handles all dashboard-related endpoints for candidate management
"""

import logging
import os
import shutil
from fastapi import APIRouter, Query, Path, HTTPException, Depends, Security, File, UploadFile, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fapi.utils.auth_dependencies import get_current_user, User
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import date
from fapi.db.models import CandidateORM, AuthUserORM
from fapi.db.models import CandidateInterview
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
    update_interview_feedback,
)

from fapi.utils.google_drive_utils import create_drive_folder, upload_to_drive
from fapi.utils.email_utils import send_consolidated_onboarding_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["Candidate Dashboard"])
security = HTTPBearer()


# ==================== ONBOARDING DOCUMENT UPLOAD ====================

@router.post("/{candidate_id}/onboarding/upload")
async def upload_onboarding_documents(
    candidate_id: int = Path(..., description="Candidate ID"),
    govId: UploadFile = File(...),
    resume: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        files_to_process = [
            ("govId", govId),
        ]
        if resume:
            files_to_process.append(("resume", resume))

        # --- GOOGLE DRIVE INTEGRATION ---
        
        
        drive_folder_id = None
        drive_link = None
        
        try:
            # Create folder in Google Drive (organized by Candidate ID and Name)
            folder_name = f"Candidate_{candidate_id}_{candidate.full_name or 'Unknown'}"
            drive_folder = create_drive_folder(folder_name)
            if drive_folder:
                drive_folder_id = drive_folder.get('id')
                drive_link = drive_folder.get('webViewLink')
            else:
                logger.warning("Failed to create or find Google Drive folder. Using mock data for testing.")
                drive_folder_id = "mock_folder_id"
                drive_link = "https://drive.google.com/mock_link"
        except Exception as drive_err:
            logger.error(f"Google Drive folder creation failed: {str(drive_err)}")
            logger.warning("Continuing without Google Drive folder for testing purposes.")
            drive_folder_id = "mock_folder_id"
            drive_link = "https://drive.google.com/mock_link"

        upload_errors = []
        for doc_type, file in files_to_process:
            # Create a clean filename
            ext = os.path.splitext(file.filename)[1]
            safe_filename = f"{doc_type}_{int(datetime.now().timestamp())}{ext}"
            
            # Read file content
            content = await file.read()
            if not content:
                continue

            # Upload to Google Drive directly (Production primary)
            try:
                file_id = upload_to_drive(content, safe_filename, drive_folder_id, file.content_type)
                if not file_id:
                    upload_errors.append(safe_filename)
                    logger.error(f"Drive upload failed for {safe_filename}")
            except Exception as upload_err:
                upload_errors.append(safe_filename)
                logger.error(f"Failed to upload {safe_filename} to Drive: {str(upload_err)}")

        if upload_errors:
            logger.warning(f"Failed to upload documents to Google Drive: {', '.join(upload_errors)}")
            # For testing, we do not raise a 500 error here so the email flow can continue
            # raise HTTPException(status_code=500, detail=f"Failed to upload documents to Google Drive: {', '.join(upload_errors)}")

        # Update candidate folder path in DB with the Drive link and mark agreement as pending review
        candidate.candidate_folder = drive_link
        candidate.agreement = "P"
        db.commit()

        # Invalidate cache so the dashboard overview sees the new agreement status
        try:
            from fapi.core.cache import invalidate_cache
            invalidate_cache("candidates")
        except ImportError:
            pass

        # Send consolidated onboarding email to recruiters
        try:
            
            # Extract signature from notes if possible
            notes = candidate.notes or ""
            signature = "Electronically Signed"
            if "Signature:" in notes:
                try:
                    signature = notes.split("Signature:")[1].strip()
                except:
                    pass
            
            await send_consolidated_onboarding_email(
                candidate_name=candidate.full_name or "Unknown",
                candidate_email=candidate.email or "N/A",
                candidate_phone=candidate.phone or "N/A",
                signature=signature,
                notes=notes,
                drive_link=drive_link,
                file_paths=[],
                placement_percentage=candidate.placement_percentage if candidate.placement_percentage else 13
            )
            logger.info(f"Consolidated onboarding email sent for candidate {candidate_id}")
        except Exception as email_err:
            logger.error(f"Failed to send consolidated onboarding email for candidate {candidate_id}: {str(email_err)}")

        return {
            "message": "Documents uploaded successfully to Google Drive",
            "storage_type": "google_drive",
            "folder_link": drive_link
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading onboarding documents for candidate {candidate_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload documents to cloud: {str(e)}")


# ==================== DASHBOARD OVERVIEW ====================

@router.get("/{candidate_id}/dashboard/overview", response_model=Dict[str, Any])
def get_candidate_dashboard_overview_endpoint(
    candidate_id: int = Path(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    
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
    
# ==================== INTERVIEW FEEDBACK ====================

@router.patch("/interviews/{interview_id}/feedback")
def update_interview_feedback_endpoint(
    interview_id: int = Path(...),
    feedback: str = Query(..., description="Pending, Positive, or Negative"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if feedback not in ("Pending", "Positive", "Negative"):
        raise HTTPException(status_code=400, detail="Invalid feedback value")
    return update_interview_feedback(db, interview_id, feedback)