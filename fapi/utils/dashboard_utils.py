from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_, extract
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from fapi.db.models import Batch, CandidateORM, CandidateMarketingORM, CandidatePlacementORM, CandidateInterview

def get_batch_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()
    #Current active bacthes
    current_active_batches = db.query(Batch).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).count()
    #Enrolled candidates
    enrolled_candidates_current = db.query(CandidateORM).join(
        Batch, 
        CandidateORM.batchid == Batch.batchid  
    ).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).count()
    total_candidates = db.query(CandidateORM).count()
    
    # Candidates in Last Batch
    last_batch = db.query(Batch).order_by(desc(Batch.startdate)).first()
    candidates_last_batch = 0
    if last_batch:
        candidates_last_batch = db.query(CandidateORM).filter(
            CandidateORM.batchid == last_batch.batchid
        ).count()
    
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
        "current_active_batches": current_active_batches,
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
    
    # Fee Collected This Month
    fee_collected_month = db.query(func.sum(CandidateORM.fee_paid)).filter(
        CandidateORM.enrolled_date >= first_day_month
    ).scalar() or 0
    
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
        "fee_collected_month": fee_collected_month,
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

def get_interview_metrics(db: Session) -> Dict[str, Any]:
    today = datetime.now().date()
    next_week = today + timedelta(days=7)
    first_day_month = today.replace(day=1)
    
    # Upcoming Interviews (Next 7 Days)
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
    marketing_candidates = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.status == "active"
    ).count()
    
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
        "marketing_candidates": marketing_candidates,
        "feedback_breakdown": feedback_dict
    }

def get_upcoming_batches(db: Session, limit: int = 3) -> List[Dict[str, Any]]:
    today = date.today()
    upcoming_batches = db.query(Batch).filter(
        Batch.startdate > today
    ).order_by(Batch.startdate).limit(limit).all()
    
    return [
        {
            "name": batch.batchname,
            "startdate": batch.startdate,
            "end_date": batch.enddate
        }
        for batch in upcoming_batches
    ]

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