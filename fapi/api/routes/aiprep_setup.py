from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Union
from pydantic import BaseModel
import json
import logging

from fapi.utils.permission_gate import enforce_access
from fapi.utils.encryption_utils import encrypt_api_key, decrypt_api_key
from fapi.utils.aiprep_setup_utils import _get_candidate_id, _validate_api_key, _mask_key, save_resume_for_session, process_resume_parsing

from fapi.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

class SetupInit(BaseModel):
    candidate_email: Optional[str] = None
    candidate_id: Optional[Union[str, int]] = None
    marketing_id: Optional[Union[str, int]] = None
    prep_token: Optional[Union[str, int]] = None

class SyncFromWblRequest(BaseModel):
    prep_token: str

class ResumeCreate(BaseModel):
    resume_json: dict
    file_name: Optional[str] = None

class APIKeyCreate(BaseModel):
    provider_name: str
    api_key: str
    model_name: Optional[str] = None
    voice_enabled: bool = False


def fetch_resume_raw(db: Session, session_id: str) -> Optional[dict]:
    if not session_id or session_id == "null": return None
    try:
        marketing_id = int(session_id)
        result = db.execute(text("SELECT candidate_json FROM candidate_marketing WHERE id = :mid"), {"mid": marketing_id}).fetchone()
        if not result or not result[0]:
            return None
        raw = result[0]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        pass
                return parsed
            except Exception:
                return None
        return raw
    except Exception:
        return None

def _resolve_session(db: Session, data: SetupInit) -> int:
    if data.prep_token:
        result = db.execute(text("SELECT id FROM candidate_marketing WHERE id = :id"), {"id": int(data.prep_token)}).fetchone()
        if result:
            return result[0]

    if data.marketing_id:
        result = db.execute(text("SELECT id FROM candidate_marketing WHERE id = :id"), {"id": int(data.marketing_id)}).fetchone()
        if result:
            return result[0]

    candidate_id = None
    if data.candidate_id:
        result = db.execute(text("SELECT id FROM candidate WHERE id = :id"), {"id": int(data.candidate_id)}).fetchone()
        if result:
            candidate_id = result[0]

    if not candidate_id and data.candidate_email:
        result = db.execute(text("SELECT id FROM candidate WHERE email = :email LIMIT 1"), {"email": data.candidate_email}).fetchone()
        if result:
            candidate_id = result[0]

    if candidate_id:
        result = db.execute(
            text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"),
            {"cid": candidate_id}
        ).fetchone()
        if result:
            return result[0]

        db.execute(text("INSERT INTO candidate_marketing (candidate_id, status) VALUES (:cid, 'active')"), {"cid": candidate_id})
        db.commit()
        result = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        return result[0]

    raise HTTPException(status_code=400, detail="Cannot resolve session from provided tokens")

def _upsert_eval_login(db: Session, marketing_id: int):
    pass

@router.get("/summary")
def get_resume_summary(session_id: str, db: Session = Depends(get_db)):
    try:
        if session_id == "null" or not session_id:
            raise HTTPException(status_code=404, detail="Invalid session ID")
        marketing_id = int(session_id)

        cand_row = db.execute(
            text("""
            SELECT c.full_name AS name, cm.email, cm.candidate_id, (cm.candidate_json IS NOT NULL) AS has_binary_resume
            FROM candidate_marketing cm
            JOIN candidate c ON c.id = cm.candidate_id
            WHERE cm.id = :mid
            """),
            {"mid": marketing_id}
        ).mappings().fetchone()
        
        if not cand_row:
            raise HTTPException(status_code=404, detail="Session/Candidate not found")

        candidate_name = cand_row["name"] if cand_row and cand_row.get("name") else ""
        candidate_email = cand_row["email"] if cand_row and cand_row.get("email") else ""
        cid = cand_row["candidate_id"] if cand_row else None
        has_binary_resume = bool(cand_row["has_binary_resume"]) if cand_row and "has_binary_resume" in cand_row else False

        raw_resume = fetch_resume_raw(db, session_id)
        has_resume = raw_resume is not None

        llm_keys = []
        has_api_key = False
        if cid:
            keys = db.execute(
                text("SELECT id, provider_name, model_name, voice_enabled, created_at FROM candidate_llm_api_keys WHERE candidate_id = :cid ORDER BY id ASC"),
                {"cid": cid}
            ).mappings().fetchall()
            llm_keys = [dict(k) for k in keys]
            has_api_key = len(llm_keys) > 0

        resume_json_out = raw_resume
        resume_filename = ""
        if isinstance(resume_json_out, dict):
            resume_filename = resume_json_out.get("_meta_filename", "")

        if has_resume and not candidate_name and isinstance(resume_json_out, dict):
            basics = resume_json_out.get("basics") or {}
            candidate_name = basics.get("name") or resume_json_out.get("name") or ""

        return {
            "resume_text": "Exists" if has_resume else None,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "has_api_key": has_api_key,
            "resume_json": resume_json_out,
            "resume_filename": resume_filename,
            "llm_keys": llm_keys,
            "has_binary_resume": has_binary_resume,
        }
    except Exception as e:
        logger.error("ERROR in get_resume_summary: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/init")
