from sqlalchemy.orm import Session
from fapi.db.models import AuthUserORM

def get_user_by_username(db: Session, uname: str):
    return db.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()
