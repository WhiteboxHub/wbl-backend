from sqlalchemy.orm import Session
from fastapi import HTTPException
from fapi.db.models import AuthUserORM, LeadORM
from datetime import datetime


def get_google_user_by_email(db: Session, email: str):
    return db.query(AuthUserORM).filter(AuthUserORM.uname == email).first()


def insert_google_user_db(db: Session, email: str, name: str, google_id: str):
    try:
        new_user = AuthUserORM(
            uname=email,
            fullname=name,
            googleId=google_id,
            passwd="google_register",
            status="inactive",
        )
        db.add(new_user)

        new_lead = LeadORM(
            full_name=name,
            email=email,
            entry_date=datetime.utcnow(),
            last_modified=datetime.utcnow(),
            massemail_unsubscribe=False,
            massemail_email_sent=False,
            moved_to_candidate=False
        )
        db.add(new_lead)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error inserting user: {str(e)}")
