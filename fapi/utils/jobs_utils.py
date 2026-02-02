# WBL_Backend\fapi\utils\jobs_utils.py
from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging
from sqlalchemy import func, and_
from sqlalchemy.orm import Session, aliased
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from fapi.db.models import JobActivityLogORM, JobTypeORM, CandidateORM, EmployeeORM
from fapi.db.schemas import JobActivityLogCreate, JobActivityLogUpdate, JobTypeCreate, JobTypeUpdate, JobActivityLogOut, JobTypeOut

logger = logging.getLogger(__name__)


def _build_job_activity_log_query(db: Session, additional_filters=None):
    """Helper function to build the common job activity log query with joins"""
    LastModUserEmployee = aliased(EmployeeORM)

    query = (
        db.query(
            JobActivityLogORM.id,
            JobActivityLogORM.job_type_id,
            JobActivityLogORM.candidate_id,
            JobActivityLogORM.employee_id,
            JobActivityLogORM.activity_date,
            JobActivityLogORM.activity_count,
            JobActivityLogORM.notes,
            JobActivityLogORM.lastmod_date_time,
            JobTypeORM.name.label("job_name"),
            CandidateORM.full_name.label("candidate_name"),
            EmployeeORM.name.label("employee_name"),
            LastModUserEmployee.name.label("lastmod_user_name")
        )
        .outerjoin(JobTypeORM, JobActivityLogORM.job_type_id == JobTypeORM.id)
        .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
        .outerjoin(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
        .outerjoin(LastModUserEmployee, JobActivityLogORM.lastmod_user_id == LastModUserEmployee.id)
    )

    if additional_filters:
        query = query.filter(additional_filters)

    return query


def _format_job_activity_log_row(row) -> Dict[str, Any]:
    """Helper function to format a job activity log row into the expected dict format"""
    return {
        "id": row.id,
        "job_id": row.job_type_id,
        "candidate_id": row.candidate_id,
        "employee_id": row.employee_id,
        "activity_date": row.activity_date,
        "activity_count": row.activity_count,
        "notes": row.notes,
        "last_mod_date": row.lastmod_date_time,
        "lastmod_user_name": row.lastmod_user_name,
        "job_name": row.job_name,
        "candidate_name": row.candidate_name,
        "employee_name": row.employee_name
    }


def _validate_job_activity_log_references(db: Session, data: Dict[str, Any]) -> None:
    """Validate that referenced job, employee, and candidate exist"""
    if "job_id" in data:
        job_type = db.query(JobTypeORM).filter(JobTypeORM.id == data["job_id"]).first()
        if not job_type:
            raise HTTPException(status_code=404, detail="Please select a job.")

    if data.get("employee_id") is not None:
        employee = db.query(EmployeeORM).filter(EmployeeORM.id == data["employee_id"]).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Please select an employee.")

    if data.get("candidate_id") is not None:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == data["candidate_id"]).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Please select a candidate.")


