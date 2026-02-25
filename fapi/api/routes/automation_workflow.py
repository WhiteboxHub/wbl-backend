from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.models import AutomationWorkflowORM
from fapi.db.schemas import AutomationWorkflow, AutomationWorkflowCreate, AutomationWorkflowUpdate
from fapi.utils.permission_gate import enforce_access
import hashlib
from fastapi import Response
from sqlalchemy import func

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automation-workflow", tags=["Automation Workflow"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, AutomationWorkflowORM)

def check_workflow_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(AutomationWorkflowORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        AutomationWorkflowORM.id,
                        func.coalesce(AutomationWorkflowORM.name, ''),
                        func.coalesce(AutomationWorkflowORM.workflow_key, ''),
                        func.coalesce(AutomationWorkflowORM.status, '')
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
