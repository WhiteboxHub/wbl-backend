import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import Session
from fapi.db.models import ApplicationReportORM, AuthUserORM

logger = logging.getLogger(__name__)

def get_extension_global_summary(db: Session) -> Dict[str, Any]:
    """Calculate aggregate metrics for Extension usage overview cards."""
    since_7d = datetime.utcnow() - timedelta(days=7)
    
    # 1. Total unique users (authenticated via user_id, or fallback to candidate_name)
    total_users = db.query(
        func.count(func.distinct(func.coalesce(ApplicationReportORM.user_id, ApplicationReportORM.candidate_name)))
    ).scalar() or 0
    
    # 2. Active users (last 7 days)
    active_users_7d = db.query(
        func.count(func.distinct(func.coalesce(ApplicationReportORM.user_id, ApplicationReportORM.candidate_name)))
    ).filter(ApplicationReportORM.submitted_at >= since_7d).scalar() or 0
    
    # 3. Total applications submitted
    total_apps = db.query(func.count(ApplicationReportORM.id)).scalar() or 0
    
    # 4. Sum field counts
    total_fields = db.query(func.sum(ApplicationReportORM.total_fields)).scalar() or 0
    total_autofill = db.query(func.sum(ApplicationReportORM.autofill_fields)).scalar() or 0
    total_llm = db.query(func.sum(ApplicationReportORM.llm_fields)).scalar() or 0
    total_human = db.query(func.sum(ApplicationReportORM.human_fields)).scalar() or 0
    
    # 5. Average Automation Rate (%)
    avg_automation = db.query(func.avg(ApplicationReportORM.automation_rate)).scalar() or 0.0
    
    return {
        "total_users": int(total_users),
        "active_users_7d": int(active_users_7d),
        "total_applications": int(total_apps),
        "total_fields": int(total_fields or 0),
        "autofill_fields": int(total_autofill or 0),
        "llm_fields": int(total_llm or 0),
        "human_fields": int(total_human or 0),
        "avg_automation_rate": round(float(avg_automation), 2)
    }

def get_paginated_extension_users(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    search_query: Optional[str] = None
) -> Dict[str, Any]:
    """Aggregated stats grouped by user/candidate for AG Grid dashboard table."""
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    
    # Group key identifier: resolved username/email, or fallback candidate name
    group_key = func.coalesce(AuthUserORM.uname, ApplicationReportORM.candidate_name)
    
    base_query = db.query(
        group_key.label("user_id"),
        func.count(ApplicationReportORM.id).label("total_applications"),
        func.sum(ApplicationReportORM.total_fields).label("total_fields"),
        func.sum(ApplicationReportORM.autofill_fields).label("autofill_fields"),
        func.sum(ApplicationReportORM.llm_fields).label("llm_fields"),
        func.sum(ApplicationReportORM.human_fields).label("human_fields"),
        func.avg(ApplicationReportORM.automation_rate).label("avg_automation_rate"),
        func.max(ApplicationReportORM.submitted_at).label("last_activity")
    ).outerjoin(
        AuthUserORM, ApplicationReportORM.user_id == AuthUserORM.id
    ).group_by(group_key)
    
    if search_query:
        search_query = f"%{search_query.strip()}%"
        base_query = base_query.filter(
            or_(
                AuthUserORM.uname.ilike(search_query),
                ApplicationReportORM.candidate_name.ilike(search_query)
            )
        )
        
    total_records = base_query.count()
    
    results = base_query.order_by(desc(func.max(ApplicationReportORM.submitted_at))).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    users = []
    for r in results:
        # Formulate log history preview (e.g. "Greenhouse, Workday")
        users.append({
            "user_id": r[0] or "Anonymous",
            "total_applications": int(r[1] or 0),
            "total_fields": int(r[2] or 0),
            "autofill_fields": int(r[3] or 0),
            "llm_fields": int(r[4] or 0),
            "human_fields": int(r[5] or 0),
            "avg_automation_rate": round(float(r[6] or 0.0), 2),
            "last_activity": r[7].isoformat() if r[7] else None
        })
        
    return {
        "total": total_records,
        "page": page,
        "page_size": page_size,
        "users": users
    }

def get_user_extension_logs(db: Session, user_identity: str) -> List[Dict[str, Any]]:
    """Return all detailed application records for a specific username or candidate name."""
    # Find user_id from uname first, if matches
    user = db.query(AuthUserORM).filter(AuthUserORM.uname == user_identity).first()
    
    query = db.query(ApplicationReportORM)
    if user:
        query = query.filter(
            or_(
                ApplicationReportORM.user_id == user.id,
                ApplicationReportORM.candidate_name == user_identity
            )
        )
    else:
        query = query.filter(ApplicationReportORM.candidate_name == user_identity)
        
    records = query.order_by(desc(ApplicationReportORM.submitted_at)).limit(200).all()
    
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "ats_platform": r.ats_platform,
            "total_fields": r.total_fields,
            "autofill_fields": r.autofill_fields,
            "llm_fields": r.llm_fields,
            "human_fields": r.human_fields,
            "automation_rate": float(r.automation_rate),
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None
        }
        for r in records
    ]

def delete_user_extension_reports(db: Session, user_identity: str) -> int:
    """Delete all reports for a specific user to clean up logs."""
    user = db.query(AuthUserORM).filter(AuthUserORM.uname == user_identity).first()
    
    query = db.query(ApplicationReportORM)
    if user:
        # Delete by user_id or by exact username matching candidate_name
        deleted = query.filter(
            or_(
                ApplicationReportORM.user_id == user.id,
                ApplicationReportORM.candidate_name == user_identity
            )
        ).delete(synchronize_session=False)
    else:
        deleted = query.filter(ApplicationReportORM.candidate_name == user_identity).delete(synchronize_session=False)
        
    db.commit()
    return deleted
