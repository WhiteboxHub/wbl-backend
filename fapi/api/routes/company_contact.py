from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import CompanyContactCreate, CompanyContactUpdate, CompanyContactOut
from fapi.utils import company_contact_utils

router = APIRouter(prefix="/company-contacts", tags=["Company Contacts"], redirect_slashes=False)

@router.get("/", response_model=List[CompanyContactOut])
def read_company_contacts(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return company_contact_utils.get_company_contacts(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_company_contacts_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):

    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = company_contact_utils.count_company_contacts(db)
    data = company_contact_utils.get_company_contacts(db, skip=skip, limit=page_size)
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
def count_company_contacts(db: Session = Depends(get_db)):
    """Get total count of company contacts for pagination"""
    count = company_contact_utils.count_company_contacts(db)
    return {"count": count}

@router.get("/search", response_model=List[CompanyContactOut])
def search_company_contacts(term: str, db: Session = Depends(get_db)):
    return company_contact_utils.search_company_contacts(db, term=term)

@router.get("/company/{company_id}", response_model=List[CompanyContactOut])
def read_contacts_by_company(company_id: int, db: Session = Depends(get_db)):
    return company_contact_utils.get_contacts_by_company(db, company_id=company_id)

@router.get("/{contact_id}", response_model=CompanyContactOut)
def read_company_contact(contact_id: int, db: Session = Depends(get_db)):
    db_contact = company_contact_utils.get_company_contact(db, contact_id=contact_id)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Company contact not found")
    return db_contact

@router.post("/", response_model=CompanyContactOut, status_code=status.HTTP_201_CREATED)
def create_company_contact(contact: CompanyContactCreate, db: Session = Depends(get_db)):
    return company_contact_utils.create_company_contact(db, contact=contact)

@router.put("/{contact_id}", response_model=CompanyContactOut)
def update_company_contact(contact_id: int, contact: CompanyContactUpdate, db: Session = Depends(get_db)):
    db_contact = company_contact_utils.update_company_contact(db, contact_id=contact_id, contact=contact)
    if not db_contact:
        raise HTTPException(status_code=404, detail="Company contact not found")
    return db_contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_contact(contact_id: int, db: Session = Depends(get_db)):
    success = company_contact_utils.delete_company_contact(db, contact_id=contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Company contact not found")
    return None
