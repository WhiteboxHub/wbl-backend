from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import OutreachEmailRecipientCreate, OutreachEmailRecipientUpdate, OutreachEmailRecipientOut
from fapi.utils import outreach_email_recipient_utils as utils

router = APIRouter(prefix="/outreach-email-recipients", tags=["Outreach Email Recipients"], redirect_slashes=False)

@router.get("/", response_model=List[OutreachEmailRecipientOut])
def read_recipients(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return utils.get_recipients(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_recipients_paginated(
    page: int = 1,
    page_size: int = 5000,
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = utils.count_recipients(db)
    data = utils.get_recipients(db, skip=skip, limit=page_size)
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
def count_recipients_route(db: Session = Depends(get_db)):
    count = utils.count_recipients(db)
    return {"count": count}

@router.get("/search", response_model=List[OutreachEmailRecipientOut])
def search_recipients_route(term: str, db: Session = Depends(get_db)):
    return utils.search_recipients(db, term=term)

@router.get("/{recipient_id}", response_model=OutreachEmailRecipientOut)
def read_recipient(recipient_id: int, db: Session = Depends(get_db)):
    db_recipient = utils.get_recipient(db, recipient_id=recipient_id)
    if not db_recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return db_recipient

@router.post("/", response_model=OutreachEmailRecipientOut, status_code=status.HTTP_201_CREATED)
def create_recipient_route(recipient: OutreachEmailRecipientCreate, db: Session = Depends(get_db)):
    return utils.create_recipient(db, recipient=recipient)

@router.put("/{recipient_id}", response_model=OutreachEmailRecipientOut)
def update_recipient_route(recipient_id: int, recipient: OutreachEmailRecipientUpdate, db: Session = Depends(get_db)):
    db_recipient = utils.update_recipient(db, recipient_id=recipient_id, recipient=recipient)
    if not db_recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return db_recipient

@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient_route(recipient_id: int, db: Session = Depends(get_db)):
    success = utils.delete_recipient(db, recipient_id=recipient_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return None
