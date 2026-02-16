from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import PersonalDomainContactCreate, PersonalDomainContactUpdate, PersonalDomainContactOut
from fapi.utils import personal_domain_contact_utils as utils

router = APIRouter(prefix="/personal-domain-contacts", tags=["Personal Domain Contacts"], redirect_slashes=False)

@router.get("/", response_model=List[PersonalDomainContactOut])
def read_contacts(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return utils.get_personal_domain_contacts(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_contacts_paginated(
    page: int = 1,
    page_size: int = 5000,
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = utils.count_personal_domain_contacts(db)
    data = utils.get_personal_domain_contacts(db, skip=skip, limit=page_size)
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
def count_contacts(db: Session = Depends(get_db)):
    count = utils.count_personal_domain_contacts(db)
    return {"count": count}

@router.get("/search", response_model=List[PersonalDomainContactOut])
def search_contacts(term: str, db: Session = Depends(get_db)):
    return utils.search_personal_domain_contacts(db, term=term)

@router.get("/{contact_id}", response_model=PersonalDomainContactOut)
def read_contact(contact_id: int, db: Session = Depends(get_db)):
    db_contact = utils.get_personal_domain_contact(db, contact_id=contact_id)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.post("/", response_model=PersonalDomainContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(contact: PersonalDomainContactCreate, db: Session = Depends(get_db)):
    return utils.create_personal_domain_contact(db, contact=contact)

@router.put("/{contact_id}", response_model=PersonalDomainContactOut)
def update_contact(contact_id: int, contact: PersonalDomainContactUpdate, db: Session = Depends(get_db)):
    db_contact = utils.update_personal_domain_contact(db, contact_id=contact_id, contact=contact)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    success = utils.delete_personal_domain_contact(db, contact_id=contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    return None
