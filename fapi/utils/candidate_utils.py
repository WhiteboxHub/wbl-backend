# wbl-backend/fapi/utils/candidate_utils.py
from sqlalchemy.orm import Session,joinedload,contains_eager
from fapi.db.database import SessionLocal
from fapi.db.models import CandidateORM, CandidatePlacementORM,CandidateMarketingORM,CandidateInterviewNew,CandidatePreparation
from fapi.db.schemas import CandidateMarketingCreate,CandidateInterviewBase, CandidateInterviewCreate, CandidateInterviewOut, CandidateInterviewUpdate,CandidatePreparationCreate, CandidatePreparationUpdate
from fastapi import HTTPException
from typing import List, Dict



def get_all_candidates_paginated(page: int = 1, limit: int = 100) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidateORM).count()
        results = (
            db.query(CandidateORM)
            .order_by(CandidateORM.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        data = [r.__dict__ for r in results]
        for item in data:
            item.pop('_sa_instance_state', None)
        return {"page": page, "limit": limit, "total": total, "data": data}
    finally:
        db.close()


def get_candidate_by_id(candidate_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        data = candidate.__dict__.copy()
        data.pop('_sa_instance_state', None)
        return data
    finally:
        db.close()


def create_candidate(candidate_data: dict) -> int:
    db: Session = SessionLocal()
    try:
        if "email" in candidate_data and candidate_data["email"]:
            candidate_data["email"] = candidate_data["email"].lower()

        new_candidate = CandidateORM(**candidate_data)
        db.add(new_candidate)
        db.commit()
        db.refresh(new_candidate)
        return new_candidate.id
    finally:
        db.close()


def update_candidate(candidate_id: int, candidate_data: dict):
    db: Session = SessionLocal()
    try:
        if "email" in candidate_data and candidate_data["email"]:
            candidate_data["email"] = candidate_data["email"].lower()

        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        for key, value in candidate_data.items():
            setattr(candidate, key, value)

        db.commit()
    finally:
        db.close()


def delete_candidate(candidate_id: int):
    db: Session = SessionLocal()
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        db.delete(candidate)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------Marketing----------------------------

def get_all_marketing_records(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidateMarketingORM).count()
        results = (
            db.query(CandidateMarketingORM)
            .options(joinedload(CandidateMarketingORM.candidate))  # LOAD candidate
            .order_by(CandidateMarketingORM.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        data = [r.__dict__ for r in results]
        for item in data:
            item.pop('_sa_instance_state', None)
        return {"page": page, "limit": limit, "total": total, "data": results}
    finally:
        db.close()


def get_marketing_by_id(record_id: int):
    db: Session = SessionLocal()
    try:
        record = (
            db.query(CandidateMarketingORM)
            .options(joinedload(CandidateMarketingORM.candidate))  # Load candidate
            .filter(CandidateMarketingORM.id == record_id)        # Apply filter
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        return record  # Return ORM object directly; FastAPI + Pydantic will serialize it
    finally:
        db.close()

def create_marketing(payload: CandidateMarketingCreate) -> Dict:
    db: Session = SessionLocal()
    try:
        new_entry = CandidateMarketingORM(**payload.dict())
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry.__dict__
    finally:
        db.close()

def update_marketing(record_id: int, payload: CandidateMarketingCreate) -> Dict:
    db: Session = SessionLocal()
    try:
        record = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
        return record.__dict__
    finally:
        db.close()

def delete_marketing(record_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        record = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        db.delete(record)
        db.commit()
        return {"message": "Marketing record deleted successfully"}
    finally:
        db.close()



# ----------------------------------------------------Candidate_Placement---------------------------------



def get_all_placements(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidatePlacementORM).count()

        results = (
            db.query(
                CandidatePlacementORM,
                CandidateORM.full_name.label("candidate_name")  #
            )
            .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
            .order_by(CandidatePlacementORM.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        data = []
        for placement, candidate_name in results:
            record = placement.__dict__.copy()
            record["candidate_name"] = candidate_name
            record.pop('_sa_instance_state', None)
            data.append(record)

        return {"page": page, "limit": limit, "total": total, "data": data}
    finally:
        db.close()


def get_placement_by_id(placement_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        result = (
            db.query(
                CandidatePlacementORM,
                CandidateORM.full_name.label("candidate_name")  # fixed here
            )
            .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
            .filter(CandidatePlacementORM.id == placement_id)
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Placement not found")

        placement, candidate_name = result
        data = placement.__dict__.copy()
        data["candidate_name"] = candidate_name
        data.pop('_sa_instance_state', None)
        return data
    finally:
        db.close()


def create_placement(payload):
    db: Session = SessionLocal()
    try:
        new_entry = CandidatePlacementORM(**payload.dict())
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry.__dict__
    finally:
        db.close()


def update_placement(placement_id: int, payload):
    db: Session = SessionLocal()
    try:
        placement = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.id == placement_id).first()
        if not placement:
            raise HTTPException(status_code=404, detail="Placement not found")
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(placement, key, value)
        db.commit()
        db.refresh(placement)
        return placement.__dict__
    finally:
        db.close()


def delete_placement(placement_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        placement = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.id == placement_id).first()
        if not placement:
            raise HTTPException(status_code=404, detail="Placement not found")
        db.delete(placement)
        db.commit()
        return {"message": "Placement deleted successfully"}
    finally:
        db.close()


# -----------------------------------------------------Candidate_Interviews------------------------------------------------------

def create_candidate_interview(db: Session, interview: CandidateInterviewCreate):
    data = interview.dict()

    # Normalize interviewer_emails to lowercase if provided
    if data.get("interviewer_emails"):
        data["interviewer_emails"] = ",".join(
            [email.strip().lower() for email in data["interviewer_emails"].split(",")]
        )

    db_obj = CandidateInterviewNew(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_candidate_interviews(db: Session, skip: int = 0, limit: int = 100):
    return db.query(CandidateInterviewNew).options(contains_eager(CandidateInterviewNew.candidate)) .join(CandidateORM, CandidateInterviewNew.candidate_id == CandidateORM.id).offset(skip).limit(limit).all()


def get_candidate_interview(db: Session, interview_id: int):
    return db.query(CandidateInterviewNew).options(joinedload(CandidateInterviewNew.candidate)).filter(CandidateInterviewNew.id == interview_id).first()


def update_candidate_interview(db: Session, interview_id: int, updates: CandidateInterviewUpdate):
    db_obj = db.query(CandidateInterviewNew).options(joinedload(CandidateInterviewNew.candidate)) .join(CandidateORM, CandidateInterviewNew.candidate_id == CandidateORM.id).filter(CandidateInterviewNew.id == interview_id).first()
    if not db_obj:
        return None

    update_data = updates.dict(exclude_unset=True)

    # Normalize interviewer_emails to lowercase if provided
    if update_data.get("interviewer_emails"):
        update_data["interviewer_emails"] = ",".join(
            [email.strip().lower() for email in update_data["interviewer_emails"].split(",")]
        )

    for key, value in update_data.items():
        setattr(db_obj, key, value)

    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_candidate_interview(db: Session, interview_id: int):
    db_obj = db.query(CandidateInterviewNew).filter(CandidateInterviewNew.id == interview_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj

# -------------------Candidate_Preparation-------------

def create_candidate_preparation(db: Session, prep_data: CandidatePreparationCreate):
    if prep_data.email:
        prep_data.email = prep_data.email.lower()
    db_prep = CandidatePreparation(**prep_data.dict())
    db.add(db_prep)
    db.commit()
    db.refresh(db_prep)
    return db_prep

# def get_candidate_preparation(db: Session, prep_id: int):
#     return db.query(CandidatePreparation).options(joinedload(CandidatePreparation.candidate))  # LOAD candidate  # ADDED: join to fetch candidate.filter(CandidatePreparation.id == prep_id).first()

# def get_all_preparations(db: Session, skip: int = 0, limit: int = 100):
#     return db.query(CandidatePreparation).options(joinedload(CandidatePreparation.candidate))  # LOAD candidate  # ADDED: join to fetch candidate.offset(skip).limit(limit).all()


def get_candidate_preparation(db: Session, prep_id: int):
    return (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate),
            joinedload(CandidatePreparation.instructor1),  # ADD
            joinedload(CandidatePreparation.instructor2),  # ADD
            joinedload(CandidatePreparation.instructor3),  # ADD
        )
        .filter(CandidatePreparation.id == prep_id)
        .first()
    )

def get_all_preparations(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate),
            joinedload(CandidatePreparation.instructor1),  # ADD
            joinedload(CandidatePreparation.instructor2),  # ADD
            joinedload(CandidatePreparation.instructor3),  # ADD
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

def update_candidate_preparation(db: Session, prep_id: int, updates: CandidatePreparationUpdate):
    db_prep = db.query(CandidatePreparation).filter(CandidatePreparation.id == prep_id).first()
    if not db_prep:
        return None
    update_data = updates.dict(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].lower()
    for key, value in update_data.items():
        setattr(db_prep, key, value)
    db.commit()
    db.refresh(db_prep)
    return db_prep

def delete_candidate_preparation(db: Session, prep_id: int):
    db_prep = db.query(CandidatePreparation).filter(CandidatePreparation.id == prep_id).first()
    if not db_prep:
        return None
    db.delete(db_prep)
    db.commit()
    return db_prep