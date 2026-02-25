from fastapi import APIRouter, Depends, HTTPException, status, Body, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.schemas import (
    AutomationContactExtractCreate, 
    AutomationContactExtractUpdate, 
    AutomationContactExtractOut,
    AutomationContactExtractBulkCreate,
    AutomationContactExtractBulkResponse,
    CheckEmailsRequest,
    CheckEmailsResponse,
)
from fapi.utils import automation_contact_utils
from fapi.db.models import AutomationContactExtractORM
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter(tags=["Automation Extracts"])

security = HTTPBearer()

@router.head("/automation-extracts")
@router.head("/automation-extracts/paginated")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, AutomationContactExtractORM)

def check_automation_extracts_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(AutomationContactExtractORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        AutomationContactExtractORM.id,
                        func.coalesce(AutomationContactExtractORM.full_name, ''),
                        func.coalesce(AutomationContactExtractORM.email, ''),
                        func.coalesce(AutomationContactExtractORM.status, ''),
                        func.coalesce(AutomationContactExtractORM.source_email, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

@router.get("/automation-extracts", response_model=List[AutomationContactExtractOut])
async def read_automation_extracts(
    status: Optional[str] = None,
    source_email: Optional[str] = None,
    email_invalid: Optional[bool] = None,
    domain_invalid: Optional[bool] = None,
    mailbox_invalid: Optional[bool] = None,
    bounced_flag: Optional[bool] = None,
    unsubscribed_flag: Optional[bool] = None,
    complained_flag: Optional[bool] = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.get_all_automation_extracts(
        db, status=status, source_email=source_email
    )

@router.get("/automation-extracts/paginated")
def read_automation_extracts_paginated(
    page: int = 1,
    page_size: int = 5000,
    status: Optional[str] = None,
    email_invalid: Optional[bool] = None,
    domain_invalid: Optional[bool] = None,
    mailbox_invalid: Optional[bool] = None,
    bounced_flag: Optional[bool] = None,
    unsubscribed_flag: Optional[bool] = None,
    complained_flag: Optional[bool] = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get automation extracts with page-based pagination and optional filters"""
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    filters = dict(
        status=status,
        email_invalid=email_invalid,
        domain_invalid=domain_invalid,
        mailbox_invalid=mailbox_invalid,
        bounced_flag=bounced_flag,
        unsubscribed_flag=unsubscribed_flag,
        complained_flag=complained_flag,
    )
    total_records = automation_contact_utils.count_automation_extracts(db, **filters)
    data = automation_contact_utils.get_automation_extracts_paginated(db, skip=skip, limit=page_size, **filters)
    total_pages = max(1, (total_records + page_size - 1) // page_size)
    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

@router.post("/automation-extracts", response_model=AutomationContactExtractOut, status_code=status.HTTP_201_CREATED)
async def create_automation_extract(
    extract: AutomationContactExtractCreate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.insert_automation_extract(extract, db)

@router.post("/automation-extracts/bulk", response_model=AutomationContactExtractBulkResponse)
async def create_automation_extracts_bulk(
    bulk_data: AutomationContactExtractBulkCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.insert_automation_extracts_bulk(bulk_data.extracts, db)

@router.delete("/automation-extracts/bulk", status_code=status.HTTP_200_OK)
async def delete_automation_extracts_bulk(
    extract_ids: List[int] = Body(...), 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.delete_automation_extracts_bulk(extract_ids, db)

@router.get("/automation-extracts/{extract_id}", response_model=AutomationContactExtractOut)
async def read_automation_extract(
    extract_id: int, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.get_automation_extract_by_id(extract_id, db)

@router.put("/automation-extracts/{extract_id}", response_model=AutomationContactExtractOut)
async def update_automation_extract(
    extract_id: int, 
    update_data: AutomationContactExtractUpdate, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return await automation_contact_utils.update_automation_extract(extract_id, update_data, db)

@router.delete("/automation-extracts/{extract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_extract(
    extract_id: int, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    await automation_contact_utils.delete_automation_extract(extract_id, db)
    return None


@router.post("/automation-extracts/check-emails", response_model=CheckEmailsResponse)
async def check_existing_emails(
    payload: CheckEmailsRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Check which of the provided emails already exist in automation_contact_extracts.
    Used for global deduplication before inserting.
    """
    found = await automation_contact_utils.check_existing_emails_bulk(payload.emails, db)
    return CheckEmailsResponse(existing_emails=found)
