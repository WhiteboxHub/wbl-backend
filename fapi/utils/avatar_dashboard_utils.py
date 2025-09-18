from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract, or_, and_, case
from datetime import datetime, date, timedelta
from typing import Dict, Any, List
from fapi.db.models import Batch, CandidateORM, CandidateMarketingORM, CandidatePlacementORM, CandidateInterview, EmployeeORM, LeadORM


def get_batch_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()
    current_active_batches = db.query(Batch).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).all()
    if current_active_batches:
        batch_names = [batch.batchname for batch in current_active_batches]
        current_active_batches_str = batch_names[0]  # First batch name
        if len(batch_names) > 1:
            current_active_batches_str += f" (+{len(batch_names) - 1} more)"
    else:
        current_active_batches_str = "No active batches"
    # If multiple batches, show count and first batch name
    current_active_batches_count = len(current_active_batches)

    # Enrolled candidates
    enrolled_candidates_current = db.query(CandidateORM).join(
        Batch,
        CandidateORM.batchid == Batch.batchid
    ).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).count()
    total_candidates = db.query(CandidateORM).count()
    # Candidates enrolled in Last Batch only for batches that have started
    last_batch = (
        db.query(Batch)
        .filter(Batch.startdate <= date.today()) 
        .order_by(desc(Batch.startdate))
        .first()
    )

    candidates_last_batch = 0
    if last_batch:
        candidates_last_batch = (
            db.query(CandidateORM)
            .filter(CandidateORM.batchid == last_batch.batchid)
            .count()
        )


    # New Enrollments in this Month
    first_day_month = today.replace(day=1)
    new_enrollments_month = db.query(CandidateORM).filter(
        CandidateORM.enrolled_date >= first_day_month
    ).count()
    # Candidate Status Breakdown
    status_breakdown = db.query(
        CandidateORM.status,
        func.count(CandidateORM.id)
    ).group_by(CandidateORM.status).all()
    status_dict = {status: count for status, count in status_breakdown}
    return {
        "current_active_batches": current_active_batches_str,
        "current_active_batches_count": current_active_batches_count,
        "enrolled_candidates_current": enrolled_candidates_current,
        "total_candidates": total_candidates,
        "candidates_last_batch": candidates_last_batch,
        "new_enrollments_month": new_enrollments_month,
        "candidate_status_breakdown": status_dict
    }


def get_financial_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()
    first_day_month = today.replace(day=1)
    # Total Fee Paid in Current Batch
    current_batch = db.query(Batch).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).first()
    total_fee_current_batch = 0
    if current_batch:
        total_fee_current_batch = db.query(func.sum(CandidateORM.fee_paid)).filter(
            CandidateORM.batchid == current_batch.batchid
        ).scalar() or 0
    # fee collected in last batch
    last_batch = (
        db.query(Batch)
        .filter(Batch.enddate < today)  # only past batches
        .order_by(Batch.enddate.desc())
        .first()
    )
    fee_collected_last_batch = 0
    if last_batch:
        fee_collected_last_batch = (
            db.query(func.sum(CandidateORM.fee_paid))
            .filter(CandidateORM.batchid == last_batch.batchid)
            .scalar()
            or 0
        )

    # Top 5 Batches by Fee Collection
    top_batches = db.query(
        Batch.batchname,
        func.sum(CandidateORM.fee_paid).label("total_fee")
    ).join(
        CandidateORM,
        CandidateORM.batchid == Batch.batchid
    ).group_by(Batch.batchid).order_by(
        desc("total_fee")
    ).limit(5).all()
    top_batches_list = [
        {"batch_name": name, "total_fee": float(total_fee)}
        for name, total_fee in top_batches
    ]
    return {
        "total_fee_current_batch": total_fee_current_batch,
        "fee_collected_last_batch": fee_collected_last_batch,
        "top_batches_fee": top_batches_list
    }


