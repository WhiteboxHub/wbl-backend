# fapi/utils/db_queries.py
from sqlalchemy.orm import Session
from fapi.utils.auth_utils import hash_password
from fapi.db.models import AuthUserORM, CandidateORM
from fapi.db.database import SessionLocal
def get_user_by_username(db: Session, uname: str):
    return db.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()

def fetch_candidate_id_and_status_by_email(db: Session, email: str):
    return db.query(CandidateORM.id.label("candidateid"), CandidateORM.status).filter(CandidateORM.email == email).first()


def get_user_by_username_sync(uname: str):
    with SessionLocal() as session:
        return session.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()

def update_user_password(db: Session, uname: str, new_password: str):
    user = db.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()
    if not user:
        return None
    user.passwd = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user