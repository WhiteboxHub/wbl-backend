from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract, or_, and_, case,text, String, cast, literal_column
from datetime import datetime, date, timedelta
from typing import Dict, Any, List
from fapi.db.models import Batch, CandidateORM, CandidateMarketingORM, CandidatePlacementORM, CandidateInterview, EmployeeORM, LeadORM, CandidatePreparation, Vendor, VendorContactExtractsORM, Recording, RecordingBatch, EmployeeTaskORM, JobTypeORM, JobActivityLogORM, PlacementFeeCollection, AmountCollectedEnum
from fapi.db.schemas import CandidatePreparationMetrics, EmployeeTaskMetrics, JobsMetrics
import re

def get_batch_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()
    current_active_batches = db.query(Batch).filter(
        Batch.startdate <= today,
        Batch.enddate >= today
    ).all()
    if current_active_batches:
        latest_batch = max(current_active_batches, key=lambda b: b.startdate)
        current_active_batches_str = latest_batch.batchname
    else:
        current_active_batches_str = "No active batches"
    # If multiple batches, show count and first batch name
    current_active_batches_count = len(current_active_batches)

    # Enrolled candidates
    latest_active_batch = (
        db.query(Batch)
        .filter(Batch.startdate <= today, Batch.enddate >= today)
        .order_by(Batch.startdate.desc())
        .first()
    )

    if latest_active_batch:
        enrolled_candidates_current = (
            db.query(CandidateORM)
            .filter(CandidateORM.batchid == latest_active_batch.batchid)
            .count()
        )
    else:
        enrolled_candidates_current = 0

    total_candidates = db.query(CandidateORM).count()
    # Candidates enrolled in Last Batch only for batches that have started
    previous_batch = (
            db.query(Batch)
            .filter(Batch.startdate <= date.today())
            .order_by(desc(Batch.startdate))
            .offset(1)  
            .first()
        )

    candidates_previous_batch = 0
    if previous_batch:
        candidates_previous_batch = (
                db.query(CandidateORM)
                .filter(CandidateORM.batchid == previous_batch.batchid)
                .count()
            )


    # New Enrollments in this Month
    first_day_month = today.replace(day=1)
    new_enrollments_month = db.query(CandidateORM).filter(
        CandidateORM.enrolled_date >= first_day_month
    ).count()
    status_breakdown = db.query(
        CandidateORM.status,
        func.count(CandidateORM.id)
    ).group_by(CandidateORM.status).all()
    status_dict = {status: count for status, count in status_breakdown}
    
    # Add Total Placements to status breakdown
    total_placements = db.query(CandidatePlacementORM).count()
    status_dict["Placements"] = total_placements
    return {
        "current_active_batches": current_active_batches_str,
        "current_active_batches_count": current_active_batches_count,
        "enrolled_candidates_current": enrolled_candidates_current,
        "total_candidates": total_candidates,
        "candidates_previous_batch": candidates_previous_batch,
        "new_enrollments_month": new_enrollments_month,
        "candidate_status_breakdown": status_dict
    }


