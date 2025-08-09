from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from typing import Optional, List
# from fapi.db.database import get_db
from fapi.utils.talent_utils import get_talent_search_filtered
from fapi.db.schemas import TalentSearch

router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/talent_search", response_model=List[TalentSearch])
def get_talent_search(
    role: Optional[str] = None,
    experience: Optional[int] = None,
    location: Optional[str] = None,
    availability: Optional[str] = None,
    skills: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        candidates = get_talent_search_filtered(db, role, experience, location, availability, skills)
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")
