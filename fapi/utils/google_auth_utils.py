# wbl-backend\fapi\utils\google_auth_utils.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fapi.db.models import AuthUser,Lead


def get_google_user_by_email(db: Session, email: str):
    user = db.query(AuthUser).filter(AuthUser.uname == email).first()
    return user

def insert_google_user_db(db: Session, email: str, name: str, google_id: str):
    try:
        new_user = AuthUser(
            uname=email,
            fullname=name,
            googleId=google_id,
            passwd="google_register",
            status="inactive",
        )
        db.add(new_user)
        print("Creating Lead instance:", type(Lead))
        print("Lead module:", Lead.__module__)

        new_lead = Lead(full_name=name, email=email)
        db.add(new_lead)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error inserting user: {str(e)}")