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
