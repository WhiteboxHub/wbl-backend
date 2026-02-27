import logging
from typing import List
from sqlalchemy.orm import Session
from fapi.db.models import AutomationWorkflowORM
from fapi.db.schemas import AutomationWorkflowCreate, AutomationWorkflowUpdate
from fastapi import HTTPException
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response

logger = logging.getLogger(__name__)

def get_workflow_by_key(db: Session, workflow_key: str):
    workflow = (
        db.query(AutomationWorkflowORM)
        .filter(
            AutomationWorkflowORM.workflow_key == workflow_key,
            AutomationWorkflowORM.status == "active",
        )
        .first()
    )
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"No active workflow found with key '{workflow_key}'",
        )
    return workflow

def create_workflow(db: Session, workflow: AutomationWorkflowCreate):
    db_workflow = AutomationWorkflowORM(**workflow.model_dump())
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

def update_workflow(db: Session, workflow_id: int, workflow: AutomationWorkflowUpdate):
    db_workflow = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Automation Workflow not found")
    
    update_data = workflow.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

def get_all_workflows(db: Session) -> List[AutomationWorkflowORM]:
    return db.query(AutomationWorkflowORM).all()

def delete_workflow(db: Session, workflow_id: int):
    db_workflow = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Automation Workflow not found")
    db.delete(db_workflow)
    db.commit()
    return {"message": "Automation Workflow deleted"}

def get_automation_workflows_version(db: Session) -> Response:
    return generate_version_for_model(db, AutomationWorkflowORM)

from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from fapi.db.models import (
    AutomationWorkflowORM,
    AutomationWorkflowScheduleORM,
    EmailSMTPCredentialsORM,
    JobAutomationKeywordORM
)
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def get_workflow_execution_bundle(db: Session, workflow_id: int):
    """
    Fetches the complete execution bundle for a workflow including:
    - Workflow config (with eagerly loaded template and delivery engine)
    - Schedule config
    - All active SMTP credentials (if applicable)
    - Active Job Automation Keywords (filtered by source)
    """
    
    # 1. Fetch Workflow with Template and Delivery Engine
    workflow_orm = (
        db.query(AutomationWorkflowORM)
        .options(
            joinedload(AutomationWorkflowORM.template),
            joinedload(AutomationWorkflowORM.delivery_engine)
        )
        .filter(AutomationWorkflowORM.id == workflow_id)
        .first()
    )
    
    if not workflow_orm:
        raise HTTPException(status_code=404, detail=f"Workflow with ID {workflow_id} not found")
        
    # 2. Fetch Schedule
    schedule_orm = (
        db.query(AutomationWorkflowScheduleORM)
        .filter(AutomationWorkflowScheduleORM.automation_workflow_id == workflow_id)
        .first()
    )
    
    # 3. Fetch SMTP Credentials (All Active)
    # Only fetch if it's an email sender workflow to save DB cycles
    smtp_credentials_orms = None
    if workflow_orm.workflow_type == "email_sender":
        smtp_credentials_orms = (
            db.query(EmailSMTPCredentialsORM)
            .filter(EmailSMTPCredentialsORM.is_active == True)
            .all()
        )
        
    # 4. Fetch Job Automation Keywords (Active, filtered by source)
    # Determine source mapping based on workflow type (e.g. email_extractor needs email_extractor keywords)
    source_filter = workflow_orm.workflow_type
    
    keyword_orms = (
        db.query(JobAutomationKeywordORM)
        .filter(
            JobAutomationKeywordORM.is_active == True,
            JobAutomationKeywordORM.source == source_filter
        )
        .all()
    )
    
    # 5. Metadata
    execution_metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "valid_for_seconds": 300
    }
    
    # Assembly
    bundle = {
        "workflow": workflow_orm,
        "schedule": schedule_orm,
        "template": workflow_orm.template,
        "delivery_engine": workflow_orm.delivery_engine,
        "smtp_credentials": smtp_credentials_orms,
        "keywords": keyword_orms,
        "execution_metadata": execution_metadata
    }
    
    return bundle

