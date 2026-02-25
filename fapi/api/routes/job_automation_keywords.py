from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from fapi.db import schemas
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.database import get_db
from fapi.utils import job_automation_keyword_utils
from fapi.db.models import JobAutomationKeywordORM
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter()


security = HTTPBearer()

@router.head("/job-automation-keywords")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, JobAutomationKeywordORM)

def check_keywords_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(JobAutomationKeywordORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        JobAutomationKeywordORM.id,
                        func.coalesce(JobAutomationKeywordORM.keyword, ''),
                        func.coalesce(JobAutomationKeywordORM.category, ''),
                        func.coalesce(JobAutomationKeywordORM.source, ''),
                        func.coalesce(JobAutomationKeywordORM.is_active, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

@router.get("/job-automation-keywords", response_model=schemas.PaginatedJobAutomationKeywords)
def get_keywords(
    category: Optional[str] = None,
    source: Optional[str] = None,
    is_active: Optional[bool] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db)
):
   
    keywords, total = job_automation_keyword_utils.get_keywords(
        db=db,
        category=category,
        source=source,
        is_active=is_active,
        action=action
    )
    
    return schemas.PaginatedJobAutomationKeywords(
        total=total,
        page=1,
        per_page=total,
        keywords=keywords
    )


@router.get("/job-automation-keywords/{keyword_id}", response_model=schemas.JobAutomationKeywordOut)
def get_keyword(keyword_id: int, db: Session = Depends(get_db)):
    """Get a specific keyword by ID"""
    keyword = job_automation_keyword_utils.get_keyword(db, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return keyword


@router.post("/job-automation-keywords", response_model=schemas.JobAutomationKeywordOut, status_code=201)
def create_keyword(
    keyword: schemas.JobAutomationKeywordCreate,
    db: Session = Depends(get_db)
):
    """Create a new job automation keyword"""
    return job_automation_keyword_utils.create_keyword(db, keyword)


@router.put("/job-automation-keywords/{keyword_id}", response_model=schemas.JobAutomationKeywordOut)
def update_keyword(
    keyword_id: int,
    keyword_update: schemas.JobAutomationKeywordUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing keyword"""
    updated_keyword = job_automation_keyword_utils.update_keyword(
        db, keyword_id, keyword_update
    )
    if not updated_keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return updated_keyword


@router.delete("/job-automation-keywords/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    """Delete a keyword"""
    success = job_automation_keyword_utils.delete_keyword(db, keyword_id)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return None


@router.get("/job-automation-keywords/category/{category}", response_model=list[schemas.JobAutomationKeywordOut])
def get_keywords_by_category(
    category: str,
    source: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all active keywords for a specific category, ordered by priority"""
    keywords = job_automation_keyword_utils.get_active_keywords_by_category(
        db, category, source
    )
    return keywords
