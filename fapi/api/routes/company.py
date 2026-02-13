from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import CompanyCreate, CompanyUpdate, CompanyOut
from fapi.utils import company_utils

router = APIRouter(prefix="/companies", tags=["Companies"], redirect_slashes=False)

@router.get("/", response_model=List[CompanyOut])
def read_companies(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Get companies with pagination.
    
    Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 1000, max: 999999)
    
    Examples:
    - /api/companies/ → Returns first 1000 records
    - /api/companies/?limit=50 → Returns first 50 records
    - /api/companies/?skip=50&limit=50 → Returns records 51-100
    - /api/companies/?limit=999999 → Returns all records (may timeout!)
    """
    return company_utils.get_companies(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_companies_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    """
    Get companies with pagination metadata.
    
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
    - /api/companies/paginated → Page 1, 5000 records
    - /api/companies/paginated?page=2 → Page 2, 5000 records
    - /api/companies/paginated?page=1&page_size=10000 → Page 1, 10000 records
    """
    # Validate and cap page_size
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)  # Ensure page is at least 1
    
    # Calculate skip
    skip = (page - 1) * page_size
    
    # Get total count
    total_records = company_utils.count_companies(db)
    
    # Get paginated data
    data = company_utils.get_companies(db, skip=skip, limit=page_size)
    
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
def count_companies(db: Session = Depends(get_db)):
    """Get total count of companies for pagination"""
    count = company_utils.count_companies(db)
    return {"count": count}

@router.get("/search", response_model=List[CompanyOut])
def search_companies(term: str, db: Session = Depends(get_db)):
    return company_utils.search_companies(db, term=term)

@router.get("/{company_id}", response_model=CompanyOut)
def read_company(company_id: int, db: Session = Depends(get_db)):
    db_company = company_utils.get_company(db, company_id=company_id)
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

@router.post("/", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    return company_utils.create_company(db, company=company)

@router.put("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, company: CompanyUpdate, db: Session = Depends(get_db)):
    db_company = company_utils.update_company(db, company_id=company_id, company=company)
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    success = company_utils.delete_company(db, company_id=company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Company not found")
    return None