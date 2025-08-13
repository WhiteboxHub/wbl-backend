from sqlalchemy.orm import Session
from fapi.db.models import LeadORM, UnsubscribeUser


def unsubscribe_lead_user(db: Session, email: str) -> (bool, str):
    lead = db.query(LeadORM).filter(LeadORM.email == email).first()

    if not lead:
        return False, "User not found"

    if lead.massemail_unsubscribe:
        return True, "Already unsubscribed"

    lead.massemail_unsubscribe = True
    db.commit()

    return True, "Successfully unsubscribed"




def unsubscribe_user(db: Session, email: str) -> (bool, str):
    record = db.query(UnsubscribeUser).filter(UnsubscribeUser.email == email).first()

    if not record:
        return False, "User not found"

    if record.remove == 'Y':
        return True, "Already unsubscribed"

    record.remove = 'Y'
    db.commit()

    return True, "Successfully unsubscribed"
