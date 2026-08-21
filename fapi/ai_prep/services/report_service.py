from typing import Optional
from sqlalchemy.orm import Session
from fapi.ai_prep.models import AiPrepReport

def fetch_assessment_report(db: Session, assessment_id: int) -> Optional[AiPrepReport]:
    """Retrieve evaluation report by assessment session ID."""
    return db.query(AiPrepReport).filter(AiPrepReport.assessment_id == assessment_id).first()
