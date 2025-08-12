from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.schemas import UnsubscribeRequest, UnsubscribeResponse
from fapi.utils.unsubscribe_utils import unsubscribe_lead_user, unsubscribe_user
from fapi.db.database import SessionLocal


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.put("/api/leads/unsubscribe", response_model=UnsubscribeResponse)
def unsubscribe(request: UnsubscribeRequest, db: Session = Depends(get_db)):
    status, message = unsubscribe_lead_user(db, request.email)
    if status:
        return {"message": message}
    else:
        raise HTTPException(status_code=404, detail=message)



@router.put("/api/unsubscribe", response_model=UnsubscribeResponse)
def unsubscribe(request: UnsubscribeRequest, db: Session = Depends(get_db)):
    status, message = unsubscribe_user(db, request.email)
    if status:
        return {"message": message}
    else:
        raise HTTPException(status_code=404, detail=message)