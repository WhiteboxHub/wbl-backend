from fastapi import APIRouter, Depends, HTTPException, status, Body, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import (
    AutomationContactExtractCreate, 
    AutomationContactExtractUpdate, 
    AutomationContactExtractOut,
    AutomationContactExtractBulkCreate,
    AutomationContactExtractBulkResponse
)
from fapi.utils import automation_contact_utils

router = APIRouter(prefix="/automation-extracts", tags=["Automation Extracts"])

security = HTTPBearer()

@router.get("/", response_model=List[AutomationContactExtractOut])
async def read_automation_extracts(
    status: Optional[str] = None, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.get_all_automation_extracts(db, status=status)

@router.get("/paginated")
def read_automation_extracts_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get automation extracts with page-based pagination"""
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = automation_contact_utils.count_automation_extracts(db, status=status)
    data = automation_contact_utils.get_automation_extracts_paginated(db, skip=skip, limit=page_size, status=status)
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

@router.post("/", response_model=AutomationContactExtractOut, status_code=status.HTTP_201_CREATED)
async def create_automation_extract(
    extract: AutomationContactExtractCreate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.insert_automation_extract(extract, db)

@router.post("/bulk", response_model=AutomationContactExtractBulkResponse)
async def create_automation_extracts_bulk(
    bulk_data: AutomationContactExtractBulkCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.insert_automation_extracts_bulk(bulk_data.extracts, db)

@router.delete("/bulk", status_code=status.HTTP_200_OK)
async def delete_automation_extracts_bulk(
    extract_ids: List[int] = Body(...), 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.delete_automation_extracts_bulk(extract_ids, db)

@router.get("/{extract_id}", response_model=AutomationContactExtractOut)
async def read_automation_extract(
    extract_id: int, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.get_automation_extract_by_id(extract_id, db)

@router.put("/{extract_id}", response_model=AutomationContactExtractOut)
async def update_automation_extract(
    extract_id: int, 
    update_data: AutomationContactExtractUpdate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.update_automation_extract(extract_id, update_data, db)

@router.delete("/{extract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_extract(
    extract_id: int, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    await automation_contact_utils.delete_automation_extract(extract_id, db)
    return None