def get_financial_metrics(db: Session) -> Dict[str, Any]:
    today = date.today()

    # Current batch
    current_batch = (
        db.query(Batch)
        .filter(Batch.startdate <= today, Batch.enddate >= today)
        .order_by(desc(Batch.startdate))
        .first()
    )

    total_fee_current_batch = 0
    if current_batch:
        total_fee_current_batch = (
            db.query(func.sum(CandidateORM.fee_paid))
            .filter(CandidateORM.batchid == current_batch.batchid)
            .scalar()
            or 0
        )

    # Previous batch
    previous_batch = (
        db.query(Batch)
        .filter(Batch.startdate < today)
        .order_by(desc(Batch.startdate))
        .offset(1)
        .first()
    )

    total_fee_previous_batch = 0
    if previous_batch:
        total_fee_previous_batch = (
            db.query(func.sum(CandidateORM.fee_paid))
            .filter(CandidateORM.batchid == previous_batch.batchid)
            .scalar()
            or 0
        )
        
    # Top 5 Batches (Zig-Zag Pattern)
    top_batches = (
        db.query(
            Batch.batchname,
            func.sum(CandidateORM.fee_paid).label("total_fee")
        )
        .join(CandidateORM, CandidateORM.batchid == Batch.batchid)
        .group_by(Batch.batchid)
        .order_by(desc("total_fee"))
        .limit(5)
        .all()
    )

    sorted_batches = list(top_batches) 

    # Zig-Zag: High → Low → High → Low → High
    pattern_result = []
    left = 0
    right = len(sorted_batches) - 1
    take_high = True

    while left <= right:
        if take_high:
            pattern_result.append(sorted_batches[left])
            left += 1
        else:
            pattern_result.append(sorted_batches[right])
            right -= 1
        take_high = not take_high

    top_batches_list = [
        {"batch_name": name, "total_fee": float(total_fee)}
        for name, total_fee in pattern_result
    ]

    # Placement Fee Collection Metrics
    total_expected = db.query(func.sum(PlacementFeeCollection.deposit_amount)).scalar() or 0
    total_collected = db.query(func.sum(PlacementFeeCollection.deposit_amount)).filter(
        PlacementFeeCollection.amount_collected == AmountCollectedEnum.yes
    ).scalar() or 0
    total_pending = float(total_expected) - float(total_collected)

    first_day_month = today.replace(day=1)
    collected_this_month = db.query(func.sum(PlacementFeeCollection.deposit_amount)).filter(
        PlacementFeeCollection.amount_collected == AmountCollectedEnum.yes,
        PlacementFeeCollection.deposit_date >= first_day_month
    ).scalar() or 0

    completed_installments = db.query(PlacementFeeCollection).filter(
        PlacementFeeCollection.amount_collected == AmountCollectedEnum.yes
    ).count()
    pending_installments = db.query(PlacementFeeCollection).filter(
        PlacementFeeCollection.amount_collected == AmountCollectedEnum.no
    ).count()

    placement_fee_metrics = {
        "total_expected": float(total_expected),
        "total_collected": float(total_collected),
        "total_pending": float(total_pending),
        "collected_this_month": float(collected_this_month),
        "installment_stats": {
            "completed": completed_installments,
            "pending": pending_installments
        }
    }

    # Final output
    return {
        "total_fee_current_batch": float(total_fee_current_batch),
        "fee_collected_previous_batch": float(total_fee_previous_batch),
        "top_batches_fee": top_batches_list,
        "placement_fee_metrics": placement_fee_metrics
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
        CandidatePlacementORM.status == "Active"
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

    # Interviews Today
    interviews_today = db.query(CandidateInterview).filter(
        func.date(CandidateInterview.interview_date) == today
    ).count()

    marketing_candidates = db.query(CandidateORM).join(
        CandidateMarketingORM,
        CandidateMarketingORM.candidate_id == CandidateORM.id
    ).filter(
        CandidateMarketingORM.status == "active"
    ).all()

    priority_1_candidates = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.status == "active",
        CandidateMarketingORM.priority == 1
    ).count()

    priority_2_candidates = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.status == "active",
        CandidateMarketingORM.priority == 2
    ).count()

    priority_3_candidates = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.status == "active",
        CandidateMarketingORM.priority == 3
    ).count()    # Interview Feedback Breakdown
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
        "interviews_today": interviews_today,
        "marketing_candidates":  len(marketing_candidates),
        "priority_1_candidates": priority_1_candidates,
        "priority_2_candidates": priority_2_candidates,
        "priority_3_candidates": priority_3_candidates,
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


def get_lead_metrics(db: Session) -> dict[str, any]:
    
    total_leads = db.query(func.count(LeadORM.id)).scalar() or 0

    current_month = datetime.now().month
    current_year = datetime.now().year

    leads_this_month = db.query(func.count(LeadORM.id)).filter(
        extract('month', LeadORM.entry_date) == current_month,
        extract('year', LeadORM.entry_date) == current_year
    ).scalar() or 0

    start_of_week = datetime.combine(
        (date.today() - timedelta(days=date.today().weekday())), datetime.min.time()
    )
    end_of_today = datetime.combine(date.today(), datetime.max.time())

    leads_this_week = db.query(func.count(LeadORM.id)).filter(
        LeadORM.entry_date >= start_of_week,
        LeadORM.entry_date <= end_of_today
    ).scalar() or 0

    
    open_leads = db.query(func.count(LeadORM.id)).filter(LeadORM.status == "open").scalar() or 0
    closed_leads = db.query(func.count(LeadORM.id)).filter(LeadORM.status == "closed").scalar() or 0
    future_leads = db.query(func.count(LeadORM.id)).filter(LeadORM.status == "future").scalar() or 0

   
    latest_lead = db.query(LeadORM).order_by(LeadORM.entry_date.desc()).first()
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
        "leads_this_week": leads_this_week,
        "open_leads": open_leads,
        "closed_leads": closed_leads,
        "future_leads":future_leads,
        "latest_lead": latest_lead_data,
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
        .having(func.count(CandidateInterview.id) > 0)  
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




