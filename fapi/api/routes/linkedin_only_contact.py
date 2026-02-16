from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import LinkedinOnlyContactCreate, LinkedinOnlyContactUpdate, LinkedinOnlyContactOut, PaginatedLinkedinOnlyContactResponse
from fapi.utils import linkedin_only_contact_utils

router = APIRouter(prefix="/linkedin-only-contacts", tags=["Linkedin Only Contacts"], redirect_slashes=False)

@router.get("/", response_model=List[LinkedinOnlyContactOut])
def read_linkedin_only_contacts(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return linkedin_only_contact_utils.get_linkedin_only_contacts(db, skip=skip, limit=limit)

@router.get("/paginated", response_model=PaginatedLinkedinOnlyContactResponse)
def read_linkedin_only_contacts_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):

    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = linkedin_only_contact_utils.count_linkedin_only_contacts(db)
    data = linkedin_only_contact_utils.get_linkedin_only_contacts(db, skip=skip, limit=page_size)
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
def count_linkedin_only_contacts(db: Session = Depends(get_db)):
    """Get total count of company contacts for pagination"""
    count = linkedin_only_contact_utils.count_linkedin_only_contacts(db)
    return {"count": count}

@router.get("/search", response_model=List[LinkedinOnlyContactOut])
def search_linkedin_only_contacts(term: str, db: Session = Depends(get_db)):
    return linkedin_only_contact_utils.search_linkedin_only_contacts(db, term=term)

@router.get("/{contact_id}", response_model=LinkedinOnlyContactOut)
def read_linkedin_only_contact(contact_id: int, db: Session = Depends(get_db)):
    db_contact = linkedin_only_contact_utils.get_linkedin_only_contact(db, contact_id=contact_id)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.post("/", response_model=LinkedinOnlyContactOut, status_code=status.HTTP_201_CREATED)
def create_linkedin_only_contact(contact: LinkedinOnlyContactCreate, db: Session = Depends(get_db)):
    return linkedin_only_contact_utils.create_linkedin_only_contact(db, contact=contact)

@router.put("/{contact_id}", response_model=LinkedinOnlyContactOut)
def update_linkedin_only_contact(contact_id: int, contact: LinkedinOnlyContactUpdate, db: Session = Depends(get_db)):
    db_contact = linkedin_only_contact_utils.update_linkedin_only_contact(db, contact_id=contact_id, contact=contact)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_linkedin_only_contact(contact_id: int, db: Session = Depends(get_db)):
    success = linkedin_only_contact_utils.delete_linkedin_only_contact(db, contact_id=contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    return None