def get_all_job_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all job activity logs with job name, candidate name, employee name, and lastmod_user_name"""
    try:
        logs = _build_job_activity_log_query(db).order_by(JobActivityLogORM.activity_date.desc()).all()
        return [_format_job_activity_log_row(row) for row in logs]
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_job_activity_log_by_id(db: Session, log_id: int) -> Dict[str, Any]:
    """Get single job activity log by ID"""
    try:
        result = _build_job_activity_log_query(db, JobActivityLogORM.id == log_id).first()
        if not result:
            raise HTTPException(status_code=404, detail="Job activity log not found")
        return _format_job_activity_log_row(result)
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity log: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_job_id(db: Session, job_id: int) -> List[Dict[str, Any]]:
    """Get all logs for a specific job ID"""
    try:
        logs = _build_job_activity_log_query(db, JobActivityLogORM.job_type_id == job_id).order_by(JobActivityLogORM.activity_date.desc()).all()
        return [_format_job_activity_log_row(row) for row in logs]
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs for job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_employee_id(db: Session, employee_id: int) -> List[Dict[str, Any]]:
    """Get all logs for a specific employee ID"""
    try:
        logs = _build_job_activity_log_query(db, JobActivityLogORM.employee_id == employee_id).order_by(JobActivityLogORM.activity_date.desc()).all()
        return [_format_job_activity_log_row(row) for row in logs]
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs for employee: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def create_job_activity_log(db: Session, log_data: JobActivityLogCreate, current_user) -> Dict[str, Any]:
    """Create new job activity log with lastmod_user_id"""
    payload = log_data.dict()

    # Validate references
    _validate_job_activity_log_references(db, payload)

    # Set lastmod user
    lastmod_employee = db.query(EmployeeORM).filter(EmployeeORM.email == current_user.uname).first()
    if lastmod_employee:
        payload["lastmod_user_id"] = lastmod_employee.id

    # Convert job_id to job_type_id for the ORM
    if "job_id" in payload:
        payload["job_type_id"] = payload.pop("job_id")

    new_log = JobActivityLogORM(**payload)
    db.add(new_log)

    try:
        db.commit()
        db.refresh(new_log)
        return get_job_activity_log_by_id(db, new_log.id)
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
    update_data: JobActivityLogUpdate,
    current_user
) -> Dict[str, Any]:
    """Update job activity log and update lastmod_user_id"""
    fields = update_data.dict(exclude_unset=True)

    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    log = db.query(JobActivityLogORM).filter(JobActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Job activity log not found")

    try:
        # Validate references for fields being updated
        _validate_job_activity_log_references(db, fields)

        # Set lastmod user
        lastmod_employee = db.query(EmployeeORM).filter(EmployeeORM.email == current_user.uname).first()
        if lastmod_employee:
            log.lastmod_user_id = lastmod_employee.id

        # Convert job_id to job_type_id for the ORM
        if "job_id" in fields:
            fields["job_type_id"] = fields.pop("job_id")

        # Update fields
        for key, value in fields.items():
            setattr(log, key, value)

        db.commit()
        db.refresh(log)
        return get_job_activity_log_by_id(db, log_id)
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
        return {"message": f"Job activity log deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


def insert_job_activity_logs_bulk(
    db: Session, 
    logs: List[JobActivityLogCreate], 
    current_user
) -> Dict[str, Any]:
    """Bulk insert job activity logs"""
    inserted = 0
    failed = 0
    failed_logs = []

    # Get employee ID for lastmod_user_id
    lastmod_user_id = None
    lastmod_employee = db.query(EmployeeORM).filter(EmployeeORM.email == current_user.uname).first()
    if lastmod_employee:
        lastmod_user_id = lastmod_employee.id

    for log_data in logs:
        try:
            payload = log_data.dict()
            
            # Basic validation
            _validate_job_activity_log_references(db, payload)
            
            # Set lastmod
            payload["lastmod_user_id"] = lastmod_user_id
            
            # Convert job_id to job_type_id
            if "job_id" in payload:
                payload["job_type_id"] = payload.pop("job_id")
            
            new_log = JobActivityLogORM(**payload)
            db.add(new_log)
            inserted += 1
            
            # Flush every 50 records
            if inserted % 50 == 0:
                db.flush()
                
        except Exception as e:
            failed += 1
            failed_logs.append({
                "candidate_id": log_data.candidate_id,
                "reason": str(e)
            })
            logger.error(f"Failed to insert activity log for candidate {log_data.candidate_id}: {str(e)}")

    try:
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk commit failed: {str(e)}")

    return {
        "inserted": inserted,
        "failed": failed,
        "total": len(logs),
        "failed_logs": failed_logs
    }


def get_all_job_types(db: Session):
    try:
        from sqlalchemy.orm import aliased
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
            .order_by(JobTypeORM.id)
            .all()
        )

        result = []
        for row in rows:
            item = {
                "id": row.id,
                "unique_id": row.unique_id,
                "name": row.name,
                "job_owner_1": row.job_owner_1,
                "job_owner_2": row.job_owner_2,
                "job_owner_3": row.job_owner_3,
                "job_owner_1_name": row.job_owner_1_name,
                "job_owner_2_name": row.job_owner_2_name,
                "job_owner_3_name": row.job_owner_3_name,
                "category": row.category,
                "description": row.description,
                "notes": row.notes,
                "lastmod_date_time": row.lastmod_date_time,
                "lastmod_user_name": row.lastmod_user_name
            }
            result.append(item)

        return result

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job types: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_job_type_by_id(db: Session, job_type_id: int):
    """Get single job type by ID with owners as employee names"""
    from sqlalchemy.orm import aliased
    Owner1 = aliased(EmployeeORM)
    Owner2 = aliased(EmployeeORM)
    Owner3 = aliased(EmployeeORM)
    LastModUserEmployee = aliased(EmployeeORM)
    
    row = (
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
        .filter(JobTypeORM.id == job_type_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Job type not found")
    
    return {
        "id": row.id,
        "unique_id": row.unique_id,
        "name": row.name,
        "job_owner_1": row.job_owner_1,
        "job_owner_2": row.job_owner_2,
        "job_owner_3": row.job_owner_3,
        "job_owner_1_name": row.job_owner_1_name,
        "job_owner_2_name": row.job_owner_2_name,
        "job_owner_3_name": row.job_owner_3_name,
        "category": row.category,
        "description": row.description,
        "notes": row.notes,
        "lastmod_date_time": row.lastmod_date_time,
        "lastmod_user_name": row.lastmod_user_name
    }


def create_job_type(db: Session, job_type_data: JobTypeCreate, current_user):
    """Create new job type with employee.id stored in lastmod_user_id"""
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname
    ).first()

    try:
        job_type_dict = job_type_data.dict()

        # Check for existing job type by unique_id
        existing_job_type = db.query(JobTypeORM).filter(JobTypeORM.unique_id == job_type_dict["unique_id"]).first()
        if existing_job_type:
            raise HTTPException(status_code=400, detail="job type with this unique_id already exists")

        # Set lastmod_user_id only if employee record exists
        if employee:
            job_type_dict["lastmod_user_id"] = employee.id
        else:
            job_type_dict["lastmod_user_id"] = None

        new_job_type = JobTypeORM(**job_type_dict)
        db.add(new_job_type)
        db.commit()
        db.refresh(new_job_type)

        return get_job_type_by_id(db, new_job_type.id)

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error in create_job_type: {str(e)}")
        raise HTTPException(
            status_code=400, detail="Foreign key constraint violation or job type already exists")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Create job type failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_job_type(db: Session, job_type_id: int, update_data: JobTypeUpdate, current_user):
    """Update job type and update lastmod_user_id with employee.id"""

    # Find employee record
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname
    ).first()

    fields = update_data.dict(exclude_unset=True)

    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")

    try:
        # Set lastmod_user_id only if employee record exists
        if employee:
            job_type.lastmod_user_id = employee.id
        else:
            job_type.lastmod_user_id = None

        for key, value in fields.items():
            setattr(job_type, key, value)

        db.commit()
        db.refresh(job_type)

        return get_job_type_by_id(db, job_type_id)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Update job type failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_job_type(db: Session, job_type_id: int) -> Dict[str, str]:
    """Delete job type"""
    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")
    logs_count = db.query(JobActivityLogORM).filter(
        JobActivityLogORM.job_type_id == job_type_id).count()
    if logs_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job type. It is being used in {logs_count} job activity log(s)"
        )

    try:
        db.delete(job_type)
        db.commit()
        return {"message": f"Job type deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