def get_candidate_preparation_metrics(db: Session):
    total_preparation_candidates = db.query(func.count(CandidatePreparation.id)).scalar() or 0
    active_candidates = db.query(func.count(CandidatePreparation.id)).filter(
        CandidatePreparation.status == "Active"
    ).scalar() or 0
    inactive_candidates = db.query(func.count(CandidatePreparation.id)).filter(
        CandidatePreparation.status == "Inactive"
    ).scalar() or 0

    return CandidatePreparationMetrics(
        total_preparation_candidates=total_preparation_candidates,
        active_candidates=active_candidates,
        inactive_candidates=inactive_candidates
    )


def get_vendor_stats(db: Session):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday()) 

    total_vendors = db.query(func.count(Vendor.id)).scalar()
    today_extracted = (
        db.query(func.count(VendorContactExtractsORM.id))
        .filter(
            and_(
                VendorContactExtractsORM.email.isnot(None),
                VendorContactExtractsORM.created_at >= today_start,
            )
        )
        .scalar()
    )
    week_extracted = (
        db.query(func.count(VendorContactExtractsORM.id))
        .filter(
            and_(
                VendorContactExtractsORM.email.isnot(None),
                VendorContactExtractsORM.created_at >= week_start,
            )
        )
        .scalar()
    )
    return {
        "total_vendors": total_vendors or 0,
        "today_extracted": today_extracted or 0,
        "week_extracted": week_extracted or 0,
    }




def get_classes_per_latest_batches(db: Session, limit: int = 5):
    latest_batches_subq = (
        db.query(Batch.batchid)
        .order_by(desc(Batch.startdate))
        .limit(limit)
        .subquery()
    )

    result = (
        db.query(
            Batch.batchname,
            func.count(Recording.id).label("classes_count"),
            func.max(Batch.startdate).label("max_startdate")
        )
        .join(RecordingBatch, RecordingBatch.batch_id == Batch.batchid)
        .join(Recording, Recording.id == RecordingBatch.recording_id)
        .filter(Batch.batchid.in_(latest_batches_subq))
        .group_by(Batch.batchname)
        .order_by(desc(func.max(Batch.startdate)))
        .all()
    )

    return result

def get_employee_task_metrics(db: Session) -> EmployeeTaskMetrics:
    today = date.today()
    total_tasks = db.query(EmployeeTaskORM).count()
    pending_tasks = db.query(EmployeeTaskORM).filter(EmployeeTaskORM.status == "pending").count()
    in_progress_tasks = db.query(EmployeeTaskORM).filter(EmployeeTaskORM.status == "in_progress").count()
    completed_tasks = db.query(EmployeeTaskORM).filter(EmployeeTaskORM.status == "completed").count()
    overdue_tasks = db.query(EmployeeTaskORM).filter(
        and_(
            EmployeeTaskORM.status != "completed",
            EmployeeTaskORM.due_date < today
        )
    ).count()

    return EmployeeTaskMetrics(
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks
    )


def get_job_metrics(db: Session) -> JobsMetrics:
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    total_job_types = db.query(JobTypeORM).count()
    total_activities = db.query(func.sum(JobActivityLogORM.activity_count)).scalar() or 0
    activities_today = db.query(func.sum(JobActivityLogORM.activity_count)).filter(
        JobActivityLogORM.activity_date == today
    ).scalar() or 0
    activities_this_week = db.query(func.sum(JobActivityLogORM.activity_count)).filter(
        JobActivityLogORM.activity_date >= week_ago
    ).scalar() or 0
    
    recent_logs = (
        db.query(JobActivityLogORM, JobTypeORM.name.label("job_name"))
        .join(JobTypeORM, JobActivityLogORM.job_type_id == JobTypeORM.id)
        .order_by(JobActivityLogORM.activity_date.desc())
        .limit(10)
        .all()
    )
    
    recent_activities = []
    for log, job_name in recent_logs:
        recent_activities.append({
            "id": log.id,
            "job_name": job_name,
            "activity_date": log.activity_date.isoformat() if log.activity_date else None,
            "activity_count": log.activity_count,
            "notes": log.notes
        })
        
    return JobsMetrics(
        total_job_types=total_job_types,
        total_activities=int(total_activities),
        activities_today=int(activities_today),
        activities_this_week=int(activities_this_week),
        recent_activities=recent_activities
    )


