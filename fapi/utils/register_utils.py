# fapi/utils/register_user.py

from sqlalchemy.orm import Session
from fastapi import HTTPException
from fapi.db.models import AuthUserORM, LeadORM
from fapi.db.schemas import UserRegistration

def clean_datetime_fields(value):
    if value and 'T' in value:
        return value.replace('T', ' ').split('.')[0]
    return value or None

def combine_notes(experience: str, education: str, specialization: str) -> str:
    parts = [f"Experience: {experience}", f"Education: {education}", f"Specialization: {specialization}"]
    return "; ".join(p for p in parts if p and p.strip())

def create_user_and_lead(db: Session, user: UserRegistration):
    uname = user.uname.lower().strip()

    if db.query(AuthUserORM).filter_by(uname=uname).first():
        raise HTTPException(status_code=409, detail="User already exists.")

    full_name = f"{user.firstname or ''} {user.lastname or ''}".strip().lower()

    # Format notes
    notes_text = combine_notes(user.experience, user.education, user.specialization)

    new_user = AuthUser(
        uname=uname,
        passwd=user.passwd,  # Already hashed in main
        team=user.team,
        status="inactive",
        lastlogin=clean_datetime_fields(user.lastlogin),
        logincount=user.logincount or 0,
        fullname=full_name,
        phone=user.phone,
        address=user.address,
        city=user.city,
        zip=(user.Zip or '').lower(),
        country=user.country,
        message=user.message,
        registereddate=clean_datetime_fields(user.registereddate),
        level3date=clean_datetime_fields(user.level3date),
        visa_status=user.visa_status,
        notes=notes_text
    )

    new_lead = Lead(
        full_name=full_name,
        phone=user.phone,
        email=uname,
        address=user.address,
        workstatus=user.visa_status,  # workauthorization maps here
        notes=notes_text
    )

    db.add(new_user)
    db.add(new_lead)
    db.commit()
