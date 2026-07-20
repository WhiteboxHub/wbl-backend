from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from fapi.db import models, schemas
from fapi.core.cache import cache_result, invalidate_cache


@cache_result(ttl=300, prefix="sessions")
def get_sessions(db: Session, search_title: str = None, page: int = 1, size: int = 200):
    query = db.query(models.Session).options(selectinload(models.Session.joined_candidates))

    if search_title:
        if search_title.isdigit():
            query = query.filter(models.Session.sessionid == int(search_title))
        else:
            query = query.filter(models.Session.title.ilike(f"%{search_title}%"))

    # pagination FIX
    query = query.order_by(models.Session.sessionid.desc())
    query = query.offset((page - 1) * size).limit(size)

    return query.all()


# =========================
# GET SINGLE SESSION
# =========================
@cache_result(ttl=300, prefix="sessions")
def get_session(db: Session, sessionid: int):
    return db.query(models.Session).filter(models.Session.sessionid == sessionid).first()


def create_session(db: Session, session: schemas.SessionCreate):
    invalidate_cache("sessions")
    invalidate_cache("resources") # Resources often fetch sessions
    invalidate_cache("candidates")

    sess_data = session.dict()
    candidate_ids = sess_data.pop("joined_candidate_ids", None)

    db_session = models.Session(**sess_data)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    if candidate_ids is not None:
        candidates = db.query(models.CandidateORM).filter(models.CandidateORM.id.in_(candidate_ids)).all()
        db_session.joined_candidates = candidates
        db.commit()
        db.refresh(db_session)

    return db_session


def update_session(db: Session, sessionid: int, session: schemas.SessionUpdate):
    invalidate_cache("sessions")
    invalidate_cache("resources")
    invalidate_cache("candidates")
    db_session = db.query(models.Session).filter(models.Session.sessionid == sessionid).first()
    if db_session:
        sess_data = session.dict(exclude_unset=True)
        candidate_ids = sess_data.pop("joined_candidate_ids", None)
        for key, value in sess_data.items():
            setattr(db_session, key, value)
        if candidate_ids is not None:
            candidates = db.query(models.CandidateORM).filter(models.CandidateORM.id.in_(candidate_ids)).all()
            db_session.joined_candidates = candidates
        db.commit()
        db.refresh(db_session)
    return db_session


def delete_session(db: Session, sessionid: int):
    invalidate_cache("sessions")
    invalidate_cache("resources")
    db_session = db.query(models.Session).filter(models.Session.sessionid == sessionid).first()
    if db_session:
        db.delete(db_session)
        db.commit()
    return db_session
