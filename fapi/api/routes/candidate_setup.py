from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from fapi.db.database import get_db
from fapi.db.models import CandidateResumeORM, CandidateAPIKeyORM, CandidateORM
from fapi.db.schemas import (
    CandidateResumeCreate, CandidateResumeOut, CandidateResumeUpdate,
    CandidateAPIKeyCreate, CandidateAPIKeyOut, CandidateAPIKeyUpdate,
    CandidateSetupStatus
)
from fapi.utils.auth_dependencies import get_current_user
from fapi.utils.db_queries import fetch_candidate_id_and_status_by_email
from fapi.utils.encryption_utils import encrypt_api_key, decrypt_api_key
import logging
import requests

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidate", tags=["Candidate Setup"])

def get_candidate_id(user, db: Session):
    # uname in AuthUserORM is usually the email in CandidateORM
    candidate_info = fetch_candidate_id_and_status_by_email(db, user.uname)
    if not candidate_info:
         raise HTTPException(status_code=404, detail="Candidate profile not found for this user.")
    return candidate_info.candidateid

@router.get("/setup-status", response_model=CandidateSetupStatus)
def get_setup_status(db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    resume = db.query(CandidateResumeORM).filter(CandidateResumeORM.candidate_id == cid).first()
    api_key = db.query(CandidateAPIKeyORM).filter(CandidateAPIKeyORM.candidate_id == cid).first()
    
    return {
        "resume_uploaded": resume is not None,
        "api_keys_configured": api_key is not None,
        "setup_complete": resume is not None and api_key is not None
    }

@router.post("/resume", response_model=CandidateResumeOut)
def upload_resume(resume_in: CandidateResumeCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    existing = db.query(CandidateResumeORM).filter(CandidateResumeORM.candidate_id == cid).first()
    if existing:
        existing.resume_json = resume_in.resume_json
        existing.file_name = resume_in.file_name
        db.commit()
        db.refresh(existing)
        return existing
    
    new_resume = CandidateResumeORM(candidate_id=cid, resume_json=resume_in.resume_json, file_name=resume_in.file_name)
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    return new_resume

@router.get("/resume", response_model=CandidateResumeOut)
def get_resume(db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    resume = db.query(CandidateResumeORM).filter(CandidateResumeORM.candidate_id == cid).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume

@router.put("/resume", response_model=CandidateResumeOut)
def update_resume(resume_in: CandidateResumeUpdate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    resume = db.query(CandidateResumeORM).filter(CandidateResumeORM.candidate_id == cid).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.resume_json = resume_in.resume_json
    resume.file_name = resume_in.file_name
    db.commit()
    db.refresh(resume)
    return resume

@router.post("/api-keys", response_model=CandidateAPIKeyOut)
def add_api_key(key_in: CandidateAPIKeyCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Validate the key before proceeding
    provider = key_in.provider_name.lower()
    is_valid = False
    try:
        if provider == "openai":
            res = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key_in.api_key}"}, timeout=5)
            is_valid = (res.status_code == 200)
        elif provider == "claude" or provider == "anthropic":
            res = requests.get("https://api.anthropic.com/v1/models", headers={"x-api-key": key_in.api_key, "anthropic-version": "2023-06-01"}, timeout=5)
            is_valid = (res.status_code == 200)
        elif provider == "gemini" or provider == "google":
            res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key_in.api_key}", timeout=5)
            is_valid = (res.status_code == 200)
        else:
            is_valid = True # skip validation for unknown providers
    except Exception as e:
        logger.error(f"Error validating API key for {key_in.provider_name}: {str(e)}")
        
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid API key for {key_in.provider_name}")

    cid = get_candidate_id(user, db)
    encrypted_key = encrypt_api_key(key_in.api_key)
    
    existing = db.query(CandidateAPIKeyORM).filter(
        CandidateAPIKeyORM.candidate_id == cid,
        CandidateAPIKeyORM.provider_name == key_in.provider_name
    ).first()
    
    if existing:
        existing.api_key = encrypted_key
        existing.model_name = key_in.model_name
        existing.services_enabled = key_in.services_enabled
        db.commit()
        db.refresh(existing)
        return existing

    new_key = CandidateAPIKeyORM(
        candidate_id=cid,
        provider_name=key_in.provider_name,
        api_key=encrypted_key,
        model_name=key_in.model_name,
        services_enabled=key_in.services_enabled
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return new_key

@router.get("/api-keys", response_model=List[CandidateAPIKeyOut])
def list_api_keys(db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    keys = db.query(CandidateAPIKeyORM).filter(CandidateAPIKeyORM.candidate_id == cid).all()
    return keys

@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    key = db.query(CandidateAPIKeyORM).filter(
        CandidateAPIKeyORM.id == key_id,
        CandidateAPIKeyORM.candidate_id == cid
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
    return {"message": "API key deleted successfully"}
