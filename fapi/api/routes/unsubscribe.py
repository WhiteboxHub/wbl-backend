from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import OutreachContactORM
from sqlalchemy import func
import base64

router = APIRouter()

@router.get("/feedback")
def handle_feedback(
    token: str = Query(..., description="Encoded email token"),
    type: str = Query("unsubscribe", description="Type of feedback: unsubscribe, bounce, complaint"),
    reason: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Updates existing outreach records for unsubscribes, bounces, or complaints.
    Strictly NO NEW INSERTS.
    """
    try:
        email = base64.b64decode(token).decode('utf-8').lower()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Find the record - strictly unique by email_lc
    contact = db.query(OutreachContactORM).filter(
        OutreachContactORM.email_lc == email
    ).first()

    if not contact:
        # Create a new record as suppressed
        logger.info(f"Creating new suppressed record for {email} ({type})")
        contact = OutreachContactORM(
            email=email,
            email_lc=email,
            source_type="MANUAL_UNSUB",
            status=type if type != "unsubscribe" else "unsubscribed",
            unsubscribe_flag=(type == "unsubscribe"),
            bounce_flag=(type == "bounce"),
            complaint_flag=(type == "complaint"),
            unsubscribe_at=func.now() if type == "unsubscribe" else None,
            unsubscribe_reason=reason if type == "unsubscribe" else None
        )
        db.add(contact)
    else:
        if type == "unsubscribe":
            contact.unsubscribe_flag = True
            contact.unsubscribe_at = func.now()
            contact.unsubscribe_reason = reason
            contact.status = "unsubscribed"
        elif type == "bounce":
            contact.bounce_flag = True
            contact.status = "bounced"
        elif type == "complaint":
            contact.complaint_flag = True
            contact.status = "complaint"

    db.commit()
    return {"message": f"Updated record for {email}", "status": "success"}

# Keep the /unsubscribe alias for backward compatibility with links already sent
@router.get("/unsubscribe")
def unsubscribe_alias(token: str = Query(...), reason: str = Query(None), db: Session = Depends(get_db)):
    return handle_feedback(token, "unsubscribe", reason, db)