def get_placement_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()
    first_day_year = today.replace(month=1, day=1)
    if today.month == 1:
        prev_month = 12
        prev_year = today.year - 1
    else:
        prev_month = today.month - 1
        prev_year = today.year
    first_day_prev_month = date(prev_year, prev_month, 1)
    if prev_month == 12:
        last_day_prev_month = date(prev_year, 12, 31)
    else:
        last_day_prev_month = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
    # Total Placements (All Time)
    total_placements = db.query(CandidatePlacementORM).count()
    # Placements This Year
    placements_year = db.query(CandidatePlacementORM).filter(
        CandidatePlacementORM.placement_date >= first_day_year
    ).count()
    # Placements Last Month
    placements_last_month = db.query(CandidatePlacementORM).filter(
        CandidatePlacementORM.placement_date >= first_day_prev_month,
        CandidatePlacementORM.placement_date <= last_day_prev_month
    ).count()
    # Last Placement Done
    last_placement = db.query(CandidatePlacementORM).order_by(
        desc(CandidatePlacementORM.placement_date)
    ).first()

    last_placement_dict = None
    if last_placement:
        candidate_name = "Unknown"
        if last_placement.candidate_id:
            candidate = db.query(CandidateORM).filter(
                CandidateORM.id == last_placement.candidate_id
            ).first()
            if candidate:
                candidate_name = candidate.full_name or f"Candidate {last_placement.candidate_id}"

    last_placement_dict = {
            "candidate_name": candidate_name,
            "company": last_placement.company,
            "placement_date": last_placement.placement_date,
            "position":last_placement.position
        }
    # Currently Active Placements
    active_placements = db.query(CandidatePlacementORM).filter(
        CandidatePlacementORM.status == "scheduled"
    ).count()
    return {
        "total_placements": total_placements,
        "placements_year": placements_year,
        "placements_last_month": placements_last_month,
        "last_placement": last_placement_dict,
        "active_placements": active_placements
    }

# Interview metrics
def get_interview_metrics(db: Session) -> Dict[str, Any]:
    today = datetime.now().date()
    next_week = today + timedelta(days=7)
    # Upcoming Interviews
    upcoming_interviews = db.query(CandidateInterview).filter(
        CandidateInterview.interview_date >= datetime.now(),
        CandidateInterview.interview_date <= datetime.combine(next_week, datetime.max.time())
    ).count()
    # Total Interviews Scheduled
    total_interviews = db.query(CandidateInterview).count()
    # Interviews This Month
    interviews_month = db.query(CandidateInterview).filter(
        extract('month', CandidateInterview.interview_date) == today.month,
        extract('year', CandidateInterview.interview_date) == today.year
    ).count()
    # Candidates in Marketing Phase
    marketing_candidates = db.query(CandidateORM.full_name).join( 
    CandidateMarketingORM, 
    CandidateMarketingORM.candidate_id == CandidateORM.id 
    ).filter( 
        CandidateMarketingORM.status == "active" 
    ).all() 
    # Interview Feedback Breakdown
    feedback_breakdown = db.query(
        CandidateInterview.feedback,
        func.count(CandidateInterview.id)
    ).group_by(CandidateInterview.feedback).all()
    feedback_dict = {}
    for feedback, count in feedback_breakdown:
        if feedback:
            feedback_dict[feedback] = count
        else:
            feedback_dict["No Feedback"] = count
    return {
        "upcoming_interviews": upcoming_interviews,
        "total_interviews": total_interviews,
        "interviews_month": interviews_month,
        "marketing_candidates":  len(marketing_candidates),
        "feedback_breakdown": feedback_dict
    }

# upcoming batches
def get_upcoming_batches(db: Session, limit: int = 3) -> List[Dict[str, Any]]:
    today = date.today()
    upcoming_batches = db.query(Batch).filter(
        Batch.startdate > today
    ).order_by(Batch.startdate).limit(limit).all()
    return [
        {
            "batchname": batch.batchname,
            "startdate": batch.startdate,
            "enddate": batch.enddate
        }
        for batch in upcoming_batches
    ]

