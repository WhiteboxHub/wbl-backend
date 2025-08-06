from sqlalchemy.orm import Session
from fapi.db.models import TalentSearch
from typing import List, Dict

def get_talent_search_filtered(
    db: Session,
    role: str = None,
    experience: int = None,
    location: str = None,
    availability: str = None,
    skills: str = None
) -> List[TalentSearch]:
    query = db.query(TalentSearch)

    if role:
        query = query.filter(TalentSearch.role == role)
    if experience:
        query = query.filter(TalentSearch.experience >= experience)
    if location:
        query = query.filter(TalentSearch.location == location)
    if availability:
        query = query.filter(TalentSearch.availability == availability)
    if skills:
        query = query.filter(TalentSearch.skills.like(f"%{skills}%"))

    return query.all()
