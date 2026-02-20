"""
automation_contact_extract.py
==============================
API routes for the automation_contact_extracts table.

Endpoints:
  POST /api/automation-contact-extracts/bulk        — bulk INSERT IGNORE
  POST /api/automation-contact-extracts/check-emails — return which emails already exist
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from fapi.db.database import get_db
from fapi.db.models import AutomationContactExtractORM
from fapi.db.schemas import (
    AutomationContactExtractBulkCreate,
    AutomationContactExtractBulkResponse,
    CheckEmailsRequest,
    CheckEmailsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/automation-contact-extracts",
    tags=["Automation Contact Extracts"],
)


@router.post("/bulk", response_model=AutomationContactExtractBulkResponse)
def bulk_insert_contact_extracts(
    payload: AutomationContactExtractBulkCreate,
    db: Session = Depends(get_db),
):
    """
    Bulk-insert contacts into automation_contact_extracts.
    Duplicate rows (by unique key on email/linkedin_id) are silently skipped
    via INSERT IGNORE, matching the previous raw SQL behaviour.
    """
    contacts = payload.contacts
    if not contacts:
        return AutomationContactExtractBulkResponse(inserted=0, skipped=0, total=0)

    rows = [c.model_dump() for c in contacts]

    try:
        stmt = mysql_insert(AutomationContactExtractORM).values(rows)
        stmt = stmt.prefix_with("IGNORE")  # INSERT IGNORE
        result = db.execute(stmt)
        db.commit()

        inserted = result.rowcount
        skipped = len(rows) - inserted
        logger.info(
            "automation_contact_extracts bulk: %d rows → %d inserted, %d skipped (duplicates)",
            len(rows), inserted, skipped,
        )
        return AutomationContactExtractBulkResponse(
            inserted=inserted,
            skipped=skipped,
            total=len(rows),
        )
    except Exception as e:
        db.rollback()
        logger.error("Bulk insert into automation_contact_extracts failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Bulk insert failed: {str(e)}")


@router.post("/check-emails", response_model=CheckEmailsResponse)
def check_existing_emails(
    payload: CheckEmailsRequest,
    db: Session = Depends(get_db),
):
    """
    Check which of the provided emails already exist in automation_contact_extracts.
    Returns the subset that is already present — used for global deduplication before inserting.
    """
    if not payload.emails:
        return CheckEmailsResponse(existing_emails=[])

    normalised = [e.strip().lower() for e in payload.emails if e]
    if not normalised:
        return CheckEmailsResponse(existing_emails=[])

    try:
        rows = (
            db.query(AutomationContactExtractORM.email)
            .filter(AutomationContactExtractORM.email.in_(normalised))
            .all()
        )
        found = [row[0].strip().lower() for row in rows if row[0]]
        logger.info("check-emails: %d queried → %d already exist", len(normalised), len(found))
        return CheckEmailsResponse(existing_emails=found)
    except Exception as e:
        logger.error("check-emails query failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Email check failed: {str(e)}")
