# WBL_Backend\fapi\utils\job_activity_log_utils.py
from fapi.db.models import EmployeeORM

from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from fapi.db.models import JobActivityLogORM, JobTypeORM, CandidateORM, EmployeeORM
from fapi.db.schemas import JobActivityLogCreate, JobActivityLogUpdate, JobTypeCreate, JobTypeUpdate

logger = logging.getLogger(__name__)


def get_all_job_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all job activity logs with job name, candidate name, and employee name"""
    try:
        # Get total count of logs (including potentially orphaned ones)
        total_logs = db.query(JobActivityLogORM).count()

        logs = (
            db.query(
                JobActivityLogORM.id,
                JobActivityLogORM.job_id,
                JobActivityLogORM.candidate_id,
                JobActivityLogORM.employee_id,
                JobActivityLogORM.activity_date,
                JobActivityLogORM.activity_count,
                JobActivityLogORM.json_downloaded,
                JobActivityLogORM.sql_downloaded,
                JobActivityLogORM.last_mod_date,
                JobTypeORM.job_name.label("job_name"),
                CandidateORM.full_name.label("candidate_name"),
                EmployeeORM.name.label("employee_name")
            )
            .outerjoin(JobTypeORM, JobActivityLogORM.job_id == JobTypeORM.id)
            .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
            .outerjoin(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
            .filter(JobTypeORM.id.isnot(None))  # Only include logs with valid job types
            .filter(EmployeeORM.id.isnot(None))  # Only include logs with valid employees
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        valid_logs_count = len(logs)
        if total_logs > valid_logs_count:
            logger.warning(f"Filtered out {total_logs - valid_logs_count} job activity logs with missing foreign key references")

        result = []
        for row in logs:
            log_dict = {
                "id": row.id,
                "job_id": row.job_id,
                "candidate_id": row.candidate_id,
                "employee_id": row.employee_id,
                "activity_date": row.activity_date,
                "activity_count": row.activity_count,
                "json_downloaded": row.json_downloaded,
                "sql_downloaded": row.sql_downloaded,
                "last_mod_date": row.last_mod_date,
                "job_name": row.job_name,
                "candidate_name": row.candidate_name,
                "employee_name": row.employee_name
            }
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_job_activity_log_by_id(db: Session, log_id: int) -> Dict[str, Any]:
    """Get single job activity log by ID"""
    try:
        result = (
            db.query(
                JobActivityLogORM.id,
                JobActivityLogORM.job_id,
                JobActivityLogORM.candidate_id,
                JobActivityLogORM.employee_id,
                JobActivityLogORM.activity_date,
                JobActivityLogORM.activity_count,
                JobActivityLogORM.json_downloaded,
                JobActivityLogORM.sql_downloaded,
                JobActivityLogORM.last_mod_date,
                JobTypeORM.job_name.label("job_name"),
                CandidateORM.full_name.label("candidate_name"),
                EmployeeORM.name.label("employee_name")
            )
            .join(JobTypeORM, JobActivityLogORM.job_id == JobTypeORM.id)
            .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
            .join(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
            .filter(JobActivityLogORM.id == log_id)
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404, detail="Job activity log not found")

        log_dict = {
            "id": result.id,
            "job_id": result.job_id,
            "candidate_id": result.candidate_id,
            "employee_id": result.employee_id,
            "activity_date": result.activity_date,
            "activity_count": result.activity_count,
            "json_downloaded": result.json_downloaded,
            "sql_downloaded": result.sql_downloaded,
            "last_mod_date": result.last_mod_date,
            "job_name": result.job_name,
            "candidate_name": result.candidate_name,
            "employee_name": result.employee_name
        }

        return log_dict
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity log: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_job_id(db: Session, job_id: int) -> List[Dict[str, Any]]:
    """Get all logs for a specific job ID"""
    try:
        logs = (
            db.query(
                JobActivityLogORM.id,
                JobActivityLogORM.job_id,
                JobActivityLogORM.candidate_id,
                JobActivityLogORM.employee_id,
                JobActivityLogORM.activity_date,
                JobActivityLogORM.activity_count,
                JobActivityLogORM.json_downloaded,
                JobActivityLogORM.sql_downloaded,
                JobActivityLogORM.last_mod_date,
                JobTypeORM.job_name.label("job_name"),
                CandidateORM.full_name.label("candidate_name"),
                EmployeeORM.name.label("employee_name")
            )
            .outerjoin(JobTypeORM, JobActivityLogORM.job_id == JobTypeORM.id)
            .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
            .outerjoin(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
            .filter(JobActivityLogORM.job_id == job_id)
            .filter(JobTypeORM.id.isnot(None))  # Ensure job type exists
            .filter(EmployeeORM.id.isnot(None))  # Ensure employee exists
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        result = []
        for row in logs:
            log_dict = {
                "id": row.id,
                "job_id": row.job_id,
                "candidate_id": row.candidate_id,
                "employee_id": row.employee_id,
                "activity_date": row.activity_date,
                "activity_count": row.activity_count,
                "json_downloaded": row.json_downloaded,
                "sql_downloaded": row.sql_downloaded,
                "last_mod_date": row.last_mod_date,
                "job_name": row.job_name,
                "candidate_name": row.candidate_name,
                "employee_name": row.employee_name
            }
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs for job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_employee_id(db: Session, employee_id: int) -> List[Dict[str, Any]]:
    """Get all logs for a specific employee ID"""
    try:
        logs = (
            db.query(
                JobActivityLogORM.id,
                JobActivityLogORM.job_id,
                JobActivityLogORM.candidate_id,
                JobActivityLogORM.employee_id,
                JobActivityLogORM.activity_date,
                JobActivityLogORM.activity_count,
                JobActivityLogORM.json_downloaded,
                JobActivityLogORM.sql_downloaded,
                JobActivityLogORM.last_mod_date,
                JobTypeORM.job_name.label("job_name"),
                CandidateORM.full_name.label("candidate_name"),
                EmployeeORM.name.label("employee_name")
            )
            .outerjoin(JobTypeORM, JobActivityLogORM.job_id == JobTypeORM.id)
            .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
            .outerjoin(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
            .filter(JobActivityLogORM.employee_id == employee_id)
            .filter(JobTypeORM.id.isnot(None))  # Ensure job type exists
            .filter(EmployeeORM.id.isnot(None))  # Ensure employee exists
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        result = []
        for row in logs:
            log_dict = {
                "id": row.id,
                "job_id": row.job_id,
                "candidate_id": row.candidate_id,
                "employee_id": row.employee_id,
                "activity_date": row.activity_date,
                "activity_count": row.activity_count,
                "json_downloaded": row.json_downloaded,
                "sql_downloaded": row.sql_downloaded,
                "last_mod_date": row.last_mod_date,
                "job_name": row.job_name,
                "candidate_name": row.candidate_name,
                "employee_name": row.employee_name
            }
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch job activity logs for employee: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def create_job_activity_log(db: Session, log_data: JobActivityLogCreate) -> Dict[str, Any]:
    """Create new job activity log"""
    payload = log_data.dict()

    # Verify job_id exists
    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == payload["job_id"]).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")

    # Verify employee_id exists
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.id == payload["employee_id"]).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Verify candidate_id exists if provided
    if payload.get("candidate_id"):
        candidate = db.query(CandidateORM).filter(
            CandidateORM.id == payload["candidate_id"]).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

    new_log = JobActivityLogORM(**payload)
    db.add(new_log)

    try:
        db.commit()
        db.refresh(new_log)

        response_data = get_job_activity_log_by_id(db, new_log.id)
        return response_data
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {str(e)}")
        raise HTTPException(status_code=400, detail="Constraint violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Create failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_job_activity_log(
    db: Session,
    log_id: int,
    update_data: JobActivityLogUpdate
) -> Dict[str, Any]:
    """Update job activity log"""
    fields = update_data.dict(exclude_unset=True)

    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    log = db.query(JobActivityLogORM).filter(
        JobActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=404, detail="Job activity log not found")

    try:
        # Verify foreign keys if they are being updated
        if "job_id" in fields:
            job_type = db.query(JobTypeORM).filter(
                JobTypeORM.id == fields["job_id"]).first()
            if not job_type:
                raise HTTPException(
                    status_code=404, detail="Job type not found")

        if "employee_id" in fields:
            employee = db.query(EmployeeORM).filter(
                EmployeeORM.id == fields["employee_id"]).first()
            if not employee:
                raise HTTPException(
                    status_code=404, detail="Employee not found")

        if "candidate_id" in fields and fields["candidate_id"]:
            candidate = db.query(CandidateORM).filter(
                CandidateORM.id == fields["candidate_id"]).first()
            if not candidate:
                raise HTTPException(
                    status_code=404, detail="Candidate not found")

        for key, value in fields.items():
            setattr(log, key, value)

        db.commit()
        db.refresh(log)

        
        response_data = get_job_activity_log_by_id(db, log_id)
        return response_data
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_job_activity_log(db: Session, log_id: int) -> Dict[str, str]:
    """Delete job activity log"""
    log = db.query(JobActivityLogORM).filter(
        JobActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=404, detail="Job activity log not found")

    try:
        db.delete(log)
        db.commit()
        return {"message": f"Job activity log with ID {log_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

def get_all_job_types(db: Session):
    """Get all job types with employee name (lmuid_name)"""
    try:
        rows = (
            db.query(
                JobTypeORM,
                EmployeeORM.name.label("lmuid_name")
            )
            .outerjoin(EmployeeORM, EmployeeORM.id == JobTypeORM.lmuid)
            .order_by(JobTypeORM.id)
            .all()
        )

        result = []
        for job_type, lmuid_name in rows:
            item = job_type.__dict__.copy()
            item.pop("_sa_instance_state", None)
            item["lmuid_name"] = lmuid_name
            result.append(item)

        return result

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job types: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

def get_job_type_by_id(db: Session, job_type_id: int) -> JobTypeORM:
    """Get single job type by ID"""
    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")
    return job_type


from fapi.db.models import EmployeeORM  # ensure imported

def create_job_type(db: Session, job_type_data: JobTypeCreate, current_user):
    """Create new job type with employee.id stored in lmuid"""
    print("Current user uname:", current_user.uname)

    # Find employee in employee table
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname

    ).first()
    print("Matched employee:", employee)


    if not employee:
        raise HTTPException(
            status_code=400,
            detail=f"Employee not found for logged-in user: {current_user.fullname}"
        )

    try:
        
        job_type_dict = job_type_data.dict()
        job_type_dict["lmuid"] = employee.id
        new_job_type = JobTypeORM(**job_type_dict)
        db.add(new_job_type)
        db.commit()
        db.refresh(new_job_type)

        return new_job_type

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Foreign key error / job type exists")

def update_job_type(db: Session, job_type_id: int, update_data: JobTypeUpdate, current_user):
    """Update job type and update lmuid with employee.id"""

    # Find employee record
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname
    ).first()

    if not employee:
        raise HTTPException(
            status_code=400,
            detail=f"Employee not found for logged-in user: {current_user.fullname}"
        )

    fields = update_data.dict(exclude_unset=True)

    job_type = db.query(JobTypeORM).filter(JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")
    job_type.lmuid = employee.id

    for key, value in fields.items():
        setattr(job_type, key, value)

    db.commit()
    db.refresh(job_type)
    return job_type


def delete_job_type(db: Session, job_type_id: int) -> Dict[str, str]:
    """Delete job type"""
    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")
    logs_count = db.query(JobActivityLogORM).filter(
        JobActivityLogORM.job_id == job_type_id).count()
    if logs_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job type. It is being used in {logs_count} job activity log(s)"
        )

    try:
        db.delete(job_type)
        db.commit()
        return {"message": f"Job type with ID {job_type_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to delete job type: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
