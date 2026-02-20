import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import AutomationWorkflowORM
from fapi.db.schemas import AutomationWorkflow, AutomationWorkflowCreate, AutomationWorkflowUpdate
from fapi.utils.permission_gate import enforce_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automation-workflow", tags=["Automation Workflow"])

@router.get("/", response_model=List[AutomationWorkflow])
def get_automation_workflows(db: Session = Depends(get_db)):
    return db.query(AutomationWorkflowORM).all()


@router.get("/by-key/{workflow_key}", response_model=AutomationWorkflow)
def get_automation_workflow_by_key(workflow_key: str, db: Session = Depends(get_db)):
    """Fetch an active workflow configuration by its unique workflow_key."""
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
    logger.info("Fetched workflow config for key='%s' id=%s", workflow_key, workflow.id)
    return workflow

@router.post("/", response_model=AutomationWorkflow, status_code=status.HTTP_201_CREATED)
def create_automation_workflow(workflow: AutomationWorkflowCreate, db: Session = Depends(get_db)):
    db_workflow = AutomationWorkflowORM(**workflow.model_dump())
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@router.put("/{workflow_id}", response_model=AutomationWorkflow)
def update_automation_workflow(workflow_id: int, workflow: AutomationWorkflowUpdate, db: Session = Depends(get_db)):
    db_workflow = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Automation Workflow not found")
    
    update_data = workflow.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@router.delete("/{workflow_id}")
def delete_automation_workflow(workflow_id: int, db: Session = Depends(get_db)):
    db_workflow = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Automation Workflow not found")
    db.delete(db_workflow)
    db.commit()
    return {"message": "Automation Workflow deleted"}
