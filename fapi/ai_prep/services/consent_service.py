from datetime import datetime
from sqlalchemy.orm import Session

from fapi.ai_prep.models import AiPrepConsent
from fapi.ai_prep.schemas import ConsentCreate

def record_candidate_consent(db: Session, candidate_id: int, payload: ConsentCreate) -> AiPrepConsent:
    """Record or update privacy consent preferences for a candidate."""
    consent = AiPrepConsent(
        candidate_id=candidate_id,
        consent_type=payload.consent_type,
        consented=payload.consented,
        consented_at=datetime.utcnow()
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def has_active_consent(db: Session, candidate_id: int, consent_type: str = "VIDEO_ANALYTICS") -> bool:
    """W3-BE1-02: Check if candidate has active, un-revoked consent for VIDEO_ANALYTICS."""
    consent = db.query(AiPrepConsent).filter(
        AiPrepConsent.candidate_id == candidate_id,
        AiPrepConsent.consent_type == consent_type,
        AiPrepConsent.consented == True,
        AiPrepConsent.revoked_at == None
    ).first()
    return consent is not None
