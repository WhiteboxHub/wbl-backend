from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.utils import session_utils
from fapi.db import schemas
from fapi.db.database import get_db

router = APIRouter()


@router.get("/session", response_model=list[schemas.SessionOut])
def read_sessions(
    search_title: str = None,
    db: Session = Depends(get_db)
):
    return session_utils.get_sessions(db, search_title=search_title)


@router.get("/session/{sessionid}", response_model=schemas.SessionOut)
def read_session(sessionid: int, db: Session = Depends(get_db)):
    session = session_utils.get_session(db, sessionid=sessionid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/session", response_model=schemas.SessionOut)
def create_new_session(session: schemas.SessionCreate, db: Session = Depends(get_db)):
    return session_utils.create_session(db, session=session)


@router.put("/session/{sessionid}", response_model=schemas.SessionOut)
def update_existing_session(sessionid: int, session: schemas.SessionUpdate, db: Session = Depends(get_db)):
    updated = session_utils.update_session(db, sessionid, session)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.delete("/session/{sessionid}", response_model=schemas.SessionOut)
def delete_existing_session(sessionid: int, db: Session = Depends(get_db)):
    deleted = session_utils.delete_session(db, sessionid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return deleted
