import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import UploadPayload, DownloadPayload
from fapi.utils import sync_cli_utils

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sync_cli",
    tags=["JobCLI Sync"],
)


@router.post("/knowledge_sync")
def upload_knowledge(
    payload: UploadPayload,
    db: Session = Depends(get_db)
):
    try:
        return sync_cli_utils.aggregate_knowledge(db, payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating knowledge: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/knowledge_updates", response_model=DownloadPayload)
def download_updates(
    current_version: str,
    db: Session = Depends(get_db)
):
    try:
        return sync_cli_utils.get_knowledge_updates(db, current_version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching knowledge updates: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
