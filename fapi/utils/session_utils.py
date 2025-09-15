from sqlalchemy.orm import Session
from fapi.db import models, schemas


def get_sessions(db: Session, search_title: str = None):
    query = db.query(models.Session)

    if search_title:
        if search_title.isdigit():
            query = query.filter(models.Session.sessionid == int(search_title))
        else:
            query = query.filter(models.Session.title.ilike(f"%{search_title}%"))

    sessions = query.order_by(models.Session.sessionid.desc()).all()
    return sessions


def get_session(db: Session, sessionid: int):
    return db.query(models.Session).filter(models.Session.sessionid == sessionid).first()


def create_session(db: Session, session: schemas.SessionCreate):
    db_session = models.Session(**session.dict())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def update_session(db: Session, sessionid: int, session: schemas.SessionUpdate):
    db_session = db.query(models.Session).filter(models.Session.sessionid == sessionid).first()
    if db_session:
        for key, value in session.dict(exclude_unset=True).items():
            setattr(db_session, key, value)
        db.commit()
        db.refresh(db_session)
    return db_session


def delete_session(db: Session, sessionid: int):
    db_session = db.query(models.Session).filter(models.Session.sessionid == sessionid).first()
    if db_session:
        db.delete(db_session)
        db.commit()
    return db_session
