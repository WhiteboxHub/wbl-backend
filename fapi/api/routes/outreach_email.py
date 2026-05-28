from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import OutreachEmailCreate, OutreachEmailUpdate, OutreachEmailOut
from fapi.utils import outreach_email_utils as utils

router = APIRouter(prefix="/outreach-emails", tags=["Outreach Emails"], redirect_slashes=False)

@router.head("/")
@router.head("/paginated")
def check_emails_version(db: Session = Depends(get_db)):
    return utils.get_emails_version(db)

@router.get("/", response_model=List[OutreachEmailOut])
def read_emails(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return utils.get_emails(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_emails_paginated(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 500)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = utils.count_emails(db)
    data = utils.get_emails(db, skip=skip, limit=page_size)
    total_pages = (total_records + page_size - 1) // page_size

    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

@router.get("/count", response_model=dict)
def count_emails_route(db: Session = Depends(get_db)):
    count = utils.count_emails(db)
    return {"count": count}

@router.get("/search", response_model=List[OutreachEmailOut])
def search_emails_route(term: str, db: Session = Depends(get_db)):
    return utils.search_emails(db, term=term)

@router.get("/{email_id}", response_model=OutreachEmailOut)
def read_email(email_id: int, db: Session = Depends(get_db)):
    db_email = utils.get_email_by_id(db, email_id=email_id)
    if not db_email:
        raise HTTPException(status_code=404, detail="Email record not found")
    return db_email

@router.post("/", response_model=OutreachEmailOut, status_code=status.HTTP_201_CREATED)
def create_email_route(email_data: OutreachEmailCreate, db: Session = Depends(get_db)):
    existing = utils.get_email_by_address(db, email_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="An outreach email with this email already exists")
    return utils.create_email(db, email_data=email_data)

@router.put("/{email_id}", response_model=OutreachEmailOut)
def update_email_route(email_id: int, email_data: OutreachEmailUpdate, db: Session = Depends(get_db)):
    db_email = utils.update_email(db, email_id=email_id, email_data=email_data)
    if not db_email:
        raise HTTPException(status_code=404, detail="Email record not found")
    return db_email

@router.delete("/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_route(email_id: int, db: Session = Depends(get_db)):
    success = utils.delete_email(db, email_id=email_id)
    if not success:
        raise HTTPException(status_code=404, detail="Email record not found")
    return None
