from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import job_automation_keyword_utils

router = APIRouter()


@router.get("/job-automation-keywords", response_model=schemas.PaginatedJobAutomationKeywords)
def get_keywords(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    source: Optional[str] = None,
    is_active: Optional[bool] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db)
):
   
    skip = (page - 1) * per_page
    keywords, total = job_automation_keyword_utils.get_keywords(
        db=db,
        skip=skip,
        limit=per_page,
        category=category,
        source=source,
        is_active=is_active,
        action=action
    )
    
    return schemas.PaginatedJobAutomationKeywords(
        total=total,
        page=page,
        per_page=per_page,
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
