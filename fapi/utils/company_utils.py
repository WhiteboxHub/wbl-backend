from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import Company
from fapi.db.schemas import CompanyCreate, CompanyUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

@cache_result(ttl=300, prefix="companies")
def get_companies(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[Company]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999  # Effectively unlimited, but may cause timeout
    
    query = db.query(Company).order_by(Company.id.desc()).offset(skip)
    
    # Apply limit with sensible defaults
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        # Cap at MAX_LIMIT to prevent abuse
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

@cache_result(ttl=300, prefix="companies")
def get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()

def create_company(db: Session, company: CompanyCreate) -> Company:
    invalidate_cache("companies")
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

def update_company(db: Session, company_id: int, company: CompanyUpdate) -> Optional[Company]:
    invalidate_cache("companies")
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
    invalidate_cache("companies")
    db_company = db.query(Company).filter(Company.id == company_id).first()
    if not db_company:
        return False
    
    db.delete(db_company)
    db.commit()
    return True

@cache_result(ttl=300, prefix="companies")
def search_companies(db: Session, term: str) -> List[Company]:
    return db.query(Company).filter(
        or_(
            Company.name.ilike(f"%{term}%"),
            Company.domain.ilike(f"%{term}%"),
            Company.city.ilike(f"%{term}%")
        )
    ).limit(100).all()

@cache_result(ttl=300, prefix="companies")
def count_companies(db: Session) -> int:
    """Get total count of companies for pagination"""
    return db.query(Company).count()
def get_companies_version(db: Session) -> Response:
    return generate_version_for_model(db, Company)
