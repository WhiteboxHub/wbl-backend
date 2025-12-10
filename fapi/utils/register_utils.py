
# wbl-backend/fapi/utils/register_utils.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from fapi.db.models import AuthUserORM, LeadORM
from fapi.db.schemas import UserRegistration

def combine_notes(experience: str, education: str, specialization: str, referby: str) -> str:
    parts = [
        f"Experience: {experience}" if experience else None,
        f"Education: {education}" if education else None,
        f"Specialization: {specialization}" if specialization else None,
        f"Referby: {referby}" if referby else None
    ]
    return "; ".join(p for p in parts if p)

def create_user_and_lead(db: Session, user: UserRegistration):
    uname = user.uname.lower().strip()
    # Check duplicates
    if db.query(AuthUserORM).filter_by(uname=uname).first():
        raise HTTPException(status_code=409, detail="User already exists. Please use a different email")
    if db.query(LeadORM).filter_by(email=uname).first():
        raise HTTPException(status_code=400, detail="Lead already exists. Please use a different email.")

    full_name = f"{user.firstname or ''} {user.lastname or ''}".strip()
    notes_text = combine_notes(user.experience, user.education, user.specialization, user.referby)

    # Create Auth User
    new_user = AuthUserORM(
        uname=uname,
        passwd=user.passwd,
        team=user.team,
        status=user.status or "inactive",
        logincount=user.logincount or 0,
        fullname=full_name.lower(),
        address=user.address,
        phone=user.phone,
        state=user.state,
        zip=user.zip,
        city=user.city,
        country=user.country,
        message=user.message,
        registereddate=user.registereddate,
        enddate=user.enddate or "1990-01-01",
        googleId=user.googleId,
        reset_token=user.reset_token,
        token_expiry=user.token_expiry,
        role=user.role,
        visa_status=user.visa_status,
        notes=notes_text
    )

    # Create Lead
    new_lead = LeadORM(
        full_name=full_name,
        phone=user.phone,
        email=uname,
        status=user.status or "open",
        address=user.address,
        workstatus=user.visa_status,
        notes=notes_text,
        moved_to_candidate=False,
        entry_date=datetime.utcnow(),
        last_modified=datetime.utcnow()
    )

    db.add(new_user)
    db.add(new_lead)
    db.commit()
