from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import logging

from fapi.utils.permission_gate import enforce_access
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.database import get_db
from fapi.db.schemas import SetupInit, SyncFromWblRequest, ResumeCreate, APIKeyCreate
from fapi.utils import aiprep_setup_utils

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/summary")
def get_resume_summary(session_id: str, _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.get_resume_summary_logic(session_id, db)

@router.post("/init")
def init_session(data: SetupInit, _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.init_session_logic(data, db)

@router.post("/init-and-summary")
def init_and_summary(data: SetupInit, _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.init_and_summary_logic(data, db)

@router.post("/sync-from-wbl")
async def sync_from_wbl(data: SyncFromWblRequest, _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return await aiprep_setup_utils.sync_from_wbl_logic(data, db)

@router.get("/me")
def get_current_user(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.get_current_user_logic(current_user.uname, db)

@router.get("/setup-status")
def get_setup_status(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.get_setup_status_logic(current_user.uname, db)

@router.post("/resume", status_code=201)
async def upload_resume_file(
    file: UploadFile = File(None),
    resume_json: Optional[str] = Form(None),
    current_user=Depends(enforce_access),
    _auth=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await aiprep_setup_utils.upload_resume_file_logic(file, resume_json, current_user.uname, db)

@router.get("/resume")
def get_resume(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.get_resume_logic(current_user.uname, db)

@router.put("/resume")
def update_resume(body: ResumeCreate, current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.update_resume_logic(body, current_user.uname, db)

@router.post("/api-keys", status_code=201)
def add_api_key(body: APIKeyCreate, current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.add_api_key_logic(body, current_user.uname, db)

@router.get("/api-keys")
def list_api_keys(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.list_api_keys_logic(current_user.uname, db)

@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.delete_api_key_logic(key_id, current_user.uname, db)

@router.post("/extract-project")
def extract_project_endpoint(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.extract_project_logic(current_user.uname, db)

@router.get("/latest-project")
def get_latest_project(current_user=Depends(enforce_access), _auth=Depends(get_current_user), db: Session = Depends(get_db)):
    return aiprep_setup_utils.get_latest_project_logic(current_user.uname, db)