# Top batch revenue
def get_top_batches_revenue(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        top_batches = db.query(
            Batch.batchname,
            func.sum(CandidateORM.fee_paid).label("total_revenue"),
            func.count(CandidateORM.id).label("candidate_count")
        ).join(
            CandidateORM,
            CandidateORM.batchid == Batch.batchid
        ).group_by(
            Batch.batchid,
            Batch.batchname
        ).order_by(
            desc("total_revenue")
        ).limit(limit).all()
        return [
            {
                "batch_name": name,
                "total_revenue": float(total_revenue),
                "candidate_count": candidate_count
            }
            for name, total_revenue, candidate_count in top_batches
        ]
    except Exception as e:
        print(f"Error in get_top_batches_revenue: {e}")
        return []

# Employee birthdays
def get_employee_birthdays(db: Session):
    today = date.today()
    next_week = today + timedelta(days=7)

    todays_birthdays = db.query(EmployeeORM).filter(
        EmployeeORM.status == 1,
        func.extract('month', EmployeeORM.dob) == today.month,
        func.extract('day', EmployeeORM.dob) == today.day
    ).all()

    upcoming_birthdays = db.query(EmployeeORM).filter(
        EmployeeORM.status == 1,
        or_(
            and_(
                func.extract('month', EmployeeORM.dob) == today.month,
                func.extract('day', EmployeeORM.dob) > today.day
            ),
            and_(
                func.extract('month', EmployeeORM.dob) == (today.month % 12) + 1,
                func.extract('day', EmployeeORM.dob) <= next_week.day
            )
        )
    ).order_by(
        func.extract('month', EmployeeORM.dob),
        func.extract('day', EmployeeORM.dob)
    ).limit(10).all()

    return {
        "today": [{"name": emp.name, "dob": emp.dob.isoformat() if emp.dob else None} for emp in todays_birthdays],
        "upcoming": [{"name": emp.name, "dob": emp.dob.isoformat() if emp.dob else None} for emp in upcoming_birthdays]
    }


# Fetching Leads
def fetch_all_leads_paginated_dashboard(page: int, limit: int, db: Session) -> dict[str, any]:
    skip = (page - 1) * limit
    # Get total count
    total_leads = db.query(func.count(LeadORM.id)).scalar() or 0
    # Get paginated leads
    leads = db.query(LeadORM)\
        .order_by(LeadORM.entry_date.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    # Convert to list of dictionaries
    leads_data = [{
        "id": lead.id,
        "full_name": lead.full_name,
        "entry_date": lead.entry_date.isoformat() if lead.entry_date else None,
        "phone": lead.phone,
        "email": lead.email,
        "workstatus": lead.workstatus,
        "status": lead.status,
        "closed_date": lead.closed_date.isoformat() if lead.closed_date else None,
        "moved_to_candidate": lead.moved_to_candidate
    } for lead in leads]
    return {
        "success": True,
        "data": {
            "leads": leads_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_leads,
                "pages": (total_leads + limit - 1) // limit
            }
        },
        "message": "Leads retrieved successfully"
    }


def get_lead_metrics(db: Session) -> dict[str, any]:
    # Total leads count
    total_leads = db.query(func.count(LeadORM.id)).scalar() or 0
    # Leads in current month
    current_month = datetime.now().month
    current_year = datetime.now().year
    leads_this_month = db.query(func.count(LeadORM.id)).filter(
        extract('month', LeadORM.entry_date) == current_month,
        extract('year', LeadORM.entry_date) == current_year
    ).scalar() or 0
    # Latest lead
    latest_lead = db.query(LeadORM).order_by(LeadORM.entry_date.desc()).first()
    # Prepare latest lead data
    latest_lead_data = None
    if latest_lead:
        latest_lead_data = {
            "id": latest_lead.id,
            "full_name": latest_lead.full_name,
            "entry_date": latest_lead.entry_date.isoformat() if latest_lead.entry_date else None,
            "phone": latest_lead.phone,
            "email": latest_lead.email,
            "workstatus": latest_lead.workstatus,
            "status": latest_lead.status
        }
    return {
        "total_leads": total_leads,
        "leads_this_month": leads_this_month,
        "latest_lead": latest_lead_data
    }




def candidate_interview_performance(db: Session):
    results = (
        db.query(
            CandidateORM.id.label("candidate_id"),
            CandidateORM.full_name.label("candidate_name"),
            func.count(CandidateInterview.id).label("total_interviews"),
            func.coalesce(
                func.sum(
                    case((CandidateInterview.feedback == "Positive", 1), else_=0)
                ), 0
            ).label("success_count")
        )
        .join(CandidateMarketingORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
        .outerjoin(CandidateInterview, CandidateInterview.candidate_id == CandidateORM.id)
        .group_by(CandidateORM.id, CandidateORM.full_name)
        .all()
    )

    return [
        {
            "candidate_id": row.candidate_id,
            "candidate_name": row.candidate_name,
            "total_interviews": row.total_interviews,
            "success_count": row.success_count
        }
        for row in results
    ]