# Dashboard-specific functions for employee tasks and jobs
def get_tasks_by_employee_id_for_dashboard(db: Session, employee_id: int) -> List[dict]:
    """Get tasks for employee with HTML stripped (for dashboard display)"""
    tasks = db.query(EmployeeTaskORM).filter(EmployeeTaskORM.employee_id == employee_id).all()
    result = []
    for t in tasks:
        # Strip HTML tags from task description for clean dashboard display
        clean_task = re.sub(r'<[^>]*>', '', t.task) if t.task else ""
        result.append({
            "id": t.id,
            "employee_id": t.employee_id,
            "employee_name": t.employee.name if t.employee else None,
            "task": clean_task,  # Plain text for dashboard
            "assigned_date": t.assigned_date,
            "due_date": t.due_date,
            "status": t.status,
            "priority": t.priority,
            "notes": t.notes
        })
    return result


def get_job_types_by_employee_id_for_dashboard(db: Session, employee_id: int) -> List[dict]:

    try:
        from sqlalchemy.orm import aliased
        from sqlalchemy import or_
        Owner1 = aliased(EmployeeORM)
        Owner2 = aliased(EmployeeORM)
        Owner3 = aliased(EmployeeORM)
        LastModUserEmployee = aliased(EmployeeORM)

        rows = (
            db.query(
                JobTypeORM.id,
                JobTypeORM.unique_id,
                JobTypeORM.name,
                JobTypeORM.job_owner_1,
                JobTypeORM.job_owner_2,
                JobTypeORM.job_owner_3,
                JobTypeORM.category,
                JobTypeORM.description,
                JobTypeORM.notes,
                JobTypeORM.lastmod_date_time,
                Owner1.name.label("job_owner_1_name"),
                Owner2.name.label("job_owner_2_name"),
                Owner3.name.label("job_owner_3_name"),
                LastModUserEmployee.name.label("lastmod_user_name")
            )
            .outerjoin(Owner1, Owner1.id == JobTypeORM.job_owner_1)
            .outerjoin(Owner2, Owner2.id == JobTypeORM.job_owner_2)
            .outerjoin(Owner3, Owner3.id == JobTypeORM.job_owner_3)
            .outerjoin(LastModUserEmployee, LastModUserEmployee.id == JobTypeORM.lastmod_user_id)
            .filter(
                or_(
                    JobTypeORM.job_owner_1 == employee_id,
                    JobTypeORM.job_owner_2 == employee_id,
                    JobTypeORM.job_owner_3 == employee_id
                )
            )
            .order_by(JobTypeORM.id)
            .all()
        )

        # Fetch the name of the person whose dashboard this is
        target_employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
        target_name = target_employee.name if target_employee else "Employee"

        result = []
        for row in rows:
            item = {
                "id": row.id,
                "unique_id": row.unique_id,
                "name": row.name,
                "employee_name": target_name,
                "job_owner_1": row.job_owner_1,
                "job_owner_2": row.job_owner_2,
                "job_owner_3": row.job_owner_3,
                "job_owner_1_name": row.job_owner_1_name,
                "job_owner_2_name": row.job_owner_2_name,
                "job_owner_3_name": row.job_owner_3_name,
                "category": row.category or "manual",
                "description": row.description,
                "notes": row.notes,
                "lastmod_date_time": row.lastmod_date_time.isoformat() if isinstance(row.lastmod_date_time, datetime) else str(row.lastmod_date_time) if row.lastmod_date_time else None,
                "lastmod_user_name": row.lastmod_user_name
            }
            result.append(item)

        return result

    except Exception as e:
        # Return empty list on error for dashboard
        return []