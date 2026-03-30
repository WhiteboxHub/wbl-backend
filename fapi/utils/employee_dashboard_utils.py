import re
from sqlalchemy.orm import Session, aliased
from fapi.core.cache import cache_result
from sqlalchemy import or_, and_, case
from typing import Dict, Any, List
from datetime import date, timedelta
from fapi.db.models import (
    EmployeeORM, CandidatePlacementORM, CandidateORM, 
    CandidateMarketingORM, CandidatePreparation, 
    EmployeeTaskORM, Recording, Session as SessionORM,
    JobTypeORM
)

def get_employee_sessions_and_recordings_internal(db: Session, employee_id: int):
    employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id, EmployeeORM.status == 1).first()
    if not employee:
        return [], []

    emp_name_orig = employee.name.lower().strip()
    emp_name_parts = emp_name_orig.split()
    
    # Build filters for database-side matching
    session_filters = [SessionORM.title.ilike(f"%{part}%") for part in emp_name_parts if len(part) > 2]
    recording_filters = [
        or_(
            Recording.description.ilike(f"%{part}%"),
            Recording.subject.ilike(f"%{part}%")
        ) for part in emp_name_parts if len(part) > 2
    ]
    
    matched_sessions = []
    matched_recordings = []
    
    if session_filters:
        query = db.query(SessionORM).filter(or_(*session_filters))
        if "sai teja" not in emp_name_orig:
            query = query.filter(~SessionORM.title.ilike("%sai teja%"))
        matched_sessions = query.order_by(SessionORM.sessiondate.desc()).limit(20).all()
        
    if recording_filters:
        query = db.query(Recording).filter(or_(*recording_filters))
        if "sai teja" not in emp_name_orig:
            query = query.filter(~Recording.description.ilike("%sai teja%"))
        matched_recordings = query.order_by(Recording.classdate.desc()).limit(20).all()

    return matched_recordings, matched_sessions

