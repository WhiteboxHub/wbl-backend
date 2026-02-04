from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import email_engine_utils

router = APIRouter()
security = HTTPBearer()

@router.get("/email-engine", response_model=List[schemas.EmailSenderEngineOut])
def read_engines(
    search: Optional[str] = Query(None, description="Search by engine name or provider"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all email engines"""
    return email_engine_utils.get_all_engines(db, search=search)

@router.get("/email-engine/{engine_id}", response_model=schemas.EmailSenderEngineOut)
def read_engine(
    engine_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific email engine"""
    return email_engine_utils.get_engine_by_id(db, engine_id)

@router.post("/email-engine", response_model=schemas.EmailSenderEngineOut)
def create_engine(
    engine: schemas.EmailSenderEngineCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new email engine"""
    return email_engine_utils.create_engine(db, engine)

@router.put("/email-engine/{engine_id}", response_model=schemas.EmailSenderEngineOut)
def update_engine(
    engine_id: int,
    engine: schemas.EmailSenderEngineUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing email engine"""
    return email_engine_utils.update_engine(db, engine_id, engine)

@router.delete("/email-engine/{engine_id}")
def delete_engine(
    engine_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete an email engine"""
    if email_engine_utils.delete_engine(db, engine_id):
        return {"message": "Email engine deleted successfully"}
    raise HTTPException(status_code=400, detail="Failed to delete email engine")
