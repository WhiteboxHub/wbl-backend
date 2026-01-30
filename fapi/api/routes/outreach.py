from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime
from jose import jwt, JWTError
from pydantic import BaseModel
from fapi.db.database import get_db
from fapi.db.outreach_models import OutreachContactORM
from fapi.core.config import SECRET_KEY, ALGORITHM
import logging

UNSUBSCRIBE_ALGORITHM = ALGORITHM

router = APIRouter()
logger = logging.getLogger("wbl.outreach")

from typing import Optional

class UnsubscribeRequest(BaseModel):
    token: Optional[str] = None
    email: Optional[str] = None

class UnsubscribeResponse(BaseModel):
    status: str
    message: str

def verify_unsubscribe_token(token: str) -> str:
    """
    Decodes the token and returns the email.
    Assumes token payload has 'sub' as email.
    """
    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[UNSUBSCRIBE_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token: missing email")
        return email
    except JWTError as e:
        logger.error(f"Unsubscribe token error: {e}")
        raise HTTPException(status_code=400, detail="Invalid or expired token")

@router.post("/outreach/unsubscribe", response_model=UnsubscribeResponse)
def unsubscribe(
    request: UnsubscribeRequest,
    db: Session = Depends(get_db)
):
    if request.token:
        email = verify_unsubscribe_token(request.token)
    elif request.email:
        email = request.email.strip()
    else:
        raise HTTPException(status_code=400, detail="Either token or email is required")

    email_lc = email.lower()
    
    contact = db.query(OutreachContactORM).filter(OutreachContactORM.email_lc == email_lc).first()
    
    if not contact:

        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.unsubscribe_flag:
        return {"status": "success", "message": "You are already unsubscribed."}
    
    logger.info(f"Unsubscribing contact: {email}")
        
    contact.unsubscribe_flag = True
    contact.unsubscribe_at = datetime.utcnow()
    contact.unsubscribe_reason = "User requested via API"
    contact.status = "unsubscribed"
    contact.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"status": "success", "message": "You have been unsubscribed successfully"}

