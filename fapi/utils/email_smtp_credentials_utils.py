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
    db_credential = EmailSMTPCredentialsORM(
        name=credential_in.name,
        email=credential_in.email,
        password=credential_in.password,
        app_password=credential_in.app_password,
        daily_limit=credential_in.daily_limit,
        note=credential_in.note,
        is_active=credential_in.is_active
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
    db_credential = get_email_smtp_credential_by_id(db, credential_id)
    if not db_credential:
        return None
    
    update_data = credential_in.model_dump(exclude_unset=True)
    # These columns are NOT NULL in the DB — skip if None to preserve existing value
    NOT_NULLABLE = {"name", "email", "password", "daily_limit", "is_active"}
    for field, value in update_data.items():
        if field in NOT_NULLABLE and value is None:
            continue
        setattr(db_credential, field, value)
    
    db.commit()
    db.refresh(db_credential)
    return db_credential

def delete_email_smtp_credential(db: Session, credential_id: int):
    invalidate_cache("email_smtp_credentials")
    db_credential = get_email_smtp_credential_by_id(db, credential_id)
    if not db_credential:
        return None
    
    db.delete(db_credential)
    db.commit()
    return db_credential

def get_email_smtp_credentials_version(db: Session) -> Response:
    return generate_version_for_model(db, EmailSMTPCredentialsORM)
