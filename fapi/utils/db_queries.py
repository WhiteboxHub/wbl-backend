# fapi/utils/db_queries.py
from sqlalchemy.orm import Session
from fapi.db.models import AuthUserORM, CandidateORM

def get_user_by_username(db: Session, uname: str):
    return db.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()

def fetch_candidate_id_and_status_by_email(db: Session, email: str):
    return db.query(CandidateORM.id.label("candidateid"), CandidateORM.status).filter(CandidateORM.email == email).first()