def init_session(data: SetupInit, db: Session = Depends(get_db)):
    try:
        marketing_id = _resolve_session(db, data)
        _upsert_eval_login(db, marketing_id)
        db.commit()
        return {"session_id": str(marketing_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR in init_session: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/init-and-summary")
def init_and_summary(data: SetupInit, db: Session = Depends(get_db)):
    try:
        marketing_id = _resolve_session(db, data)
        _upsert_eval_login(db, marketing_id)
        db.commit()
        session_id = str(marketing_id)
        
        summary = get_resume_summary(session_id, db)
        return {
            "session_id": session_id,
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR in init_and_summary: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-from-wbl")
async def sync_from_wbl(data: SyncFromWblRequest, db: Session = Depends(get_db)):
    session_id = data.prep_token
    resume = fetch_resume_raw(db, session_id)
    if not resume:
        raise HTTPException(status_code=400, detail="Setup not completed yet")

    needs_extraction = False
    name = "Candidate"
    email = ""
    try:
        candidate_id = int(session_id)
        result = db.execute(
            text("SELECT id FROM aiprep_tool_project_context WHERE user_id = :uid"),
            {"uid": candidate_id}
        ).fetchone()
        needs_extraction = not result

        row = db.execute(
            text("SELECT full_name AS name, email FROM candidate c JOIN candidate_marketing cm ON c.id = cm.candidate_id WHERE cm.id = :mid"),
            {"mid": candidate_id}
        ).mappings().fetchone()
        if row:
            if row.get("name"):
                name = row["name"]
            email = row.get("email") or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if needs_extraction:
        try:
            from fapi.utils.aiprep_setup_utils import extract_latest_company_bg
            extract_latest_company_bg(session_id, resume, "dummy_key", "openai")
        except Exception as e:
            logger.error(f"Extraction failed during sync: {e}")

    return {"session_id": session_id, "candidate_name": name, "candidate_email": email}

@router.get("/me")
def get_current_user(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        row = db.execute(text("SELECT full_name FROM candidate WHERE id = :cid"), {"cid": candidate_id}).fetchone()
        name = row[0] if row and row[0] else "Candidate"
        return {
            "session_id": str(candidate_id),
            "candidate_name": name,
            "candidate_email": user_email
        }
    except Exception as e:
        logger.error(f"get_current_user error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch candidate profile")

@router.get("/setup-status")
def get_setup_status(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        resume_exists = db.execute(
            text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid AND candidate_json IS NOT NULL"), 
            {"cid": candidate_id}
        ).fetchone() is not None
        keys_exist = db.execute(
            text("SELECT id FROM candidate_llm_api_keys WHERE candidate_id = :cid LIMIT 1"),
            {"cid": candidate_id}
        ).fetchone() is not None

        return {
            "resume_uploaded": resume_exists,
            "api_keys_configured": keys_exist,
            "setup_complete": resume_exists and keys_exist,
        }
    except Exception as e:
        logger.error(f"setup-status error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch setup status")

@router.post("/resume", status_code=201)
async def upload_resume_file(
    file: UploadFile = File(None),
    resume_json: Optional[str] = Form(None),
    current_user=Depends(enforce_access),
    db: Session = Depends(get_db)
):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        
        marketing_id_row = db.execute(text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"), {"cid": candidate_id}).fetchone()
        if not marketing_id_row:
            db.execute(text("INSERT INTO candidate_marketing (candidate_id, status) VALUES (:cid, 'active')"), {"cid": candidate_id})
            db.commit()
            marketing_id_row = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        marketing_id = marketing_id_row[0]

        updated_resume = None
        file_name = file.filename if file else "resume.json"

        if file:
            content = await file.read()
            if file.filename.endswith(".json") or file.content_type == "application/json":
                updated_resume = json.loads(content.decode("utf-8"))
                save_resume_for_session(db, str(marketing_id), updated_resume)
            else:
                updated_resume = process_resume_parsing(content, file.filename, candidate_id, marketing_id, db)
                save_resume_for_session(db, str(marketing_id), updated_resume)
        elif resume_json:
            updated_resume = json.loads(resume_json)
            save_resume_for_session(db, str(marketing_id), updated_resume)
        else:
            raise HTTPException(status_code=400, detail="No file or resume_json provided")

        return {"resume_json": updated_resume, "file_name": file_name}
    except Exception as e:
        logger.error(f"upload_resume error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resume")
def get_resume(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        marketing_id_row = db.execute(text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"), {"cid": candidate_id}).fetchone()
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Resume not found")
            
        raw = fetch_resume_raw(db, str(marketing_id_row[0]))
        if not raw:
            raise HTTPException(status_code=404, detail="Resume not found")
        return {"resume_json": raw}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_resume error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch resume")

@router.put("/resume")
def update_resume(body: ResumeCreate, current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        marketing_id_row = db.execute(text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"), {"cid": candidate_id}).fetchone()
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Candidate marketing not found")
            
        save_resume_for_session(db, str(marketing_id_row[0]), body.resume_json)
        return {"resume_json": body.resume_json, "file_name": body.file_name}
    except Exception as e:
        logger.error(f"update_resume error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update resume")

@router.post("/api-keys", status_code=201)
def add_api_key(body: APIKeyCreate, current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    provider = body.provider_name.lower()
    is_valid, supports_voice = _validate_api_key(provider, body.api_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid API Key")

    encrypted_key = encrypt_api_key(body.api_key)
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        dup = db.execute(
            text("SELECT id FROM candidate_llm_api_keys WHERE candidate_id = :cid AND provider_name = :p AND model_name = :m AND api_key = :k"),
            {"cid": candidate_id, "p": body.provider_name, "m": body.model_name or "", "k": encrypted_key}
        ).fetchone()

        if dup:
            db.execute(text("UPDATE candidate_llm_api_keys SET voice_enabled = :v WHERE id = :id"), {"v": int(body.voice_enabled), "id": dup[0]})
            db.commit()
            row = db.execute(text("SELECT id, provider_name, model_name, voice_enabled, api_key FROM candidate_llm_api_keys WHERE id = :id"), {"id": dup[0]}).mappings().fetchone()
        else:
            db.execute(
                text("INSERT INTO candidate_llm_api_keys (candidate_id, provider_name, api_key, model_name, voice_enabled) VALUES (:cid, :p, :k, :m, :v)"),
                {"cid": candidate_id, "p": body.provider_name, "k": encrypted_key, "m": body.model_name or "", "v": int(body.voice_enabled)}
            )
            db.commit()
            last_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
            row = db.execute(text("SELECT id, provider_name, model_name, voice_enabled, api_key FROM candidate_llm_api_keys WHERE id = :id"), {"id": last_id}).mappings().fetchone()
        
        row_dict = dict(row)
        try:
            raw = decrypt_api_key(row_dict["api_key"])
            row_dict["masked_key"] = _mask_key(raw)
        except:
            row_dict["masked_key"] = "****"
        row_dict.pop("api_key", None)
        return row_dict
    except Exception as e:
        logger.error(f"add_api_key error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save API key")

@router.get("/api-keys")
def list_api_keys(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        rows = db.execute(
            text("SELECT id, provider_name, model_name, voice_enabled, api_key FROM candidate_llm_api_keys WHERE candidate_id = :cid"),
            {"cid": candidate_id}
        ).mappings().fetchall()

        result = []
        for r in rows:
            row_dict = dict(r)
            try:
                raw = decrypt_api_key(row_dict["api_key"])
                row_dict["masked_key"] = _mask_key(raw)
            except:
                row_dict["masked_key"] = "****"
            row_dict.pop("api_key", None)
            result.append(row_dict)
        return result
    except Exception as e:
        logger.error(f"list_api_keys error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")

@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        existing = db.execute(
            text("SELECT id FROM candidate_llm_api_keys WHERE id = :kid AND candidate_id = :cid"),
            {"kid": key_id, "cid": candidate_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="API key not found")
        db.execute(text("DELETE FROM candidate_llm_api_keys WHERE id = :kid"), {"kid": key_id})
        db.commit()
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_api_key error for {current_user.uname}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete API key")

@router.post("/extract-project")
def extract_project_endpoint(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        marketing_id_row = db.execute(text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"), {"cid": candidate_id}).fetchone()
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Setup not completed yet")
            
        marketing_id = str(marketing_id_row[0])
        
        row = db.execute(
            text("SELECT * FROM aiprep_tool_project_context WHERE user_id = :uid"),
            {"uid": marketing_id}
        ).mappings().fetchone()
        
        if row:
            res = dict(row)
            try: res["skills"] = json.loads(res.get("skills") or "[]")
            except: res["skills"] = []
            return res
        return {}
    except Exception as e:
        logger.error(f"extract-project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest-project")
def get_latest_project(current_user=Depends(enforce_access), db: Session = Depends(get_db)):
    try:
        user_email = current_user.uname
        candidate_id = _get_candidate_id(db, user_email)
        marketing_id_row = db.execute(text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"), {"cid": candidate_id}).fetchone()
        if not marketing_id_row:
            return {}
            
        marketing_id = str(marketing_id_row[0])
        
        row = db.execute(
            text("SELECT * FROM aiprep_tool_project_context WHERE user_id = :uid"),
            {"uid": marketing_id}
        ).mappings().fetchone()
        
        if row:
            res = dict(row)
            try: res["skills"] = json.loads(res.get("skills") or "[]")
            except: res["skills"] = []
            return res
        return {}
    except Exception as e:
        logger.error(f"latest-project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

