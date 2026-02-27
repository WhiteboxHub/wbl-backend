from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import CandidateMarketingORM, AutomationWorkflowScheduleORM
from fapi.db.schemas import CandidateMarketingOut
from fapi.utils.permission_gate import enforce_access

router = APIRouter()

@router.get("/eligible-candidates", response_model=List[CandidateMarketingOut])
def get_eligible_candidates(db: Session = Depends(get_db)):
    """Fetch candidates where run_weekly_flow is 1"""
    candidates = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.run_weekly_workflow == 1).all()
    return candidates

@router.post("/reset/{candidate_id}")
def reset_candidate_workflow(candidate_id: int, db: Session = Depends(get_db)):
    """Reset the run_weekly_workflow flag for a candidate"""
    candidate = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate marketing record not found")
    
    candidate.run_weekly_workflow = 0
    db.commit()
    return {"message": f"Successfully reset workflow flag for candidate {candidate_id}"}
