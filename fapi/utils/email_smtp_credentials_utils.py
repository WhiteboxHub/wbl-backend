from sqlalchemy.orm import Session
from sqlalchemy import desc
from fapi.db.models import EmailSMTPCredentialsORM
from fapi.db.schemas import EmailSMTPCredentialsCreate, EmailSMTPCredentialsUpdate
from typing import List, Optional
from datetime import datetime
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

@cache_result(ttl=300, prefix="email_smtp_credentials")
def get_email_smtp_credential_by_id(db: Session, credential_id: int):
    return db.query(EmailSMTPCredentialsORM).filter(EmailSMTPCredentialsORM.id == credential_id).first()

@cache_result(ttl=300, prefix="email_smtp_credentials")
def get_email_smtp_credential_by_email(db: Session, email: str):
    return db.query(EmailSMTPCredentialsORM).filter(EmailSMTPCredentialsORM.email == email).first()

@cache_result(ttl=300, prefix="email_smtp_credentials")
def get_email_smtp_credentials(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    search: str = None
):
    query = db.query(EmailSMTPCredentialsORM)
    if search:
        query = query.filter(EmailSMTPCredentialsORM.name.ilike(f"%{search}%"))
    return query.order_by(desc(EmailSMTPCredentialsORM.created_at)).offset(skip).limit(limit).all()

def create_email_smtp_credential(db: Session, credential_in: EmailSMTPCredentialsCreate):
    invalidate_cache("email_smtp_credentials")
    # B2 fix: also bust the workflow execution bundle cache so the scheduler
    # immediately picks up the new credential instead of serving a stale snapshot.
    invalidate_cache("workflows")
    db_credential = EmailSMTPCredentialsORM(
        **credential_in.model_dump(exclude_unset=True)
    )
    db.add(db_credential)
    db.commit()
    db.refresh(db_credential)
    return db_credential

def update_email_smtp_credential(
    db: Session, 
    credential_id: int, 
    credential_in: EmailSMTPCredentialsUpdate
):
    invalidate_cache("email_smtp_credentials")
    # B2 fix: bust execution bundle cache so App Password changes take effect immediately.
    invalidate_cache("workflows")
    db_credential = get_email_smtp_credential_by_id(db, credential_id)
    if not db_credential:
        return None
    
    update_data = credential_in.model_dump(exclude_unset=True)
    # These columns are NOT NULL in the DB — skip if None to preserve existing value
    NOT_NULLABLE = {
        "name", "email", "password", "daily_limit", "is_active", 
        "current_day_sent", "last_reset_date", "is_warming_up", "is_healthy"
    }
    for field, value in update_data.items():
        if field in NOT_NULLABLE and value is None:
            continue
        setattr(db_credential, field, value)
    
    db.commit()
    db.refresh(db_credential)
    return db_credential

def delete_email_smtp_credential(db: Session, credential_id: int):
    invalidate_cache("email_smtp_credentials")
    # B2 fix: bust execution bundle cache on deletion too.
    invalidate_cache("workflows")
    db_credential = get_email_smtp_credential_by_id(db, credential_id)
    if not db_credential:
        return None
    
    db.delete(db_credential)
    db.commit()
    return db_credential

def increment_credential_sent(db: Session, credential_id: int) -> dict:
    """
    B4: Atomically increment current_day_sent for an SMTP credential.
    If last_reset_date < today, the counter resets to 1 first.
    Also updates last_used_at and last_reset_date.

    Returns a dict with the updated counters so the caller can confirm
    the operation without a second GET.
    """
    from datetime import date as date_type
    from sqlalchemy import func as sqlfunc

    today = date_type.today()
    db_credential = (
        db.query(EmailSMTPCredentialsORM)
        .filter(EmailSMTPCredentialsORM.id == credential_id)
        .with_for_update()  # atomic row-level lock
        .first()
    )
    if not db_credential:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="SMTP credential not found")

    # Reset counter if date has rolled over
    if db_credential.last_reset_date != today:
        db_credential.current_day_sent = 0
        db_credential.last_reset_date = today

    db_credential.current_day_sent += 1
    db_credential.last_used_at = datetime.now()

    db.commit()
    db.refresh(db_credential)

    # Bust caches so downstream reads are fresh
    invalidate_cache("email_smtp_credentials")
    invalidate_cache("workflows")

    return {
        "id": db_credential.id,
        "current_day_sent": db_credential.current_day_sent,
        "daily_limit": db_credential.daily_limit,
        "last_reset_date": str(db_credential.last_reset_date),
    }


def get_email_smtp_credentials_version(db: Session) -> Response:
    return generate_version_for_model(db, EmailSMTPCredentialsORM)
