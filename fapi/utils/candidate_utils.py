from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.models import CandidatePlacementORM,CandidateMarketingORM, CandidateORM
from fapi.db.schemas import CandidatePlacementCreate,CandidateMarketingCreate
from fastapi import HTTPException
from typing import List, Dict

# --------------------------------Candidate------------------------------

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
        


def get_all_marketing_records(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidateMarketingORM).count()
        results = (
            db.query(CandidateMarketingORM)
            .order_by(CandidateMarketingORM.id.desc())
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

def get_marketing_by_id(record_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        record = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        data = record.__dict__.copy()
        data.pop('_sa_instance_state', None)
        return data
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


def get_all_placements(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidatePlacementORM).count()
        results = (
            db.query(CandidatePlacementORM)
            .order_by(CandidatePlacementORM.id.desc())
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

def get_placement_by_id(placement_id: int) -> Dict:
    db: Session = SessionLocal()
    try:
        placement = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.id == placement_id).first()
        if not placement:
            raise HTTPException(status_code=404, detail="Placement not found")
        data = placement.__dict__.copy()
        data.pop('_sa_instance_state', None)
        return data
    finally:
        db.close()

def create_placement(payload: CandidatePlacementCreate) -> Dict:
    db: Session = SessionLocal()
    try:
        new_entry = CandidatePlacementORM(**payload.dict())
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry.__dict__
    finally:
        db.close()

def update_placement(placement_id: int, payload: CandidatePlacementCreate) -> Dict:
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