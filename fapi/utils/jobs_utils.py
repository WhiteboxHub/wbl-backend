# WBL_Backend\fapi\utils\jobs_utils.py
from fapi.db.models import EmployeeORM  # ensure imported
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
    """Get all job activity logs with job name, candidate name, employee name, and lastmod_user_name"""
    try:

        total_logs = db.query(JobActivityLogORM).count()


        from sqlalchemy.orm import aliased
        LastModUserEmployee = aliased(EmployeeORM)

        logs = (
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
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        # All logs are now returned, including those with missing job type references
        logger.info(f"Retrieved {len(logs)} job activity logs (total in database: {total_logs})")

        result = []
        for row in logs:
            log_dict = {
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
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_job_activity_log_by_id(db: Session, log_id: int) -> Dict[str, Any]:
    """Get single job activity log by ID"""
    try:
        from sqlalchemy.orm import aliased
        LastModUserEmployee = aliased(EmployeeORM)

        result = (
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
            .join(JobTypeORM, JobActivityLogORM.job_type_id == JobTypeORM.id)
            .outerjoin(CandidateORM, JobActivityLogORM.candidate_id == CandidateORM.id)
            .outerjoin(EmployeeORM, JobActivityLogORM.employee_id == EmployeeORM.id)
            .outerjoin(LastModUserEmployee, JobActivityLogORM.lastmod_user_id == LastModUserEmployee.id)
            .filter(JobActivityLogORM.id == log_id)
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404, detail="Job activity log not found")

        log_dict = {
            "id": result.id,
            "job_id": result.job_type_id,
            "candidate_id": result.candidate_id,
            "employee_id": result.employee_id,
            "activity_date": result.activity_date,
            "activity_count": result.activity_count,
            "notes": result.notes,
            "last_mod_date": result.lastmod_date_time,
            "lastmod_user_name": result.lastmod_user_name,
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
        from sqlalchemy.orm import aliased
        LastModUserEmployee = aliased(EmployeeORM)

        logs = (
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
            .filter(JobActivityLogORM.job_type_id == job_id)
            .filter(JobTypeORM.id.isnot(None))  # Ensure job type exists
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        result = []
        for row in logs:
            log_dict = {
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
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch job activity logs for job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_employee_id(db: Session, employee_id: int) -> List[Dict[str, Any]]:
    """Get all logs for a specific employee ID"""
    try:
        from sqlalchemy.orm import aliased
        LastModUserEmployee = aliased(EmployeeORM)

        logs = (
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
            .filter(JobActivityLogORM.employee_id == employee_id)
            .filter(JobTypeORM.id.isnot(None))  # Ensure job type exists
            .order_by(JobActivityLogORM.activity_date.desc())
            .all()
        )

        result = []
        for row in logs:
            log_dict = {
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
            result.append(log_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch job activity logs for employee: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def create_job_activity_log(db: Session, log_data: JobActivityLogCreate, current_user) -> Dict[str, Any]:
    """Create new job activity log with lastmod_user_id"""
    payload = log_data.dict()


    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == payload["job_id"]).first()
    if not job_type:
        raise HTTPException(
            status_code=404,
            detail="Please select a job."
        )


    if payload.get("employee_id") is not None:
        employee = db.query(EmployeeORM).filter(
            EmployeeORM.id == payload["employee_id"]).first()
        if not employee:
            raise HTTPException(
                status_code=404,
                detail="Please select an employee."
            )

    if payload.get("candidate_id") is not None:
        candidate = db.query(CandidateORM).filter(
            CandidateORM.id == payload["candidate_id"]).first()
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="Please select a candidate."
            )

    lastmod_employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname
    ).first()

    if lastmod_employee:
        payload["lastmod_user_id"] = lastmod_employee.id

    # Convert job_id to job_type_id for the ORM
    if "job_id" in payload:
        payload["job_type_id"] = payload["job_id"]
        del payload["job_id"]

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
    update_data: JobActivityLogUpdate,
    current_user
) -> Dict[str, Any]:
    """Update job activity log and update lastmod_user_id"""
    fields = update_data.dict(exclude_unset=True)

    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    log = db.query(JobActivityLogORM).filter(
        JobActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=404, detail="Job activity log not found")

    try:

        if "job_id" in fields:
            job_type = db.query(JobTypeORM).filter(
                JobTypeORM.id == fields["job_id"]).first()
            if not job_type:
                raise HTTPException(
                    status_code=404,
                    detail="Please select a job."
                )

        if "employee_id" in fields and fields["employee_id"] is not None:
            employee = db.query(EmployeeORM).filter(
                EmployeeORM.id == fields["employee_id"]).first()
            if not employee:
                raise HTTPException(
                    status_code=404,
                    detail="Please select an employee."
                )

        if "candidate_id" in fields and fields["candidate_id"] is not None:
            candidate = db.query(CandidateORM).filter(
                CandidateORM.id == fields["candidate_id"]).first()
            if not candidate:
                raise HTTPException(
                    status_code=404,
                    detail="Please select a candidate."
                )

        lastmod_employee = db.query(EmployeeORM).filter(
            EmployeeORM.email == current_user.uname
        ).first()

        if lastmod_employee:
            log.lastmod_user_id = lastmod_employee.id

        # Convert job_id to job_type_id for the ORM (same as create function)
        if "job_id" in fields:
            fields["job_type_id"] = fields["job_id"]
            del fields["job_id"]

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
        return {"message": f"Job activity log deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


def get_all_job_types(db: Session):
    """Get all job types with job owner name and lastmod user name"""
    try:
        from sqlalchemy.orm import aliased
        JobOwnerEmployee = aliased(EmployeeORM)
        LastModUserEmployee = aliased(EmployeeORM)

        rows = (
            db.query(
                JobTypeORM.id,
                JobTypeORM.unique_id,
                JobTypeORM.name,
                JobTypeORM.job_owner,
                JobTypeORM.description,
                JobTypeORM.notes,
                JobTypeORM.lastmod_date_time,
                JobOwnerEmployee.name.label("job_owner_name"),
                LastModUserEmployee.name.label("lastmod_user_name")
            )
            .outerjoin(JobOwnerEmployee, JobOwnerEmployee.id == JobTypeORM.job_owner)
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
                "job_owner": row.job_owner,
                "job_owner_name": row.job_owner_name,
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


def get_job_type_by_id(db: Session, job_type_id: int) -> JobTypeORM:
    """Get single job type by ID"""
    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")
    return job_type


def create_job_type(db: Session, job_type_data: JobTypeCreate, current_user):
    """Create new job type with employee.id stored in lastmod_user_id"""
    employee = db.query(EmployeeORM).filter(
        EmployeeORM.email == current_user.uname
    ).first()

    try:
        job_type_dict = job_type_data.dict()

        if "job_owner_id" in job_type_dict:
            job_type_dict["job_owner"] = job_type_dict.pop("job_owner_id")

        if job_type_dict.get("job_owner") is not None:
            job_owner_employee = db.query(EmployeeORM).filter(
                EmployeeORM.id == job_type_dict["job_owner"]
            ).first()
            if not job_owner_employee:
                raise HTTPException(
                    status_code=404,
                    detail=f"Job owner employee with ID {job_type_dict['job_owner']} not found"
                )

        if employee:
            job_type_dict["lastmod_user_id"] = employee.id
        else:
            job_type_dict["lastmod_user_id"] = None

        new_job_type = JobTypeORM(**job_type_dict)
        db.add(new_job_type)
        db.commit()
        db.refresh(new_job_type)

        from sqlalchemy.orm import aliased
        JobOwnerEmployee = aliased(EmployeeORM)
        LastModUserEmployee = aliased(EmployeeORM)

        result = (
            db.query(
                JobTypeORM.id,
                JobTypeORM.unique_id,
                JobTypeORM.name,
                JobTypeORM.job_owner.label("job_owner_id"),  # Explicitly label as job_owner_id
                JobTypeORM.description,
                JobTypeORM.notes,
                JobTypeORM.lastmod_date_time,
                JobOwnerEmployee.name.label("job_owner_name"),
                LastModUserEmployee.name.label("lastmod_user_name")
            )
            .outerjoin(JobOwnerEmployee, JobOwnerEmployee.id == JobTypeORM.job_owner)
            .outerjoin(LastModUserEmployee, LastModUserEmployee.id == JobTypeORM.lastmod_user_id)
            .filter(JobTypeORM.id == new_job_type.id)
            .first()
        )

        # Debug: Print the result object to understand its structure
        logger.debug(f"Result object: {result}")
        logger.debug(f"Result job_owner_id type: {type(result.job_owner_id)}")
        logger.debug(f"Result job_owner_id value: {result.job_owner_id}")

        return {
            "id": result.id,
            "unique_id": result.unique_id,
            "name": result.name,
            "job_owner": result.job_owner_id,  # Use the explicitly labeled field
            "job_owner_name": result.job_owner_name,
            "description": result.description,
            "notes": result.notes,
            "lastmod_date_time": result.lastmod_date_time,
            "lastmod_user_name": result.lastmod_user_name
        }

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
    logger.info(f"Job type update fields received: {fields}")

    if "job_owner_id" in fields:
        fields["job_owner"] = fields.pop("job_owner_id")
    elif "job_owner" in fields:
        pass

    job_type = db.query(JobTypeORM).filter(
        JobTypeORM.id == job_type_id).first()
    if not job_type:
        raise HTTPException(status_code=404, detail="Job type not found")

    try:
        if "job_owner" in fields:
            if fields["job_owner"] is not None:
                job_owner_employee = db.query(EmployeeORM).filter(
                    EmployeeORM.id == fields["job_owner"]
                ).first()
                if not job_owner_employee:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Job owner employee with ID {fields['job_owner']} not found"
                    )

        if employee:
            job_type.lastmod_user_id = employee.id
        else:
            job_type.lastmod_user_id = None

        for key, value in fields.items():
            setattr(job_type, key, value)

        db.commit()
        db.refresh(job_type)

        from sqlalchemy.orm import aliased
        JobOwnerEmployee = aliased(EmployeeORM)
        LastModUserEmployee = aliased(EmployeeORM)

        result = (
            db.query(
                JobTypeORM.id,
                JobTypeORM.unique_id,
                JobTypeORM.name,
                JobTypeORM.job_owner.label("job_owner_id"),  # Explicitly label as job_owner_id
                JobTypeORM.description,
                JobTypeORM.notes,
                JobTypeORM.lastmod_date_time,
                JobOwnerEmployee.name.label("job_owner_name"),
                LastModUserEmployee.name.label("lastmod_user_name")
            )
            .outerjoin(JobOwnerEmployee, JobOwnerEmployee.id == JobTypeORM.job_owner)
            .outerjoin(LastModUserEmployee, LastModUserEmployee.id == JobTypeORM.lastmod_user_id)
            .filter(JobTypeORM.id == job_type.id)
            .first()
        )

        # Debug: Print the result object to understand its structure
        logger.debug(f"Update result object: {result}")
        logger.debug(f"Update result job_owner_id type: {type(result.job_owner_id)}")
        logger.debug(f"Update result job_owner_id value: {result.job_owner_id}")
        logger.debug(f"Update result job_owner_name type: {type(result.job_owner_name)}")
        logger.debug(f"Update result job_owner_name value: {result.job_owner_name}")

        return {
            "id": result.id,
            "unique_id": result.unique_id,
            "name": result.name,
            "job_owner": result.job_owner_id,  # Use the explicitly labeled field
            "job_owner_name": result.job_owner_name,
            "description": result.description,
            "notes": result.notes,
            "lastmod_date_time": result.lastmod_date_time,
            "lastmod_user_name": result.lastmod_user_name
        }
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
        logger.error(f"Failed to delete job type: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
