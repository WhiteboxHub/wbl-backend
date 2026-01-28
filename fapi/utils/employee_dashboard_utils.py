from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any
from datetime import date, timedelta
from fapi.db.models import (
    EmployeeORM, CandidatePlacementORM, CandidateORM, 
    CandidateMarketingORM, CandidatePreparation, 
    EmployeeTaskORM, Recording, Session as SessionORM
)

def get_employee_dashboard_metrics(db: Session, employee_id: int) -> Dict[str, Any]:
    today = date.today()
    three_months_ago = today - timedelta(days=90)
    
    employee = db.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
    if not employee:
        return None
    
    # 2. Placements made by that employee (based on marketing manager)
    placements = (
        db.query(CandidatePlacementORM)
        .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
        .join(CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id)
        .filter(CandidateMarketingORM.marketing_manager == employee_id)
        .all()
    )
    
    # 3. Assigned candidates
    # Prep
    prep_candidates = (
        db.query(CandidatePreparation, CandidateORM.full_name)
        .join(CandidateORM, CandidatePreparation.candidate_id == CandidateORM.id)
        .filter(
            or_(
                CandidatePreparation.instructor1_id == employee_id,
                CandidatePreparation.instructor2_id == employee_id,
                CandidatePreparation.instructor3_id == employee_id
            )
        )
        .filter(CandidatePreparation.status == "active")
        .all()
    )
    
    # Marketing - Get all marketing candidates that are also in prep with this employee
    # First get the candidate IDs from prep
    prep_candidate_ids = [prep.candidate_id for prep in prep_candidates]
    
    marketing_candidates = (
        db.query(CandidateMarketingORM, CandidateORM.full_name)
        .join(CandidateORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
        .filter(CandidateMarketingORM.candidate_id.in_(prep_candidate_ids))
        .filter(CandidateMarketingORM.status == "active")
        .all()
    )
    
    # 4. Tasks (only pending, in process)
    tasks = (
        db.query(EmployeeTaskORM)
        .filter(EmployeeTaskORM.employee_id == employee_id)
        .filter(EmployeeTaskORM.status != "completed")
        .all()
    )
    
    # 5. Job help to placed candidated - from placement start date up to 3 months
    job_help_candidates = (
        db.query(CandidatePlacementORM)
        .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
        .join(CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id)
        .filter(
            CandidateMarketingORM.marketing_manager == employee_id,
            CandidatePlacementORM.placement_date >= three_months_ago
        )
        .all()
    )
    
    # 6. Classes and Session
    # Search for employee name in recordings and sessions
    recordings = (
        db.query(Recording)
        .filter(Recording.description.ilike(f"%{employee.name}%"))
        .order_by(Recording.classdate.desc())
        .limit(10)
        .all()
    )
    
    sessions = (
        db.query(SessionORM)
        .filter(SessionORM.title.ilike(f"%{employee.name}%"))
        .order_by(SessionORM.sessiondate.desc())
        .limit(10)
        .all()
    )
    
    return {
        "employee_info": employee,
        "placements": placements,
        "assigned_prep_candidates": prep_candidates,
        "assigned_marketing_candidates": marketing_candidates,
        "pending_tasks": tasks,
        "job_help_candidates": job_help_candidates,
        "classes": recordings,
        "sessions": sessions,
        "is_birthday": employee.dob.month == today.month and employee.dob.day == today.day if employee.dob else False
    }
