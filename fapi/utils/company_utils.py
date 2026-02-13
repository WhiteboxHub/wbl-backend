from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import Company
from fapi.db.schemas import CompanyCreate, CompanyUpdate
from typing import List, Optional

def get_companies(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[Company]:
    query = db.query(Company).order_by(Company.id.desc()).offset(skip)
    if limit:
        query = query.limit(limit)
    return query.all()

def get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()

def create_company(db: Session, company: CompanyCreate) -> Company:
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

def update_company(db: Session, company_id: int, company: CompanyUpdate) -> Optional[Company]:
    db_company = db.query(Company).filter(Company.id == company_id).first()
    if not db_company:
        return None
    
    update_data = company.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_company, key, value)
    
    db.commit()
    db.refresh(db_company)
    return db_company

def delete_company(db: Session, company_id: int) -> bool:
    db_company = db.query(Company).filter(Company.id == company_id).first()
    if not db_company:
        return False
    
    db.delete(db_company)
    db.commit()
    return True

def search_companies(db: Session, term: str) -> List[Company]:
    return db.query(Company).filter(
        or_(
            Company.name.ilike(f"%{term}%"),
            Company.domain.ilike(f"%{term}%"),
            Company.city.ilike(f"%{term}%")
        )
    ).limit(100).all()
