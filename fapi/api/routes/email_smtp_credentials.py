from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import (
    EmailSMTPCredentialsOut, 
    EmailSMTPCredentialsCreate, 
    EmailSMTPCredentialsUpdate
)
from fapi.utils import email_smtp_credentials_utils
from fapi.utils.email_smtp_credentials_utils import get_email_smtp_credentials_version

router = APIRouter()

security = HTTPBearer()

@router.head("/email-smtp-credentials")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_email_smtp_credentials_version(db)

@router.get("/email-smtp-credentials", response_model=List[EmailSMTPCredentialsOut])
def read_email_smtp_credentials(
    skip: int = 0,
    limit: int = 100,
    search: str = Query(None, description="Search by name"),
    db: Session = Depends(get_db)
):
    return email_smtp_credentials_utils.get_email_smtp_credentials(db, skip=skip, limit=limit, search=search)

@router.get("/email-smtp-credentials/{credential_id}", response_model=EmailSMTPCredentialsOut)
def read_email_smtp_credential(credential_id: int, db: Session = Depends(get_db)):
    db_credential = email_smtp_credentials_utils.get_email_smtp_credential_by_id(db, credential_id)
    if db_credential is None:
        raise HTTPException(status_code=404, detail="Email SMTP Credential not found")
    return db_credential

@router.post("/email-smtp-credentials", response_model=EmailSMTPCredentialsOut)
def create_new_email_smtp_credential(
    credential: EmailSMTPCredentialsCreate, 
    db: Session = Depends(get_db)
):
    db_credential = email_smtp_credentials_utils.get_email_smtp_credential_by_email(db, email=credential.email)
    if db_credential:
        raise HTTPException(status_code=400, detail="Email already registered")
    return email_smtp_credentials_utils.create_email_smtp_credential(db=db, credential_in=credential)

@router.put("/email-smtp-credentials/{credential_id}", response_model=EmailSMTPCredentialsOut)
def update_existing_email_smtp_credential(
    credential_id: int, 
    credential: EmailSMTPCredentialsUpdate, 
    db: Session = Depends(get_db)
):
    db_credential = email_smtp_credentials_utils.update_email_smtp_credential(db, credential_id, credential)
    if db_credential is None:
        raise HTTPException(status_code=404, detail="Email SMTP Credential not found")
    return db_credential

@router.delete("/email-smtp-credentials/{credential_id}", response_model=EmailSMTPCredentialsOut)
def delete_existing_email_smtp_credential(credential_id: int, db: Session = Depends(get_db)):
    db_credential = email_smtp_credentials_utils.delete_email_smtp_credential(db, credential_id)
    if db_credential is None:
        raise HTTPException(status_code=404, detail="Email SMTP Credential not found")
    return db_credential
