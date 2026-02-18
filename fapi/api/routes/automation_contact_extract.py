from fastapi import APIRouter, Depends, HTTPException, status, Body
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

@router.get("/", response_model=List[AutomationContactExtractOut])
async def read_automation_extracts(status: Optional[str] = None, db: Session = Depends(get_db)):
    return await automation_contact_utils.get_all_automation_extracts(db, status=status)

@router.post("/", response_model=AutomationContactExtractOut, status_code=status.HTTP_201_CREATED)
async def create_automation_extract(extract: AutomationContactExtractCreate, db: Session = Depends(get_db)):
    return await automation_contact_utils.insert_automation_extract(extract, db)

@router.post("/bulk", response_model=AutomationContactExtractBulkResponse)
async def create_automation_extracts_bulk(
    bulk_data: AutomationContactExtractBulkCreate,
    db: Session = Depends(get_db)
):
    return await automation_contact_utils.insert_automation_extracts_bulk(bulk_data.extracts, db)

@router.delete("/bulk", status_code=status.HTTP_200_OK)
async def delete_automation_extracts_bulk(extract_ids: List[int] = Body(...), db: Session = Depends(get_db)):
    return await automation_contact_utils.delete_automation_extracts_bulk(extract_ids, db)

@router.get("/{extract_id}", response_model=AutomationContactExtractOut)
async def read_automation_extract(extract_id: int, db: Session = Depends(get_db)):
    return await automation_contact_utils.get_automation_extract_by_id(extract_id, db)

@router.put("/{extract_id}", response_model=AutomationContactExtractOut)
async def update_automation_extract(extract_id: int, update_data: AutomationContactExtractUpdate, db: Session = Depends(get_db)):
    return await automation_contact_utils.update_automation_extract(extract_id, update_data, db)

@router.delete("/{extract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_extract(extract_id: int, db: Session = Depends(get_db)):
    await automation_contact_utils.delete_automation_extract(extract_id, db)
    return None
