from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.ai_talent_outreach_model import AITalentOutreachORM
from fapi.db.schemas import AITalentOutreachCreate, AITalentOutreachResponse
import logging

router = APIRouter()
logger = logging.getLogger("wbl.ai_talent_outreach")

@router.post("/ai-talent-outreach", response_model=AITalentOutreachResponse)
async def create_ai_talent_outreach(
    data: AITalentOutreachCreate,
    db: Session = Depends(get_db)
):
    try:
        # Convert empty strings to None for optional/Enum fields to avoid MySQL truncation errors
        dump = data.model_dump()
        for key, value in dump.items():
            if value == "":
                dump[key] = None
                
        # Handle duplicate submission: Check if email already exists
        existing_item = db.query(AITalentOutreachORM).filter(AITalentOutreachORM.email == data.email).first()
        
        if existing_item:
            logger.info(f"Duplicate submission for email: {data.email}. Updating existing record.")
            for key, value in dump.items():
                setattr(existing_item, key, value)
            db.commit()
            db.refresh(existing_item)
            return existing_item
        else:
            db_item = AITalentOutreachORM(**dump)
            db.add(db_item)
            db.commit()
            db.refresh(db_item)
            return db_item
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_ai_talent_outreach: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