@cache_result(ttl=300, prefix="metrics")
def get_employee_dashboard_metrics(db: Session, employee_id: int) -> Dict[str, Any]:
    today = date.today()
    three_months_ago = today - timedelta(days=90)
    employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
    if not employee:
        return None
    placements_found = (
        db.query(CandidatePlacementORM, CandidateORM.full_name)
        .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
        .join(CandidatePreparation, CandidatePlacementORM.candidate_id == CandidatePreparation.candidate_id)
        .filter(
            or_(
                CandidatePreparation.instructor1_id == employee_id,
                CandidatePreparation.instructor2_id == employee_id,
                CandidatePreparation.instructor3_id == employee_id
            )
        )
        .distinct()
        .all()
    )
    
    placements = []
    for p, full_name in placements_found:
        p_dict = {
            "id": p.id,
            "candidate_id": p.candidate_id,
            "candidate_name": full_name or "Anonymous",
            "company": p.company,
            "position": p.position,
            "placement_date": p.placement_date.isoformat() if p.placement_date else None,
            "status": p.status
        }
        placements.append(p_dict)
    
    placements.sort(key=lambda x: x["placement_date"] or "", reverse=True)
    
    # Optimized combined candidates query
    I1 = aliased(EmployeeORM)
    I2 = aliased(EmployeeORM)
    I3 = aliased(EmployeeORM)
    
    candidates_raw = (
        db.query(
            CandidatePreparation,
            CandidateORM.full_name,
            I1.name.label("inst1_name"),
            I2.name.label("inst2_name"),
            I3.name.label("inst3_name"),
            CandidateMarketingORM.status.label("mkt_status")
        )
        .join(CandidateORM, CandidatePreparation.candidate_id == CandidateORM.id)
        .outerjoin(I1, CandidatePreparation.instructor1_id == I1.id)
        .outerjoin(I2, CandidatePreparation.instructor2_id == I2.id)
        .outerjoin(I3, CandidatePreparation.instructor3_id == I3.id)
        .outerjoin(CandidateMarketingORM, and_(
            CandidatePreparation.candidate_id == CandidateMarketingORM.candidate_id,
            CandidateMarketingORM.status == "active"
        ))
        .filter(
            or_(
                CandidatePreparation.instructor1_id == employee_id,
                CandidatePreparation.instructor2_id == employee_id,
                CandidatePreparation.instructor3_id == employee_id
            ),
            CandidatePreparation.status == "active"
        )
        .all()
    )
    
    consolidated_candidates = []
    for prep, full_name, i1, i2, i3, mkt_status in candidates_raw:
        # Determine status
        status = "In Marketing" if mkt_status == "active" else "In Preparation"
        
        # Get other instructors
        instructors = []
        if prep.instructor1_id and prep.instructor1_id != employee_id:
            instructors.append(i1 or "Unknown")
        if prep.instructor2_id and prep.instructor2_id != employee_id:
            instructors.append(i2 or "Unknown")
        if prep.instructor3_id and prep.instructor3_id != employee_id:
            instructors.append(i3 or "Unknown")
            
        consolidated_candidates.append({
            "id": prep.id,
            "candidate_id": prep.candidate_id,
            "full_name": full_name,
            "status": status,
            "other_instructors": ", ".join(instructors) if instructors else "None"
        })
    
    
    all_tasks_raw = (
        db.query(EmployeeTaskORM)
        .filter(EmployeeTaskORM.employee_id == employee_id)
        .all()
    )
    
    tasks = []
    completed_task_count = 0
    pending_task_count = 0
    in_progress_task_count = 0
    
    for t in all_tasks_raw:
        if t.status == "completed":
            completed_task_count += 1
        elif t.status == "pending":
            pending_task_count += 1
        elif t.status == "in_progress":
            in_progress_task_count += 1
        if t.status != "completed":
            task_dict = {
                "id": t.id,
                "task": re.sub(r'<[^>]*>', '', t.task) if t.task else "",
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "assigned_date": t.assigned_date.isoformat() if t.assigned_date else None
            }
            tasks.append(task_dict)
    
    
    job_help_found = (
        db.query(CandidatePlacementORM, CandidateORM.full_name)
        .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
        .join(CandidatePreparation, CandidatePlacementORM.candidate_id == CandidatePreparation.candidate_id)
        .filter(
            and_(
                or_(
                    CandidatePreparation.instructor1_id == employee_id,
                    CandidatePreparation.instructor2_id == employee_id,
                    CandidatePreparation.instructor3_id == employee_id
                ),
                CandidatePlacementORM.placement_date >= three_months_ago
            )
        )
        .distinct()
        .all()
    )
    
    job_help_candidates = []
    for p, full_name in job_help_found:
        jh_dict = {
            "id": p.id,
            "candidate_id": p.candidate_id,
            "candidate_name": full_name or "Anonymous",
            "company": p.company,
            "position": p.position,
            "placement_date": p.placement_date.isoformat() if p.placement_date else None,
            "status": p.status
        }
        job_help_candidates.append(jh_dict)

    
    job_help_candidates.sort(key=lambda x: x["placement_date"] or "", reverse=True)

    
    jobs_raw = db.query(JobTypeORM).filter(
        or_(
            JobTypeORM.job_owner_1 == employee_id,
            JobTypeORM.job_owner_2 == employee_id,
            JobTypeORM.job_owner_3 == employee_id
        )
    ).all()
    
    jobs = []
    for j in jobs_raw:
        jobs.append({
            "id": j.id,
            "unique_id": j.unique_id,
            "name": j.name,
            "category": j.category,
            "description": j.description
        })
    

    recordings, sessions = get_employee_sessions_and_recordings_internal(db, employee_id)
    
    return {
        "employee_info": {
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "phone": employee.phone,
            "startdate": employee.startdate.isoformat() if employee.startdate else None,
            "dob": employee.dob.isoformat() if employee.dob else None,
            "status": employee.status,
            "state": employee.state,
            "aadhaar": employee.aadhaar,
            "instructor": employee.instructor,
            "address": employee.address,
            "notes": re.sub(r'<[^>]*>', '', employee.notes) if employee.notes else ""
        },
        "placements": placements,
        "candidates": consolidated_candidates,
        "candidate_metrics": {
            "total_count": len(consolidated_candidates),
            "prep_count": len([c for c in consolidated_candidates if c["status"] == "In Preparation"]),
            "marketing_count": len([c for c in consolidated_candidates if c["status"] == "In Marketing"]),
            "placement_count": len(placements)
        },
        "task_metrics": {
            "total_completed": completed_task_count,
            "total_pending": pending_task_count,
            "total_in_progress": in_progress_task_count
        },
        "jobs": jobs,
        "jobs_count": len(jobs),
        "pending_tasks": tasks,
        "completed_task_count": completed_task_count,
        "job_help_candidates": job_help_candidates,
        "classes": recordings,
        "sessions": sessions,
        "is_birthday": employee.dob.month == today.month and employee.dob.day == today.day if employee.dob else False
    }
