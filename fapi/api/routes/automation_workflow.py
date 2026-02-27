from fastapi import Security, APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import logging
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import AutomationWorkflow, AutomationWorkflowCreate, AutomationWorkflowUpdate
from fapi.utils import automation_workflow_utils
from fapi.utils.automation_workflow_utils import (
    get_workflow_by_key,
    create_workflow,
    update_workflow,
    get_automation_workflows_version,
    get_all_workflows,
    delete_workflow
)

from fapi.db.models import AutomationWorkflowORM
from fapi.db.schemas import AutomationWorkflow, AutomationWorkflowCreate, AutomationWorkflowUpdate, ExecutionBundleResponse
from fapi.utils.permission_gate import enforce_access
from fapi.utils.automation_workflow_utils import get_workflow_execution_bundle


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automation-workflow", tags=["Automation Workflow"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_automation_workflows_version(db)

@router.get("/", response_model=List[AutomationWorkflow])
def get_automation_workflows(db: Session = Depends(get_db)):
    return automation_workflow_utils.get_all_workflows(db)


@router.get("/by-key/{workflow_key}", response_model=AutomationWorkflow)
def get_automation_workflow_by_key(workflow_key: str, db: Session = Depends(get_db)):
    """Fetch an active workflow configuration by its unique workflow_key."""
    workflow = get_workflow_by_key(db, workflow_key)
    logger.info("Fetched workflow config for key='%s' id=%s", workflow_key, workflow.id)
    return workflow

@router.get("/{workflow_id}/execution-bundle", response_model=ExecutionBundleResponse)
def get_automation_workflow_execution_bundle(workflow_id: int, db: Session = Depends(get_db)):
    """Fetch all necessary configurations in a single atomic bundle for workflow execution."""
    bundle = get_workflow_execution_bundle(db, workflow_id)
    return bundle

@router.post("/", response_model=AutomationWorkflow, status_code=status.HTTP_201_CREATED)
def create_automation_workflow(workflow: AutomationWorkflowCreate, db: Session = Depends(get_db)):
    return create_workflow(db, workflow)

@router.put("/{workflow_id}", response_model=AutomationWorkflow)
def update_automation_workflow(workflow_id: int, workflow: AutomationWorkflowUpdate, db: Session = Depends(get_db)):
    return update_workflow(db, workflow_id, workflow)

@router.delete("/{workflow_id}")
def delete_automation_workflow(workflow_id: int, db: Session = Depends(get_db)):
    return automation_workflow_utils.delete_workflow(db, workflow_id)
