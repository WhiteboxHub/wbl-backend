from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import CompanyContactCreate, CompanyContactUpdate, CompanyContactOut
from fapi.utils import company_contact_utils

router = APIRouter(prefix="/company-contacts", tags=["Company Contacts"], redirect_slashes=False)

@router.get("/", response_model=List[CompanyContactOut])
def read_company_contacts(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Get company contacts with pagination.
    
    Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 1000, max: 999999)
    
    Examples:
    - /api/company-contacts/ → Returns first 1000 records
    - /api/company-contacts/?limit=50 → Returns first 50 records
    - /api/company-contacts/?skip=50&limit=50 → Returns records 51-100
    - /api/company-contacts/?limit=999999 → Returns all records (may timeout!)
    """
    return company_contact_utils.get_company_contacts(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_company_contacts_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    """
    Get company contacts with pagination metadata.
    
    Parameters:
    - page: Page number (starts at 1)
    - page_size: Number of records per page (default: 5000, max: 10000)
    
    Returns:
    {
        "data": [...],           // Array of records
        "page": 1,               // Current page number
        "page_size": 5000,       // Records per page
        "total_records": 200000, // Total number of records
        "total_pages": 40,       // Total number of pages
        "has_next": true,        // Whether there's a next page
        "has_prev": false        // Whether there's a previous page
    }
    
    Examples:
    - /api/company-contacts/paginated → Page 1, 5000 records
    - /api/company-contacts/paginated?page=2 → Page 2, 5000 records
    - /api/company-contacts/paginated?page=1&page_size=10000 → Page 1, 10000 records
    """
    # Validate and cap page_size
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)  # Ensure page is at least 1
    
    # Calculate skip
    skip = (page - 1) * page_size
    
    # Get total count
    total_records = company_contact_utils.count_company_contacts(db)
    
    # Get paginated data
    data = company_contact_utils.get_company_contacts(db, skip=skip, limit=page_size)
    
    # Calculate pagination metadata
    total_pages = (total_records + page_size - 1) // page_size  # Ceiling division
    
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
