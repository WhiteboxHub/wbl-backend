import re
from sqlalchemy.orm import Session
from typing import List, Dict
from fapi.db.models import (
    EmployeeORM, 
    CandidatePreparation, 
    CandidateMarketingORM, 
    Recording, 
    JobTypeORM, 
    EmployeeTaskORM, 
    CandidatePlacementORM, 
    CandidateORM,
    Batch
)
from typing import List
from fapi.db.models import Session as SessionORM 
from datetime import datetime, date
from typing import List, Dict, Any
from sqlalchemy import or_

def search_employees(db: Session, query: str) -> List[EmployeeORM]:
    return db.query(EmployeeORM).filter(EmployeeORM.name.ilike(f"%{query}%")).all()


def safe_date(value):
    
    if not value or value in ["0000-00-00", "0000-00-00 00:00:00"]:
        return None
    if isinstance(value, (datetime, date)):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def get_employee_details(db: Session) -> List[Dict]:
    employees = db.query(EmployeeORM).all()
    result = []
    for emp in employees:
        result.append({
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
            "phone": emp.phone,
            "startdate": safe_date(emp.startdate),
            "address": emp.address,
            "state": emp.state,
            "dob": safe_date(emp.dob),
            "enddate": safe_date(emp.enddate),
            "notes": re.sub(r'<[^>]*>', '', emp.notes) if emp.notes else "",
            "status": emp.status,
            "instructor": emp.instructor,
            "aadhaar": emp.aadhaar
        })
    return result





def get_employee_candidates(db: Session, employee_id: int) -> Dict:
    
    prep_records = db.query(CandidatePreparation).filter(
        (CandidatePreparation.instructor1_id == employee_id) |
        (CandidatePreparation.instructor2_id == employee_id) |
        (CandidatePreparation.instructor3_id == employee_id),
        CandidatePreparation.status == "active"
    ).all()

    prep_candidates = [prep.candidate.full_name for prep in prep_records]

    prep_candidate_ids = [prep.candidate_id for prep in prep_records]  
    marketing_records = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.candidate_id.in_(prep_candidate_ids),
        CandidateMarketingORM.status == "active"
    ).all()

    marketing_candidates = [m.candidate.full_name for m in marketing_records]

    return {
        "preparation": {
            "count": len(prep_candidates),
            "names": prep_candidates
        },
        "marketing": {
            "count": len(marketing_candidates),
            "names": marketing_candidates
        }
    }



def get_employee_sessions_and_recordings(db: Session, employee_id: int):
    employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id, EmployeeORM.status == 1).first()
    if not employee:
        return {"error": "Active employee not found"}

    emp_name = employee.name.lower().strip()  

    all_sessions = db.query(SessionORM).all()
    all_recordings = db.query(Recording).all()

    matched_sessions = []
    matched_recordings = []

    
    for s in all_sessions:
        if s.title and any(part in s.title.lower() for part in emp_name.split()):
            matched_sessions.append(s)

    for r in all_recordings:
        text = " ".join(filter(None, [r.description, r.subject or ""])).lower()
        if any(part in text for part in emp_name.split()):
            matched_recordings.append(r)

    return {
        "employee": employee,
        "sessions": matched_sessions,
        "recordings": matched_recordings
    }


def get_employee_jobs(db: Session, employee_id: int) -> Dict[str, Any]:
    jobs = db.query(JobTypeORM).filter(
        or_(
            JobTypeORM.job_owner_1 == employee_id,
            JobTypeORM.job_owner_2 == employee_id,
            JobTypeORM.job_owner_3 == employee_id
        )
    ).all()
    
    job_names = [j.name for j in jobs]
    
    return {
        "count": len(job_names),
        "names": job_names
    }


import re

def get_employee_tasks(db: Session, employee_id: int) -> List[Dict[str, Any]]:
    tasks = db.query(EmployeeTaskORM).filter(EmployeeTaskORM.employee_id == employee_id).all()
    return [
        {
            "id": t.id,
            "task": re.sub(r'<[^>]*>', '', t.task) if t.task else "",
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "assigned_date": t.assigned_date.isoformat() if t.assigned_date else None
        } for t in tasks
    ]


def get_employee_placements(db: Session, employee_id: int) -> Dict[str, Any]:
    placements = db.query(CandidatePlacementORM).join(
        CandidatePreparation, 
        CandidatePlacementORM.candidate_id == CandidatePreparation.candidate_id
    ).filter(
        or_(
            CandidatePreparation.instructor1_id == employee_id,
            CandidatePreparation.instructor2_id == employee_id,
            CandidatePreparation.instructor3_id == employee_id
        )
    ).all()
    
    candidate_names = []
    for p in placements:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == p.candidate_id).first()
        if candidate:
            candidate_names.append(candidate.full_name)
    
    return {
        "count": len(candidate_names),
        "names": candidate_names
    }