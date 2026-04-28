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

def validate_resume_json(resume_json: Dict[str, Any]):
    # Define sets of possible keys for each mandatory field
    field_maps = {
        "Work Experience": ["Work Experience", "experience", "work", "work_experience", "employment"],
        "Education": ["Education", "education", "academics"],
        "LinkedIn": ["LinkedIn", "linkedin", "linkedin_url"],
        "Contact Number": ["Contact Number", "phone", "contact_number", "mobile", "phone_number"],
        "Email ID": ["Email ID", "email", "email_id"]
    }
    
    def find_field(data, keys):
        if isinstance(data, dict):
            for k, v in data.items():
                if k in keys and str(v).strip():
                    return True
                if find_field(v, keys):
                    return True
        elif isinstance(data, list):
            for item in data:
                if find_field(item, keys):
                    return True
        return False

    missing_fields = []
    
    for label, possible_keys in field_maps.items():
        if not find_field(resume_json, possible_keys):
            missing_fields.append(label)
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing or invalid mandatory fields: {', '.join(missing_fields)}"
        )

def detect_provider(api_key: str) -> str:
    if api_key.startswith("sk-ant"):
        return "claude"
    if api_key.startswith("sk-") or api_key.startswith("sk-proj-"):
        return "openai"
    if api_key.startswith("AIzaSy"):
        return "gemini"
    return "unknown"

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
    validate_resume_json(resume_in.resume_json)
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
    validate_resume_json(resume_in.resume_json)
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
    detected = detect_provider(key_in.api_key)
    provider = key_in.provider_name.lower()
    
    # If the provided provider name matches the detected one (or detected is unknown/provided is unknown), proceed.
    # We prioritize the provided provider name from the UI, but we can log a warning if they mismatch.
    
    is_valid = False
    supports_voice = False
    
    try:
        if provider == "openai":
            headers = {"Authorization": f"Bearer {key_in.api_key}"}
            res = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
            if res.status_code == 200:
                is_valid = True
                models = res.json().get("data", [])
                supports_voice = any(m["id"] == "whisper-1" for m in models)
        elif provider == "claude" or provider == "anthropic":
            headers = {
                "x-api-key": key_in.api_key, 
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            # Anthropic doesn't have a simple /models GET endpoint that works with API keys easily?
            # Actually they have /v1/models in some versions. Let's try a small message if needed, 
            # but /models is usually the standard.
            res = requests.get("https://api.anthropic.com/v1/models", headers=headers, timeout=5)
            if res.status_code == 200:
                is_valid = True
                # Claude 3.5 Sonnet supports multimodal (including audio in some contexts)
                supports_voice = True # For now assume Claude models added are latest
        elif provider == "gemini" or provider == "google":
            res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key_in.api_key}", timeout=5)
            if res.status_code == 200:
                is_valid = True
                models = res.json().get("models", [])
                # Gemini 1.5 Pro and Flash support audio
                supports_voice = any("gemini-1.5" in m["name"] for m in models)
        else:
            is_valid = True # skip validation for unknown providers
            supports_voice = True

    except Exception as e:
        logger.error(f"Error validating API key for {key_in.provider_name}: {str(e)}")
        
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid API Key")

    if key_in.voice_enabled and not supports_voice:
        raise HTTPException(status_code=400, detail="API key does not support voice processing")

    cid = get_candidate_id(user, db)
    encrypted_key = encrypt_api_key(key_in.api_key)
    
    # Check for exact duplicate (same provider, same model, same key) to avoid noise
    existing_duplicate = db.query(CandidateAPIKeyORM).filter(
        CandidateAPIKeyORM.candidate_id == cid,
        CandidateAPIKeyORM.provider_name == key_in.provider_name,
        CandidateAPIKeyORM.model_name == key_in.model_name,
        CandidateAPIKeyORM.api_key == encrypted_key
    ).first()

    if existing_duplicate:
        existing_duplicate.voice_enabled = key_in.voice_enabled
        db.commit()
        db.refresh(existing_duplicate)
        # Return with masked key
        out = CandidateAPIKeyOut.from_orm(existing_duplicate)
        try:
            raw = decrypt_api_key(existing_duplicate.api_key)
            out.masked_key = f"{'*' * (len(raw)-4)}{raw[-4:]}" if len(raw) > 4 else "****"
        except:
            out.masked_key = "****"
        return out

    new_key = CandidateAPIKeyORM(
        candidate_id=cid,
        provider_name=key_in.provider_name,
        api_key=encrypted_key,
        model_name=key_in.model_name,
        voice_enabled=key_in.voice_enabled
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    
    # Return with masked key
    out = CandidateAPIKeyOut.from_orm(new_key)
    try:
        raw = decrypt_api_key(new_key.api_key)
        out.masked_key = f"{'*' * (len(raw)-4)}{raw[-4:]}" if len(raw) > 4 else "****"
    except:
        out.masked_key = "****"
    return out

@router.get("/api-keys", response_model=List[CandidateAPIKeyOut])
def list_api_keys(db: Session = Depends(get_db), user = Depends(get_current_user)):
    cid = get_candidate_id(user, db)
    keys = db.query(CandidateAPIKeyORM).filter(CandidateAPIKeyORM.candidate_id == cid).all()
    out = []
    for k in keys:
        try:
            raw = decrypt_api_key(k.api_key)
            masked = f"{'*' * (len(raw)-4)}{raw[-4:]}" if len(raw) > 4 else "****"
        except:
            masked = "****"
        item = CandidateAPIKeyOut.from_orm(k)
        item.masked_key = masked
        out.append(item)
    return out

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