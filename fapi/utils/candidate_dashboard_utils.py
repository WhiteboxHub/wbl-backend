"""
Candidate Dashboard Utility Functions
All business logic for dashboard operations using SQLAlchemy ORM
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, case, and_, or_, desc, distinct
from fastapi import HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

from fapi.db.models import (
    CandidateORM,
    CandidatePreparation,
    CandidateMarketingORM,
    CandidatePlacementORM,
    CandidateInterview,
    Batch,
    EmployeeORM,
    AuthUserORM,
)
from fapi.db.schemas import CandidateInterviewOut


# ==================== HELPER FUNCTIONS ====================

def _serialize_employee(employee: EmployeeORM) -> Dict[str, Any]:
    """Serialize employee object to dict"""
    if not employee:
        return None
    return {
        "id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "phone": getattr(employee, "phone", None),
    }


def _calculate_duration_days(start_date: date, end_date: Optional[date] = None) -> Optional[int]:
    """Calculate duration in days between two dates"""
    if not start_date:
        return None
    end = end_date or datetime.now().date()
    return (end - start_date).days


def _get_active_or_latest(records: List, status_field: str = "status", active_value: str = "active"):
    """Get active record or latest if no active exists"""
    if not records:
        return None
    active = next((r for r in records if getattr(r, status_field, None) == active_value), None)
    return active or records[0]


# ==================== DASHBOARD OVERVIEW ====================

def get_dashboard_overview(db: Session, candidate_id: int) -> Dict[str, Any]:
    """
    Get comprehensive dashboard overview for a candidate
    Single query with all necessary joins for efficiency
    """
    candidate = (
        db.query(CandidateORM)
        .options(
            joinedload(CandidateORM.batch),
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor1),
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor2),
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor3),
            selectinload(CandidateORM.marketing_records).joinedload(CandidateMarketingORM.marketing_manager_obj),
            selectinload(CandidateORM.placements),
            selectinload(CandidateORM.interviews).joinedload(CandidateInterview.position),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    basic_info = _get_basic_candidate_info(candidate)

    journey = _build_journey_timeline(candidate)

    #
    phase_metrics = _build_phase_metrics(candidate, db)

    team_info = _build_team_info(candidate)

    interview_stats = _calculate_interview_stats(candidate.interviews)

    all_interviews = sorted(
        candidate.interviews,
        key=lambda x: x.interview_date or date.min,
        reverse=True
    )

    alerts = _generate_candidate_alerts(candidate, db)

    return {
        "basic_info": basic_info,
        "journey": journey,
        "phase_metrics": phase_metrics,
        "team_info": team_info,
        "interview_stats": interview_stats,
        "interviews": [_serialize_interview_summary(i) for i in all_interviews],
        "alerts": alerts,
    }


def _get_basic_candidate_info(candidate: CandidateORM) -> Dict[str, Any]:
    """Extract basic candidate information"""
    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "secondary_email": candidate.secondaryemail,
        "secondary_phone": candidate.secondaryphone,
        "status": candidate.status,
        "work_status": candidate.workstatus,
        "education": candidate.education,
        "work_experience": candidate.workexperience,
        "linkedin_id": candidate.linkedin_id,
        "github_link": candidate.github_link,
        "candidate_folder": candidate.candidate_folder,
        "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
        "batch_id": candidate.batchid,
        "batch_name": candidate.batch.batchname if candidate.batch else None,
        "address": candidate.address,
        "fee_paid": float(candidate.fee_paid) if candidate.fee_paid else 0.0,
        "agreement": candidate.agreement,
        "notes": candidate.notes,
    }

def _build_journey_timeline(candidate: CandidateORM) -> Dict[str, Any]:
    """Build journey timeline showing progression through phases"""
    journey = {
        "enrolled": {
            "completed": True,
            "date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
            "status": candidate.status,
            "days_since": _calculate_duration_days(candidate.enrolled_date) if candidate.enrolled_date else None,
        },
        "preparation": {"completed": False, "active": False, "start_date": None, "end_date": None},
        "marketing": {"completed": False, "active": False, "start_date": None, "end_date": None},
        "placement": {"completed": False, "active": False, "date": None},
    }

    active_prep = _get_active_or_latest(candidate.preparations, "status", "active")
    if active_prep:
        is_active = active_prep.status == "active"
        journey["preparation"] = {
            "completed": not is_active,
            "active": is_active,
            "start_date": active_prep.start_date.isoformat() if active_prep.start_date else None,
            "end_date": active_prep.target_date.isoformat() if active_prep.target_date else None,  # ✅ Correct
            "duration_days": _calculate_duration_days(active_prep.start_date),
        }

    active_marketing = _get_active_or_latest(candidate.marketing_records, "status", "active")
    if active_marketing:
        is_active = active_marketing.status == "active"
        journey["marketing"] = {
            "completed": not is_active,
            "active": is_active,
            "start_date": active_marketing.start_date.isoformat() if active_marketing.start_date else None,
            "duration_days": _calculate_duration_days(active_marketing.start_date),
        }

    active_placement = _get_active_or_latest(candidate.placements, "status", "Active")
    if active_placement:
        journey["placement"] = {
            "completed": True,
            "active": active_placement.status == "Active",
            "date": active_placement.placement_date.isoformat() if active_placement.placement_date else None,
            "company": active_placement.company,
            "position": active_placement.position,
            "days_since": _calculate_duration_days(active_placement.placement_date),
        }

    return journey

def _build_phase_metrics(candidate: CandidateORM, db: Session) -> Dict[str, Any]:
    """Build metrics for each phase"""
    metrics = {
        "enrolled": {
            "date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
            "days_since": _calculate_duration_days(candidate.enrolled_date),
            "batch_name": candidate.batch.batchname if candidate.batch else None,
            "fee_paid": float(candidate.fee_paid) if candidate.fee_paid else 0.0,
            "status": candidate.status,
        },
        "preparation": None,
        "marketing": None,
        "placement": None,
    }

    prep = _get_active_or_latest(candidate.preparations, "status", "active")
    if prep:
        metrics["preparation"] = {
            "id": prep.id,
            "status": prep.status,
            "start_date": prep.start_date.isoformat() if prep.start_date else None,
            "target_marketing_date": prep.target_date.isoformat() if prep.target_date else None,  # ✅ This is correct
            "duration_days": _calculate_duration_days(prep.start_date),
            "rating": prep.rating,
            "communication": prep.communication,
            "years_of_experience": prep.years_of_experience,
        }

    marketing = _get_active_or_latest(candidate.marketing_records, "status", "active")
    if marketing:
        interview_counts = _calculate_interview_stats(candidate.interviews)
        metrics["marketing"] = {
            "id": marketing.id,
            "status": marketing.status,
            "start_date": marketing.start_date.isoformat() if marketing.start_date else None,
            "duration_days": _calculate_duration_days(marketing.start_date),
            "priority": getattr(marketing, "priority", None),
            "total_interviews": interview_counts["total"],
            "positive_interviews": interview_counts["positive"],
            "pending_interviews": interview_counts["pending"],
            "negative_interviews": interview_counts["negative"],
            "success_rate": interview_counts["success_rate"],
        }

    placement = _get_active_or_latest(candidate.placements, "status", "Active")
    if placement:
        metrics["placement"] = {
            "id": placement.id,
            "status": placement.status,
            "company": placement.company,
            "position": placement.position,
            "placement_date": placement.placement_date.isoformat() if placement.placement_date else None,
            "days_since": _calculate_duration_days(placement.placement_date),
            "base_salary": float(placement.base_salary_offered) if placement.base_salary_offered else None,
            "type": placement.type,
            # "priority": placement.priority,
        }

    return metrics

def _build_team_info(candidate: CandidateORM) -> Dict[str, Any]:
    """Build team information from candidate relationships"""
    team = {
        "preparation": {"instructors": []},
        "marketing": {"manager": None, "support": []},
    }

    prep = _get_active_or_latest(candidate.preparations, "status", "active")
    if prep:
        if prep.instructor1:
            team["preparation"]["instructors"].append({
                **_serialize_employee(prep.instructor1),
                "role": "Primary Instructor"
            })
        if prep.instructor2:
            team["preparation"]["instructors"].append({
                **_serialize_employee(prep.instructor2),
                "role": "Co-Instructor"
            })
        if prep.instructor3:
            team["preparation"]["instructors"].append({
                **_serialize_employee(prep.instructor3),
                "role": "Assistant Instructor"
            })

    marketing = _get_active_or_latest(candidate.marketing_records, "status", "active")
    if marketing and marketing.marketing_manager_obj:
        team["marketing"]["manager"] = _serialize_employee(marketing.marketing_manager_obj)

    return team


def _calculate_interview_stats(interviews: List[CandidateInterview]) -> Dict[str, Any]:
    """Calculate interview statistics from list of interviews"""
    total = len(interviews)
    if total == 0:
        return {
            "total": 0,
            "positive": 0,
            "pending": 0,
            "negative": 0,
            "success_rate": 0.0,
        }

    positive = sum(1 for i in interviews if i.feedback == "Positive")
    pending = sum(1 for i in interviews if i.feedback == "Pending")
    negative = sum(1 for i in interviews if i.feedback == "Negative")

    success_rate = round((positive / total) * 100, 2) if total > 0 else 0.0

    return {
        "total": total,
        "positive": positive,
        "pending": pending,
        "negative": negative,
        "success_rate": success_rate,
    }


def _serialize_interview_summary(interview: CandidateInterview) -> Dict[str, Any]:
    """Serialize interview to summary format"""
    return {
        "id": interview.id,
        "company": interview.company,
        "company_type": interview.company_type,
        "interview_date": interview.interview_date.isoformat() if interview.interview_date else None,
        "type_of_interview": interview.type_of_interview,
        "mode_of_interview": interview.mode_of_interview,
        "feedback": interview.feedback,
        "has_recording": bool(interview.recording_link),
        "has_transcript": bool(interview.transcript),
        "source_job_id": interview.position.source_job_id if interview.position else None,
    }


def _generate_candidate_alerts(candidate: CandidateORM, db: Session) -> List[Dict[str, Any]]:
    """Generate alerts/notifications for candidate"""
    alerts = []

    prep = _get_active_or_latest(candidate.preparations, "status", "active")
    if prep and prep.status == "active" and prep.target_date:
        if prep.target_date < datetime.now().date():
            alerts.append({
                "type": "warning",
                "phase": "preparation",
                "message": f"Preparation target date ({prep.target_date}) has passed",
            })


    marketing = _get_active_or_latest(candidate.marketing_records, "status", "active")
    if marketing and marketing.status == "active":
        recent_interviews = [
            i for i in candidate.interviews
            if i.interview_date and i.interview_date >= datetime.now().date() - timedelta(days=14)
        ]
        if len(recent_interviews) == 0:
            alerts.append({
                "type": "warning",
                "phase": "marketing",
                "message": "No interviews in the last 14 days",
            })

    return alerts


# ==================== JOURNEY TIMELINE ====================

def get_candidate_journey_timeline(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get detailed journey timeline for candidate"""
    candidate = (
        db.query(CandidateORM)
        .options(
            selectinload(CandidateORM.preparations),
            selectinload(CandidateORM.marketing_records),
            selectinload(CandidateORM.placements),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return _build_journey_timeline(candidate)


# ==================== FULL PROFILE ====================

def get_candidate_full_profile(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get complete candidate profile with all details"""
    candidate = (
        db.query(CandidateORM)
        .options(
            joinedload(CandidateORM.batch),
            selectinload(CandidateORM.preparations),
            selectinload(CandidateORM.marketing_records),
            selectinload(CandidateORM.placements),
            selectinload(CandidateORM.interviews),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    authuser = None
    if candidate.email:
        authuser = db.query(AuthUserORM).filter(
            func.lower(AuthUserORM.uname) == candidate.email.lower()
        ).first()

    return {
        "candidate_id": candidate.id,
        "personal_info": {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "secondary_email": candidate.secondaryemail,
            "secondary_phone": candidate.secondaryphone,
            "linkedin_id": candidate.linkedin_id,
            "github_link": candidate.github_link,
            "dob": candidate.dob.isoformat() if candidate.dob else None,
            "address": candidate.address,
            "status": candidate.status,
            "work_status": candidate.workstatus,
            "education": candidate.education,
            "work_experience": candidate.workexperience,
        },
        "emergency_contact": {
            "name": candidate.emergcontactname,
            "email": candidate.emergcontactemail,
            "phone": candidate.emergcontactphone,
            "address": candidate.emergcontactaddrs,
        },
        "enrollment": {
            "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
            "batch_id": candidate.batchid,
            "batch_name": candidate.batch.batchname if candidate.batch else None,
            "candidate_folder": candidate.candidate_folder,
            "agreement": candidate.agreement,
        },
        "financial": {
            "fee_paid": float(candidate.fee_paid) if candidate.fee_paid else 0.0,
            "payment_status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
        },
        "login_access": {
            "has_account": authuser is not None,
            "login_count": authuser.logincount if authuser else 0,
            "last_login": authuser.lastlogin.isoformat() if authuser and authuser.lastlogin else None,
            "registered_date": authuser.registereddate.isoformat() if authuser and authuser.registereddate else None,
            "status": authuser.status if authuser else "No Account",
        },
        "notes": candidate.notes,
    }





# ==================== PREPARATION PHASE (FIXED) ====================


def get_preparation_phase_details(
    db: Session, 
    candidate_id: int, 
    include_inactive: bool = False
) -> Dict[str, Any]:
    """Get preparation phase details - returns empty structure if no records"""
    
    # First check if candidate exists
    candidate = (
        db.query(CandidateORM)
        .options(joinedload(CandidateORM.batch))
        .filter(CandidateORM.id == candidate_id)
        .first()
    )
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Build query for preparation records
    query = (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate).joinedload(CandidateORM.batch),
            joinedload(CandidatePreparation.instructor1),
            joinedload(CandidatePreparation.instructor2),
            joinedload(CandidatePreparation.instructor3),
        )
        .filter(CandidatePreparation.candidate_id == candidate_id)
    )

    if not include_inactive:
        query = query.filter(CandidatePreparation.status == "active")

    prep_records = query.order_by(desc(CandidatePreparation.start_date)).all()

    # Return default structure if no preparation records exist
    if not prep_records:
        return {
            "status": "Not Started",
            "start_date": None,
            "duration_days": 0,
            "rating": "N/A",
            "communication": "N/A",
            "batch_name": candidate.batch.batchname if candidate.batch else "N/A",
            "instructors": [],
            "notes": None,
            "github": None,
            "resume": None
        }

    current_prep = prep_records[0]

    # Build result with actual preparation data
    result = {
        "id": current_prep.id,
        "candidate_id": current_prep.candidate_id,
        "candidate_name": current_prep.candidate.full_name if current_prep.candidate else None,
        # REMOVED: "batch": current_prep.batch,  # ❌ This doesn't exist
        "batch_name": current_prep.candidate.batch.batchname if current_prep.candidate and current_prep.candidate.batch else "N/A",
        "start_date": current_prep.start_date.isoformat() if current_prep.start_date else None,
        "status": current_prep.status,
        "rating": current_prep.rating,
        "communication": current_prep.communication,
        "years_of_experience": current_prep.years_of_experience,
        "target_date": current_prep.target_date.isoformat() if current_prep.target_date else None,
        "notes": current_prep.notes,
        # FIX: Use correct field names from your model
        "github": current_prep.github_url,  # Changed from github to github_url
        "resume": current_prep.resume_url,  # Changed from resume to resume_url
        "move_to_mrkt": current_prep.move_to_mrkt,
        "duration_days": _calculate_duration_days(current_prep.start_date),
        "instructors": [],
        "last_modified": current_prep.last_mod_datetime.isoformat() if current_prep.last_mod_datetime else None,
    }

    # Add instructors
    if current_prep.instructor1:
        result["instructors"].append({
            **_serialize_employee(current_prep.instructor1),
            "role": "Primary Instructor",
            "position": 1,
        })
    if current_prep.instructor2:
        result["instructors"].append({
            **_serialize_employee(current_prep.instructor2),
            "role": "Co-Instructor",
            "position": 2,
        })
    if current_prep.instructor3:
        result["instructors"].append({
            **_serialize_employee(current_prep.instructor3),
            "role": "Assistant Instructor",
            "position": 3,
        })

    # Add historical records if requested
    if include_inactive and len(prep_records) > 1:
        result["historical_records"] = [
            {
                "id": p.id,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "status": p.status,
                "rating": p.rating,
            }
            for p in prep_records[1:]
        ]

    return result

# ==================== MARKETING PHASE (FIXED) ====================

def get_marketing_phase_details(
    db: Session, 
    candidate_id: int, 
    include_inactive: bool = False
) -> Dict[str, Any]:
    """Get marketing phase details - returns empty structure if no records"""
    
    # First check if candidate exists
    candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Build query for marketing records
    query = (
        db.query(CandidateMarketingORM)
        .options(
            joinedload(CandidateMarketingORM.candidate).joinedload(CandidateORM.batch),
            joinedload(CandidateMarketingORM.marketing_manager_obj),
        )
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
    )

    if not include_inactive:
        query = query.filter(CandidateMarketingORM.status == "active")

    marketing_records = query.order_by(desc(CandidateMarketingORM.start_date)).all()

    # Get interviews for stats (even if no marketing record)
    interviews = (
        db.query(CandidateInterview)
        .filter(CandidateInterview.candidate_id == candidate_id)
        .all()
    )

    interview_stats = _calculate_interview_stats(interviews)

    # Return default structure if no marketing records exist
    if not marketing_records:
        return {
            "status": "Not Started",
            "start_date": None,
            "duration_days": 0,
            "interview_stats": interview_stats,
            "interview_breakdown": _calculate_interview_breakdown(interviews) if interviews else {},
            "top_companies": _get_top_companies_for_candidate(db, candidate_id) if interviews else [],
        }

    current_marketing = marketing_records[0]

    # Calculate detailed stats
    interview_breakdown = _calculate_interview_breakdown(interviews)
    top_companies = _get_top_companies_for_candidate(db, candidate_id)

    # Build result with actual marketing data
    result = {
        "id": current_marketing.id,
        "candidate_id": current_marketing.candidate_id,
        "candidate_name": current_marketing.candidate.full_name if current_marketing.candidate else None,
        "start_date": current_marketing.start_date.isoformat() if current_marketing.start_date else None,
        "status": current_marketing.status,
        "email": current_marketing.email,
        "password": "***********" if current_marketing.password else None,  # Masked
        "google_voice_number": current_marketing.google_voice_number,
        "priority": getattr(current_marketing, "priority", None),
        "notes": current_marketing.notes,
        "move_to_placement": current_marketing.move_to_placement,
        "candidate_resume": current_marketing.candidate_resume,
        "duration_days": _calculate_duration_days(current_marketing.start_date),
        "marketing_manager": _serialize_employee(current_marketing.marketing_manager_obj),
        "interview_stats": interview_stats,
        "interview_breakdown": interview_breakdown,
        "top_companies": top_companies,
        "last_modified": current_marketing.last_mod_datetime.isoformat() if current_marketing.last_mod_datetime else None,
    }

    # Add historical records if requested
    if include_inactive and len(marketing_records) > 1:
        result["historical_records"] = [
            {
                "id": m.id,
                "start_date": m.start_date.isoformat() if m.start_date else None,
                "status": m.status,
                "rating": m.rating,
            }
            for m in marketing_records[1:]
        ]

    return result


def _calculate_interview_breakdown(interviews: List[CandidateInterview]) -> Dict[str, Any]:
    """Calculate detailed interview breakdown"""
    breakdown = {
        "by_company_type": {},
        "by_interview_type": {},
        "by_mode": {},
        "by_feedback": {},
    }

    for interview in interviews:
        ct = interview.company_type or "Unknown"
        breakdown["by_company_type"][ct] = breakdown["by_company_type"].get(ct, 0) + 1

        it = interview.type_of_interview or "Unknown"
        breakdown["by_interview_type"][it] = breakdown["by_interview_type"].get(it, 0) + 1

        
        mode = interview.mode_of_interview or "Unknown"
        breakdown["by_mode"][mode] = breakdown["by_mode"].get(mode, 0) + 1

        feedback = interview.feedback or "Unknown"
        breakdown["by_feedback"][feedback] = breakdown["by_feedback"].get(feedback, 0) + 1

    return breakdown


def _get_top_companies_for_candidate(db: Session, candidate_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get top companies by interview count for candidate"""
    results = (
        db.query(
            CandidateInterview.company,
            func.count(CandidateInterview.id).label("interview_count"),
            func.sum(
                case((CandidateInterview.feedback == "Positive", 1), else_=0)
            ).label("positive_count"),
            func.max(CandidateInterview.interview_date).label("last_interview_date"),
        )
        .filter(CandidateInterview.candidate_id == candidate_id)
        .group_by(CandidateInterview.company)
        .order_by(desc("interview_count"))
        .limit(limit)
        .all()
    )

    return [
        {
            "company": r.company,
            "total_interviews": r.interview_count,
            "positive_interviews": r.positive_count or 0,
            "last_interview_date": r.last_interview_date.isoformat() if r.last_interview_date else None,
        }
        for r in results
    ]


# ==================== PLACEMENT PHASE ====================

def get_placement_phase_details(
    db: Session, 
    candidate_id: int, 
    include_inactive: bool = False
) -> Dict[str, Any]:
    """Get placement phase details"""
    query = (
        db.query(CandidatePlacementORM)
        .filter(CandidatePlacementORM.candidate_id == candidate_id)
    )

    if not include_inactive:
        query = query.filter(CandidatePlacementORM.status == "Active")

    placements = query.order_by(desc(CandidatePlacementORM.placement_date)).all()

    if not placements:
        return {
            "candidate_id": candidate_id,
            "has_placements": False,
            "active_placement": None,
            "other_placements": [],
        }

    active_placement = placements[0]
    other_placements = placements[1:] if len(placements) > 1 else []

    result = {
        "candidate_id": candidate_id,
        "has_placements": True,
        "active_placement": {
            "id": active_placement.id,
            "position": active_placement.position,
            "company": active_placement.company,
            "placement_date": active_placement.placement_date.isoformat() if active_placement.placement_date else None,
            "type": active_placement.type,
            "status": active_placement.status,
            "base_salary_offered": float(active_placement.base_salary_offered) if active_placement.base_salary_offered else None,
            "benefits": active_placement.benefits,
            "fee_paid": float(active_placement.fee_paid) if active_placement.fee_paid else None,
            "notes": active_placement.notes,
            "days_since_placement": _calculate_duration_days(active_placement.placement_date),
            "last_modified": active_placement.last_mod_datetime.isoformat() if active_placement.last_mod_datetime else None,
        },
        "other_placements": [
            {
                "id": p.id,
                "company": p.company,
                "position": p.position,
                "placement_date": p.placement_date.isoformat() if p.placement_date else None,
                "status": p.status,
                "base_salary_offered": float(p.base_salary_offered) if p.base_salary_offered else None,
            }
            for p in other_placements
        ],
    }

    return result


# ==================== INTERVIEW ANALYTICS ====================

def get_candidate_interview_analytics(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get comprehensive interview analytics"""
    interviews = (
        db.query(CandidateInterview)
        .filter(CandidateInterview.candidate_id == candidate_id)
        .order_by(CandidateInterview.interview_date)
        .all()
    )

    if not interviews:
        return {
            "candidate_id": candidate_id,
            "has_interviews": False,
            "summary": {"total": 0, "positive": 0, "pending": 0, "negative": 0, "success_rate": 0.0},
        }

    # Basic stats
    summary = _calculate_interview_stats(interviews)

    breakdown = _calculate_interview_breakdown(interviews)

    success_by_company_type = _calculate_success_rates_by_dimension(
        interviews, "company_type"
    )

    success_by_interview_type = _calculate_success_rates_by_dimension(
        interviews, "type_of_interview"
    )

    success_by_mode = _calculate_success_rates_by_dimension(
        interviews, "mode_of_interview"
    )

    weekly_activity = _calculate_weekly_activity(interviews, weeks=12)

    top_companies = _get_top_companies_for_candidate(db, candidate_id, limit=10)

    funnel = _calculate_conversion_funnel(interviews)

    return {
        "candidate_id": candidate_id,
        "has_interviews": True,
        "summary": summary,
        "breakdown": breakdown,
        "success_by_company_type": success_by_company_type,
        "success_by_interview_type": success_by_interview_type,
        "success_by_mode": success_by_mode,
        "weekly_activity": weekly_activity,
        "top_companies": top_companies,
        "conversion_funnel": funnel,
    }


def _calculate_success_rates_by_dimension(
    interviews: List[CandidateInterview], 
    dimension: str
) -> Dict[str, Any]:
    """Calculate success rates grouped by a specific dimension"""
    grouped = {}

    for interview in interviews:
        key = getattr(interview, dimension, None) or "Unknown"

        if key not in grouped:
            grouped[key] = {"total": 0, "positive": 0}

        grouped[key]["total"] += 1
        if interview.feedback == "Positive":
            grouped[key]["positive"] += 1

    result = {}
    for key, counts in grouped.items():
        total = counts["total"]
        positive = counts["positive"]
        success_rate = round((positive / total) * 100, 2) if total > 0 else 0.0

        result[key] = {
            "total": total,
            "positive": positive,
            "success_rate": success_rate,
        }

    return result


def _calculate_weekly_activity(interviews: List[CandidateInterview], weeks: int = 12) -> List[Dict[str, Any]]:
    """Calculate weekly interview activity"""
    cutoff_date = datetime.now().date() - timedelta(weeks=weeks)
    recent_interviews = [
        i for i in interviews
        if i.interview_date and i.interview_date >= cutoff_date
    ]


    weekly_counts = {}
    for interview in recent_interviews:
        if not interview.interview_date:
            continue

        week_start = interview.interview_date - timedelta(days=interview.interview_date.weekday())
        week_key = week_start.isoformat()

        if week_key not in weekly_counts:
            weekly_counts[week_key] = 0

        weekly_counts[week_key] += 1

    activity = [
        {"week_start": week, "count": count}
        for week, count in sorted(weekly_counts.items())
    ]

    return activity


def _calculate_conversion_funnel(interviews: List[CandidateInterview]) -> Dict[str, Any]:
    """Calculate interview conversion funnel"""
    funnel = {
        "recruiter_call": 0,
        "technical": 0,
        "hr_round": 0,
        "final_round": 0,
    }

    type_mapping = {
        "Recruiter Call": "recruiter_call",
        "Technical": "technical",
        "HR Round": "hr_round",
        "Final Round": "final_round",
    }

    for interview in interviews:
        interview_type = interview.type_of_interview
        if interview_type in type_mapping:
            funnel[type_mapping[interview_type]] += 1

    return funnel


# ==================== FILTERED INTERVIEWS ====================

def get_candidate_interviews_with_filters(
    db: Session,
    candidate_id: int,
    company_type: Optional[str] = None,
    feedback: Optional[str] = None,
    interview_type: Optional[str] = None,
    mode: Optional[str] = None,
    company: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get interviews with filters"""
    query = (
        db.query(CandidateInterview)
        .filter(CandidateInterview.candidate_id == candidate_id)
    )

    if company_type:
        query = query.filter(CandidateInterview.company_type == company_type)

    if feedback:
        query = query.filter(CandidateInterview.feedback == feedback)

    if interview_type:
        query = query.filter(CandidateInterview.type_of_interview == interview_type)

    if mode:
        query = query.filter(CandidateInterview.mode_of_interview == mode)

    if company:
        query = query.filter(CandidateInterview.company.ilike(f"%{company}%"))

    if start_date:
        query = query.filter(CandidateInterview.interview_date >= start_date)

    if end_date:
        query = query.filter(CandidateInterview.interview_date <= end_date)

    interviews = (
        query.order_by(desc(CandidateInterview.interview_date))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [_serialize_interview_detail(i) for i in interviews]


def _serialize_interview_detail(interview: CandidateInterview) -> Dict[str, Any]:
    """Serialize interview to detailed format"""
    return {
        "id": interview.id,
        "candidate_id": interview.candidate_id,
        "company": interview.company,
        "company_type": interview.company_type,
        "interviewer_emails": interview.interviewer_emails,
        "interviewer_contact": interview.interviewer_contact,
        "interviewer_linkedin": interview.interviewer_linkedin,
        "interview_date": interview.interview_date.isoformat() if interview.interview_date else None,
        "mode_of_interview": interview.mode_of_interview,
        "type_of_interview": interview.type_of_interview,
        "recording_link": interview.recording_link,
        "transcript": interview.transcript,
        "url": interview.url,
        "backup_url": interview.backup_url,
        "feedback": interview.feedback,
        "notes": interview.notes,
        "last_mod_datetime": interview.last_mod_datetime.isoformat() if interview.last_mod_datetime else None,
    }


# ==================== PHASE SUMMARY ====================

def get_candidate_phase_summary(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get condensed phase summary for metric cards"""
    candidate = (
        db.query(CandidateORM)
        .options(
            selectinload(CandidateORM.preparations),
            selectinload(CandidateORM.marketing_records),
            selectinload(CandidateORM.placements),
            selectinload(CandidateORM.interviews),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return _build_phase_metrics(candidate, db)


# ==================== TEAM MEMBERS ====================

def get_candidate_team_members(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get all team members assigned to candidate"""
    candidate = (
        db.query(CandidateORM)
        .options(
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor1),
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor2),
            selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor3),
            selectinload(CandidateORM.marketing_records).joinedload(CandidateMarketingORM.marketing_manager_obj),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return _build_team_info(candidate)


# ==================== PHASE TRANSITIONS ====================

def update_candidate_phase_status(
    db: Session,
    candidate_id: int,
    phase: str,
    action: str
) -> Dict[str, Any]:
    """Update candidate phase status (move between phases)"""
    candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if phase == "preparation" and action == "activate":
        existing = (
            db.query(CandidatePreparation)
            .filter(
                CandidatePreparation.candidate_id == candidate_id,
                CandidatePreparation.status == "active"
            )
            .first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Candidate already has an active preparation record")

        new_prep = CandidatePreparation(
            candidate_id=candidate_id,
            start_date=datetime.now().date(),
            status="active"
        )
        db.add(new_prep)
        db.commit()
        db.refresh(new_prep)

        return {"message": "Candidate moved to preparation phase", "preparation_id": new_prep.id}

    elif phase == "marketing" and action == "activate":
        active_prep = (
            db.query(CandidatePreparation)
            .filter(
                CandidatePreparation.candidate_id == candidate_id,
                CandidatePreparation.status == "active"
            )
            .first()
        )

        if active_prep:
            active_prep.status = "inactive"

        existing = (
            db.query(CandidateMarketingORM)
            .filter(
                CandidateMarketingORM.candidate_id == candidate_id,
                CandidateMarketingORM.status == "active"
            )
            .first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Candidate already has an active marketing record")

        new_marketing = CandidateMarketingORM(
            candidate_id=candidate_id,
            start_date=datetime.now().date(),
            status="active"
        )
        db.add(new_marketing)
        db.commit()
        db.refresh(new_marketing)

        return {"message": "Candidate moved to marketing phase", "marketing_id": new_marketing.id}

    elif phase == "placement" and action == "activate":
        active_marketing = (
            db.query(CandidateMarketingORM)
            .filter(
                CandidateMarketingORM.candidate_id == candidate_id,
                CandidateMarketingORM.status == "active"
            )
            .first()
        )

        if active_marketing:
            active_marketing.status = "inactive"

        existing = (
            db.query(CandidatePlacementORM)
            .filter(
                CandidatePlacementORM.candidate_id == candidate_id,
                CandidatePlacementORM.status == "Active"
            )
            .first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Candidate already has an active placement record")

        new_placement = CandidatePlacementORM(
            candidate_id=candidate_id,
            placement_date=datetime.now().date(),
            status="Active"
        )
        db.add(new_placement)
        db.commit()
        db.refresh(new_placement)

        return {"message": "Candidate moved to placement phase", "placement_id": new_placement.id}

    else:
        raise HTTPException(status_code=400, detail=f"Invalid phase ({phase}) or action ({action})")


# ==================== STATISTICS ====================

def get_candidate_statistics(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Get comprehensive statistics for candidate"""
    candidate = (
        db.query(CandidateORM)
        .options(
            selectinload(CandidateORM.preparations),
            selectinload(CandidateORM.marketing_records),
            selectinload(CandidateORM.placements),
            selectinload(CandidateORM.interviews),
        )
        .filter(CandidateORM.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    stats = {
        "total_days_in_system": _calculate_duration_days(candidate.enrolled_date),
        "days_in_preparation": 0,
        "days_in_marketing": 0,
        "days_since_placement": 0,
        "total_interviews": len(candidate.interviews),
        "interview_success_rate": 0.0,
    }

    for prep in candidate.preparations:
        if prep.start_date:
            end_date = prep.target_date or datetime.now().date()
            stats["days_in_preparation"] += _calculate_duration_days(prep.start_date, end_date) or 0

    for marketing in candidate.marketing_records:
        if marketing.start_date:
            stats["days_in_marketing"] += _calculate_duration_days(marketing.start_date) or 0

    active_placement = _get_active_or_latest(candidate.placements, "status", "Active")
    if active_placement and active_placement.placement_date:
        stats["days_since_placement"] = _calculate_duration_days(active_placement.placement_date)

    interview_stats = _calculate_interview_stats(candidate.interviews)
    stats["interview_success_rate"] = interview_stats["success_rate"]

    return stats




def _get_login_info(db: Session, email: str) -> Dict[str, Any]:
    """Get login information from authuser table"""
    if not email:
        return {
            "has_account": False,
            "login_count": 0,
            "last_login": None,
            "registered_date": None,
            "status": "No Account",
            "total_days_registered": 0
        }
    
    authuser = db.query(AuthUserORM).filter(
        func.lower(AuthUserORM.uname) == email.lower()
    ).first()
    
    if not authuser:
        return {
            "has_account": False,
            "login_count": 0,
            "last_login": None,
            "registered_date": None,
            "status": "No Account",
            "total_days_registered": 0
        }
    
    total_days = 0
    if authuser.registereddate:
        total_days = (datetime.now().date() - authuser.registereddate.date()).days
    
    return {
        "has_account": True,
        "login_count": authuser.logincount or 0,
        "last_login": authuser.lastlogin.isoformat() if authuser.lastlogin else None,
        "registered_date": authuser.registereddate.isoformat() if authuser.registereddate else None,
        "status": authuser.status or "active",
        "total_days_registered": total_days
    }
