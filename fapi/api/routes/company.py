from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import CompanyCreate, CompanyUpdate, CompanyOut
from fapi.utils import company_utils

router = APIRouter(prefix="/companies", tags=["Companies"], redirect_slashes=False)

@router.get("/", response_model=List[CompanyOut])
def read_companies(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return company_utils.get_companies(db, skip=skip, limit=limit)

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
