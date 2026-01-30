import re
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
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
    all_sessions = db.query(SessionORM).all()
    all_recordings = db.query(Recording).all()
    matched_sessions = []
    matched_recordings = []

    def is_match(text):
        if not text: return False
        t = text.lower()
        if "sai teja" in t and "sai teja" not in emp_name_orig:
            return False
        return any(part in t for part in emp_name_parts)

    for s in all_sessions:
        if is_match(s.title):
            matched_sessions.append(s)

    for r in all_recordings:
        text = " ".join(filter(None, [r.description, r.subject or ""]))
        if is_match(text):
            matched_recordings.append(r)

    return matched_recordings, matched_sessions

def get_employee_dashboard_metrics(db: Session, employee_id: int) -> Dict[str, Any]:
    today = date.today()
    three_months_ago = today - timedelta(days=90)
    employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
    if not employee:
        return None
    placements_found = (
        db.query(CandidatePlacementORM)
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
    for p in placements_found:
        
        candidate = db.query(CandidateORM).filter(CandidateORM.id == p.candidate_id).first()
        p_dict = {
            "id": p.id,
            "candidate_id": p.candidate_id,
            "candidate_name": candidate.full_name if candidate else "Anonymous",
            "company": p.company,
            "position": p.position,
            "placement_date": p.placement_date.isoformat() if p.placement_date else None,
            "status": p.status
        }
        placements.append(p_dict)
    
    placements.sort(key=lambda x: x["placement_date"] or "", reverse=True)
    
    all_associated_ids = [r[0] for r in db.query(CandidatePreparation.candidate_id).filter(
        or_(
            CandidatePreparation.instructor1_id == employee_id,
            CandidatePreparation.instructor2_id == employee_id,
            CandidatePreparation.instructor3_id == employee_id
        )
    ).all()]
    all_associated_ids = list(set(all_associated_ids))

    
    prep_candidates_raw = (
        db.query(CandidatePreparation, CandidateORM.full_name)
        .join(CandidateORM, CandidatePreparation.candidate_id == CandidateORM.id)
        .filter(
            CandidatePreparation.candidate_id.in_(all_associated_ids),
            CandidatePreparation.status == "active"
        )
        .all()
    )
    
    prep_candidates = []
    for prep, full_name in prep_candidates_raw:
        prep_candidates.append({
            "id": prep.id,
            "candidate_id": prep.candidate_id,
            "full_name": full_name,
            "status": prep.status,
            "start_date": str(prep.start_date) if prep.start_date else None,
        })
    
    marketing_candidates_raw = (
        db.query(CandidateMarketingORM, CandidateORM.full_name)
        .join(CandidateORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
        .filter(
            CandidateMarketingORM.candidate_id.in_(all_associated_ids),
            CandidateMarketingORM.status == "active"
        )
        .all()
    )

    marketing_candidates = []
    for marketing, full_name in marketing_candidates_raw:
        marketing_candidates.append({
            "id": marketing.id,
            "candidate_id": marketing.candidate_id,
            "full_name": full_name,
            "status": marketing.status,
            "start_date": str(marketing.start_date) if marketing.start_date else None,
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
        db.query(CandidatePlacementORM)
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
    for p in job_help_found:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == p.candidate_id).first()
        jh_dict = {
            "id": p.id,
            "candidate_id": p.candidate_id,
            "candidate_name": candidate.full_name if candidate else "Anonymous",
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
    recordings = sorted(recordings, key=lambda x: x.classdate or date.min, reverse=True)[:20]
    sessions = sorted(sessions, key=lambda x: x.sessiondate or date.min, reverse=True)[:20]
    
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
        "assigned_prep_candidates": prep_candidates,
        "assigned_marketing_candidates": marketing_candidates,
        "candidate_metrics": {
            "prep_count": len(prep_candidates),
            "marketing_count": len(marketing_candidates),
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
