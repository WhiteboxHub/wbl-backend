# wbl-backend/fapi/utils/candidate_utils.py
from sqlalchemy.orm import Session, joinedload, selectinload,contains_eager
from sqlalchemy import or_,func
from fapi.db.database import SessionLocal,get_db

from fapi.db.models import AuthUserORM, Batch, CandidateORM, CandidatePlacementORM,CandidateMarketingORM,CandidateInterview,CandidatePreparation, EmployeeORM, PlacementFeeCollection
from fapi.db.schemas import CandidateMarketingCreate, CandidateInterviewCreate,CandidateBase,BatchOut,CandidatePlacementUpdate,CandidateMarketingUpdate,CandidateInterviewUpdate,CandidatePreparationCreate, CandidatePreparationUpdate, CandidateInterviewOut

from fastapi import HTTPException,APIRouter,Depends
from typing import List, Dict,Any, Optional 
from datetime import date

router = APIRouter()
      
def get_all_candidates_paginated(
    db: Session,
    page: int = 1,
    limit: int = 0,
    search: str = None,
    search_by: str = "all",
    sort: str = "enrolled_date:desc"
) -> Dict[str, Any]:
    query = (
        db.query(CandidateORM)
        .options(joinedload(CandidateORM.batch)) 
    )

    if search:
        if search_by == "id":
            try:
                query = query.filter(CandidateORM.id == int(search))
            except ValueError:
                query = query.filter(CandidateORM.id == -1)
        elif search_by == "full_name":
            query = query.filter(CandidateORM.full_name.ilike(f"%{search}%"))
        elif search_by == "email":
            query = query.filter(CandidateORM.email.ilike(f"%{search}%"))
        elif search_by == "phone":
            query = query.filter(CandidateORM.phone.ilike(f"%{search}%"))
        else:
            query = query.filter(
                or_(
                    CandidateORM.full_name.ilike(f"%{search}%"),
                    CandidateORM.email.ilike(f"%{search}%"),
                    CandidateORM.phone.ilike(f"%{search}%"),
                )
            )

    # Apply sorting
    if sort:
        sort_fields = sort.split(",")
        for field in sort_fields:
            col, direction = field.split(":")
            if not hasattr(CandidateORM, col):
                raise HTTPException(status_code=400, detail=f"Cannot sort by field: {col}")
            column = getattr(CandidateORM, col)
            query = query.order_by(column.desc() if direction == "desc" else column.asc())

    total = query.count()

    if limit > 0:
        candidates = query.offset((page - 1) * limit).limit(limit).all()
    else:
        candidates = query.all()

    # Get active preparation and marketing statuses efficiently
    active_prep_ids = {r[0] for r in db.query(CandidatePreparation.candidate_id).filter(CandidatePreparation.status == "active").all()}
    active_marketing_ids = {r[0] for r in db.query(CandidateMarketingORM.candidate_id).filter(CandidateMarketingORM.status == "active").all()}

    data = []
    for candidate in candidates:
        item = candidate.__dict__.copy()
        item.pop('_sa_instance_state', None)

        if candidate.batch:
            item["batchname"] = candidate.batch.batchname
        else:
            item["batchname"] = None
        
        item["is_in_prep"] = "Yes" if candidate.id in active_prep_ids else "No"
        item["is_in_marketing"] = "Yes" if candidate.id in active_marketing_ids else "No"

        data.append(item)

    return {"data": data, "total": total, "page": page, "limit": limit}


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
        candidate_data.setdefault("enrolled_date", date.today())
        if "email" in candidate_data and candidate_data["email"]:
            candidate_data["email"] = candidate_data["email"].lower()

        new_candidate = CandidateORM(**candidate_data)
        db.add(new_candidate)
        db.commit()
        db.refresh(new_candidate)
        return new_candidate.id
    except Exception as e:
        db.rollback()
        print("Error creating candidate:", e)  
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


        
def update_candidate(candidate_id: int, candidate_data: dict):
    db: Session = SessionLocal()
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        for key, value in candidate_data.items():
            setattr(candidate, key, value)

        db.flush()

        if getattr(candidate, "move_to_prep", False):
            active_prep = db.query(CandidatePreparation).filter_by(candidate_id=candidate.id, status='active').first()
            if not active_prep:
                new_prep = CandidatePreparation(
                    candidate_id=candidate.id,
                    start_date=date.today(),
                    status="active"
                )
                db.add(new_prep)
        
        # Keep the flag in sync with the actual active preparation status
        final_active_prep = db.query(CandidatePreparation).filter_by(candidate_id=candidate.id, status='active').first()
        candidate.move_to_prep = True if final_active_prep else False

        db.commit()
        db.refresh(candidate)
        return candidate.id

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close() 




# # -----------------------------------------------Marketing----------------------------

def get_all_marketing_records(page: int, limit: int) -> dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidateMarketingORM).count()

        records = (
            db.query(CandidateMarketingORM)
            .options(
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.batch),

                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor1),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor2),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor3),

                joinedload(CandidateMarketingORM.marketing_manager_obj),
            )
            .order_by(CandidateMarketingORM.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        results_serialized = [serialize_marketing(r) for r in records]

        return {"page": page, "limit": limit, "total": total, "data": results_serialized}
    finally:
        db.close()


def serialize_marketing(record: CandidateMarketingORM) -> dict:
    if not record:
        return None

    record_dict = record.__dict__.copy()
    record_dict.pop("_sa_instance_state", None)

    candidate = record.candidate
    record_dict["candidate"] = candidate.__dict__.copy() if candidate else None
    if record_dict["candidate"]:
        record_dict["candidate"].pop("_sa_instance_state", None)
        record_dict["candidate"]["batch"] = candidate.batch.__dict__.copy() if candidate.batch else None
        if record_dict["candidate"]["batch"]:
            record_dict["candidate"]["batch"].pop("_sa_instance_state", None)
        
        # Add workstatus from candidate
        record_dict["workstatus"] = candidate.workstatus if candidate else None

        # Get instructors from ACTIVE preparation record (not last one)
        active_prep = None
        if candidate.preparations:
            # Find the active preparation record
            for prep in candidate.preparations:
                if prep.status == 'active':
                    active_prep = prep
                    break
        
        # Set instructor names from active preparation
        if active_prep:
            record_dict["instructor1_name"] = active_prep.instructor1.name if active_prep.instructor1 else None
            record_dict["instructor2_name"] = active_prep.instructor2.name if active_prep.instructor2 else None
            record_dict["instructor3_name"] = active_prep.instructor3.name if active_prep.instructor3 else None
        else:
            record_dict["instructor1_name"] = None
            record_dict["instructor2_name"] = None
            record_dict["instructor3_name"] = None
    else:
        record_dict["instructor1_name"] = record_dict["instructor2_name"] = record_dict["instructor3_name"] = None

    # Marketing manager
    if record.marketing_manager_obj:
        record_dict["marketing_manager_obj"] = record.marketing_manager_obj.__dict__.copy()
        record_dict["marketing_manager_obj"].pop("_sa_instance_state", None)
    else:
        record_dict["marketing_manager_obj"] = None

    return record_dict


def get_marketing_by_candidate_id(candidate_id: int):
    db: Session = SessionLocal()
    try:
        records = (
            db.query(CandidateMarketingORM)
            .options(
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.batch),

                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor1),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor2),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparations)
                .joinedload(CandidatePreparation.instructor3),

                joinedload(CandidateMarketingORM.marketing_manager_obj),
            )
            .filter(CandidateMarketingORM.candidate_id == candidate_id)
            .all()
        )

        if not records:
            raise HTTPException(status_code=404, detail="No marketing records found for this candidate")

        results_serialized = [serialize_marketing(r) for r in records]
        return {"candidate_id": candidate_id, "data": results_serialized}
    finally:
        db.close()


def create_marketing(payload: CandidateMarketingCreate) -> dict:
    db: Session = SessionLocal()
    try:
        new_entry = CandidateMarketingORM(**payload.dict())
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return serialize_marketing(new_entry)
    finally:
        db.close()


def update_marketing(record_id: int, payload: CandidateMarketingUpdate) -> dict:
    db: Session = SessionLocal()
    try:
        record = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")

        update_data = payload.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(record, key) and not isinstance(value, dict):
                setattr(record, key, value)

        if getattr(record, "move_to_placement", False):
            candidate = db.query(CandidateORM).filter(CandidateORM.id == record.candidate_id).first()
            if candidate:
                placement_exists = (
                    db.query(CandidatePlacementORM)
                    .filter_by(candidate_id=candidate.id, status="Active")
                    .first()
                )
                if not placement_exists:
                    new_placement = CandidatePlacementORM(
                        candidate_id=candidate.id,
                        placement_date=date.today(),
                        status="Active"
                    )
                    db.add(new_placement)

        # Keep flag in sync with actual active placement status
        final_placement = db.query(CandidatePlacementORM).filter_by(candidate_id=record.candidate_id, status="Active").first()
        record.move_to_placement = True if final_placement else False

        db.commit()
        db.refresh(record)
        return serialize_marketing(record)
    finally:
        db.close()


def delete_marketing(record_id: int) -> dict:
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


def get_placement_by_id(db: Session, placement_id: int):
    result = (
        db.query(
            CandidatePlacementORM,
            CandidateORM.full_name.label("candidate_name"),
            CandidateMarketingORM.start_date.label("marketing_start_date"),
        )
        .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
        .outerjoin(
            CandidateMarketingORM,
            CandidatePlacementORM.candidate_id == CandidateMarketingORM.candidate_id,
        )
        .filter(CandidatePlacementORM.id == placement_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Placement not found")

    placement, candidate_name, marketing_start_date = result
    data = placement.__dict__.copy()
    data.pop("_sa_instance_state", None)
    data["candidate_name"] = candidate_name
    data["marketing_start_date"] = marketing_start_date
    return data


def get_all_placements(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidatePlacementORM).count()

        # Get unique placement IDs first
        placement_ids_subquery = (
            db.query(CandidatePlacementORM.id)
            .order_by(CandidatePlacementORM.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .subquery()
        )

        # Then fetch full data for those IDs
        results = (
            db.query(
                CandidatePlacementORM,
                CandidateORM.full_name.label("candidate_name"),
                func.coalesce(
                    CandidateMarketingORM.start_date,
                ).label("marketing_start_date")
            )
            .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
            .outerjoin(
                CandidateMarketingORM,
                CandidatePlacementORM.candidate_id == CandidateMarketingORM.candidate_id
            )
            .filter(CandidatePlacementORM.id.in_(placement_ids_subquery))
            .order_by(CandidatePlacementORM.id.desc())
            .all()
        )

        # Deduplicate in Python to ensure uniqueness
        seen_ids = set()
        data = []
        for placement, candidate_name, marketing_start_date in results:
            if placement.id not in seen_ids:
                seen_ids.add(placement.id)
                record = placement.__dict__.copy()
                record.pop("_sa_instance_state", None)
                record["candidate_name"] = candidate_name
                record["marketing_start_date"] = marketing_start_date
                data.append(record)

        return {"page": page, "limit": limit, "total": total, "data": data}
    finally:
        db.close()


def get_placements_by_candidate(candidate_id: int) -> list:
    db: Session = SessionLocal()
    try:
        results = (
            db.query(
                CandidatePlacementORM,
                CandidateORM.full_name.label("candidate_name"),
                CandidateMarketingORM.start_date.label("marketing_start_date"),
            )
            .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
            .outerjoin(
                CandidateMarketingORM,
                CandidatePlacementORM.candidate_id == CandidateMarketingORM.candidate_id
            )
            .filter(CandidatePlacementORM.candidate_id == candidate_id)
            .all()
        )

        if not results:
            raise HTTPException(status_code=404, detail="No placements found for this candidate")

        data = []
        for placement, candidate_name, marketing_start_date in results:
            record = placement.__dict__.copy()
            record.pop("_sa_instance_state", None)
            record["candidate_name"] = candidate_name
            record["marketing_start_date"] = marketing_start_date
            data.append(record)
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
        placement = db.query(CandidatePlacementORM).filter(
            CandidatePlacementORM.id == placement_id  
        ).first()
        if not placement:
            raise HTTPException(status_code=404, detail="Placement not found")

        for key, value in payload.dict(exclude_unset=True).items():
            setattr(placement, key, value)

        db.commit()
        db.refresh(placement)
        return placement
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

# ----------------------------------------Candidate_Interviews-------------------------------------

def create_candidate_interview(db: Session, interview: CandidateInterviewCreate):
    data = interview.dict()

    if data.get("interviewer_emails"):
        data["interviewer_emails"] = ",".join(
            [email.strip().lower() for email in data["interviewer_emails"].split(",")]
        )
    db_obj = CandidateInterview(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_candidate_interview_with_instructors(db: Session, interview_id: int):
    return (
        db.query(CandidateInterview)
        .join(CandidatePreparation, CandidateInterview.candidate_id == CandidatePreparation.candidate_id)
        .options(
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor1),
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor2),
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor3),
        )
        .filter(CandidateInterview.id == interview_id)
        .first()
    )


def list_interviews_with_instructors(db: Session):
    return (
        db.query(CandidateInterview)
        .join(CandidatePreparation, CandidateInterview.candidate_id == CandidatePreparation.candidate_id)
        .options(
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor1),
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor2),
            joinedload(CandidateInterview.candidate)
            .joinedload(CandidateORM.preparations)
            .joinedload(CandidatePreparation.instructor3),
        )
        .order_by(CandidateInterview.interview_date.desc())
        .all()
    )

def serialize_interview(interview: CandidateInterview) -> dict:
    data = CandidateInterviewOut.from_orm(interview).dict()

    data["instructor1_name"] = None
    data["instructor2_name"] = None
    data["instructor3_name"] = None

    if interview.candidate and interview.candidate.preparations:
        prep = interview.candidate.preparations[0]  
        if prep.instructor1:
            data["instructor1_name"] = prep.instructor1.name
        if prep.instructor2:
            data["instructor2_name"] = prep.instructor2.name
        if prep.instructor3:
            data["instructor3_name"] = prep.instructor3.name

    return data


def update_candidate_interview(db: Session, interview_id: int, updates: CandidateInterviewUpdate):
    db_obj = db.query(CandidateInterview).options(joinedload(CandidateInterview.candidate)) .join(CandidateORM, CandidateInterview.candidate_id == CandidateORM.id).filter(CandidateInterview.id == interview_id).first()
    if not db_obj:
        return None

    update_data = updates.dict(exclude_unset=True)

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
    db_obj = db.query(CandidateInterview).filter(CandidateInterview.id == interview_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj



def get_active_marketing_candidates(db: Session):
    results = (
        db.query(CandidateMarketingORM, CandidateORM)
        .join(CandidateORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
        .filter(CandidateMarketingORM.status == "active")
        .all()
    )

    return [
        {
            "candidate_id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "start_date": marketing.start_date,
            "status": marketing.status,
        }
        for marketing, candidate in results
    ]


# -------------------Candidate_Preparation-------------
from datetime import datetime
def is_valid_date(date_str):
    if not date_str:
        return False
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
def create_candidate_preparation(db: Session, prep_data: CandidatePreparationCreate):
    if prep_data.email:
        prep_data.email = prep_data.email.lower()
    db_prep = CandidatePreparation(**prep_data.dict(exclude_unset=True))
    db.add(db_prep)
    db.commit()
    db.refresh(candidate)

    # Return the full object so it matches the response_model
    return candidate

def get_preparations_by_candidate(db: Session, candidate_id: int):
    results = (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate),
            joinedload(CandidatePreparation.instructor1),
            joinedload(CandidatePreparation.instructor2),
            joinedload(CandidatePreparation.instructor3),
        )
        .filter(CandidatePreparation.candidate_id == candidate_id)
        .all()
    )

    if not results:
        raise HTTPException(status_code=404, detail="No preparations found for this candidate")

    return results


def get_all_preparations(db: Session):
    preps = (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate)
            .joinedload(CandidateORM.batch),  
            joinedload(CandidatePreparation.instructor1),
            joinedload(CandidatePreparation.instructor2),
            joinedload(CandidatePreparation.instructor3),
        )
        .all()
    )

    # Efficiently get candidates who have active marketing records
    active_marketing_ids = {r[0] for r in db.query(CandidateMarketingORM.candidate_id).filter(CandidateMarketingORM.status == "active").all()}

    for prep in preps:
        prep.is_in_marketing = "Yes" if prep.candidate_id in active_marketing_ids else "No"

    return preps

def update_candidate_preparation(db: Session, prep_id: int, updates: CandidatePreparationUpdate):
    db_prep = db.query(CandidatePreparation).filter(CandidatePreparation.id == prep_id).first()
    if not db_prep:
        return None

    update_data = updates.dict(exclude_unset=True)
 
    for key, value in update_data.items():
        if hasattr(db_prep, key):
            setattr(db_prep, key, value)

    db.flush()  

    candidate = db.query(CandidateORM).filter(CandidateORM.id == db_prep.candidate_id).first()
    if candidate and getattr(db_prep, "move_to_mrkt", False):
        marketing_exists = (
            db.query(CandidateMarketingORM)
            .filter_by(candidate_id=candidate.id, status="active")
            .first()
        )
        if not marketing_exists:
            new_marketing = CandidateMarketingORM(
                candidate_id=candidate.id,
                start_date=date.today(),
                status="active"
            )
            db.add(new_marketing)

    # Keep flag in sync with actual active marketing status
    final_marketing = db.query(CandidateMarketingORM).filter_by(candidate_id=db_prep.candidate_id, status="active").first()
    db_prep.move_to_mrkt = True if final_marketing else False

    db.commit()
    db.refresh(db_prep)
    return db_prep



def delete_candidate_preparation(db: Session, prep_id: int) -> Optional[dict]:
    db_prep = (
        db.query(CandidatePreparation)
        .options(
            joinedload(CandidatePreparation.candidate),
            joinedload(CandidatePreparation.instructor1),
        )
        .filter(CandidatePreparation.id == prep_id)
        .first()
    )
    if not db_prep:
        return None
  
    result = {
        "id": db_prep.id,
        "candidate_id": db_prep.candidate_id,
        "instructor1_id": db_prep.instructor1_id,
    }
    db.delete(db_prep)
    db.commit()
    return result

def get_candidate_suggestions(search_term: str, db: Session):
    if not search_term or len(search_term.strip()) < 2:
        return []

    try:
        candidates = (
            db.query(CandidateORM.id, CandidateORM.full_name, CandidateORM.email)
            .filter(
                or_(
                    CandidateORM.full_name.ilike(f"%{search_term}%"),
                    CandidateORM.email.ilike(f"%{search_term}%")
                )
            )
            .order_by(CandidateORM.full_name)
            .limit(10)
            .all()
        )

        return [
            {
                "id": c.id,
                "name": c.full_name,
                "email": c.email or "No email"
            }
            for c in candidates
        ]
    except Exception as e:
        return {"error": str(e)}



# ------------------------------------------------------ Candidate Search ------------------------------------------------------

def get_candidate_details(candidate_id: int, db: Session):
    try:
        candidate = (
            db.query(CandidateORM)
            .options(
                selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor1),
                selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor2),
                selectinload(CandidateORM.preparations).joinedload(CandidatePreparation.instructor3),
                selectinload(CandidateORM.marketing_records).joinedload(CandidateMarketingORM.marketing_manager_obj),
                selectinload(CandidateORM.interviews),
                selectinload(CandidateORM.placements),
            )
            .filter(CandidateORM.id == candidate_id)
            .first()
        )

        if not candidate:
            return {"error": "Candidate not found"}

        # Batch name
        batch_name = f"Batch ID: {candidate.batchid}"
        batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
        if batch:
            batch_name = batch.batchname

        # Auth user info
        authuser = None
        if candidate.email:
            authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(candidate.email)).first()

        return {
            "candidate_id": candidate.id,
            "basic_info": {
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "secondary_email": getattr(candidate, "secondaryemail", None),
                "secondary_phone": getattr(candidate, "secondaryphone", None),
                "linkedin_id": candidate.linkedin_id,
                "status": candidate.status,
                "work_status": candidate.workstatus,
                "education": candidate.education,
                "work_experience": candidate.workexperience,
                "ssn": f"-*-{str(candidate.ssn)[-4:]}" if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
                "dob": candidate.dob.isoformat() if candidate.dob else None,
                "address": candidate.address,
                "agreement": candidate.agreement,
                "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                "batch_name": batch_name,
                "candidate_folder": candidate.candidate_folder,
                "github_link": candidate.github_link,
                "notes": candidate.notes,
            },
            "emergency_contact": {
                "emergency_contact_name": candidate.emergcontactname,
                "emergency_contact_phone": candidate.emergcontactphone,
                "emergency_contact_email": candidate.emergcontactemail,
                "emergency_contact_address": candidate.emergcontactaddrs,
            },
            "fee_financials": {
                "fee_paid": candidate.fee_paid,
                "payment_status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
                "notes": candidate.notes,
            },
            "preparation_records": [
                {
                    "start_date": prep.start_date.isoformat() if prep.start_date else None,
                    "instructor_1_name": prep.instructor1.name if prep.instructor1 else None,
                    "instructor_2_name": prep.instructor2.name if prep.instructor2 else None,
                    "instructor_3_name": prep.instructor3.name if prep.instructor3 else None,
                    "rating": prep.rating,

                    "communication": prep.communication,
                    "years_of_experience": prep.years_of_experience,
                    "last_modified": prep.last_mod_datetime.isoformat()
                    if getattr(prep, "last_mod_datetime", None)
                    else None,
                }
                for prep in candidate.preparations
            ],
            "marketing_records": [
                {
                    "start_date": m.start_date.isoformat() if m.start_date else None,
                    "Marketing Email": m.email,
                    "Email Password": m.password,
                    "Linkedin Username": m.linkedin_username,
                    "Linkedin Password": m.linkedin_passwd,
                    "marketing_manager_name": m.marketing_manager_obj.name if m.marketing_manager_obj else None,
                    "notes": m.notes,
                    "last_modified": m.last_mod_datetime.isoformat()
                    if getattr(m, "last_mod_datetime", None)
                    else None,
                }
                for m in candidate.marketing_records
            ],
            "interview_records": [
                {
                    "company": i.company,
                    "interview_date": i.interview_date.isoformat() if i.interview_date else None,
                    "interview_type": i.type_of_interview,
                    "company_type": i.company_type,
                    "mode_of_interview": i.mode_of_interview,
                    "feedback": i.feedback,
                    "recording_link": i.recording_link,
                    "notes": i.notes,
                }
                for i in candidate.interviews
            ],
            "placement_records": [
                {
                    "position": p.position,
                    "company": p.company,
                    "placement_date": p.placement_date.isoformat() if p.placement_date else None,
                    "status": p.status,
                    "type": p.type,
                    "base_salary_offered": float(p.base_salary_offered) if p.base_salary_offered else None,
                    "benefits": p.benefits,
                    "placement_fee_paid": float(p.fee_paid) if p.fee_paid else None,
                    "last_modified": p.last_mod_datetime.isoformat()
                    if getattr(p, "last_mod_datetime", None)
                    else None,
                    "notes": p.notes,
                }
                for p in candidate.placements
            ],
            "placement_fee_collection": [
                {
                    "id": fee.id,
                    "placement_id": fee.placement_id,
                    "installment_id": fee.installment_id,
                    "deposit_date": fee.deposit_date.isoformat() if fee.deposit_date else None,
                    "deposit_amount": float(fee.deposit_amount) if fee.deposit_amount else None,
                    "amount_collected": fee.amount_collected.value if fee.amount_collected else None,
                    "lastmod_user_id": fee.lastmod_user_id,
                    "last_mod_date": fee.last_mod_date.isoformat() if fee.last_mod_date else None,
                }
                for p in candidate.placements
                for fee in db.query(PlacementFeeCollection).filter(PlacementFeeCollection.placement_id == p.id).all()
            ],
            "login_access": {
                "login_count": getattr(authuser, "logincount", 0) if authuser else 0,
                "last_login": authuser.lastmoddatetime.isoformat()
                if authuser and getattr(authuser, "lastmoddatetime", None)
                else None,
                "registered_date": authuser.registereddate.isoformat()
                if authuser and getattr(authuser, "registereddate", None)
                else None,
                "status": getattr(authuser, "status", "No Account") if authuser else "No Account",
                "google_id": getattr(authuser, "googleId", None) if authuser else None,
            },
            "miscellaneous": {
                "notes": candidate.notes,
                "preparation_active": bool(candidate.preparations),
                "marketing_active": bool(candidate.marketing_records),
                "placement_active": bool(candidate.placements),
            },
        }

    except Exception as e:
        return {"error": str(e)}



def search_candidates_comprehensive(search_term: str, db: Session):
    """
    Search candidates by name and return detailed information for accordion display.
    """
    try:
        candidates = (
            db.query(CandidateORM)
            .filter(CandidateORM.full_name.ilike(f"%{search_term}%"))
            .options(
                selectinload(CandidateORM.preparations),
                selectinload(CandidateORM.marketing_records),
                selectinload(CandidateORM.interviews),
                selectinload(CandidateORM.placements),
            )
            .all()
        )

        if not candidates:
            return []

        results = []

        for c in candidates:
            batch = db.query(Batch).filter(Batch.batchid == c.batchid).first()
            batch_name = batch.batchname if batch else f"Batch ID: {c.batchid}"

            authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(c.email)).first() if c.email else None

            results.append(
                {
                    "candidate_id": c.id,
                    "full_name": c.full_name,
                    "email": c.email,
                    "phone": c.phone,
                    "status": c.status,
                    "batch_name": batch_name,
                    "preparation_count": len(c.preparations),
                    "marketing_count": len(c.marketing_records),
                    "interview_count": len(c.interviews),
                    "placement_count": len(c.placements),
                    "registered_date": authuser.registereddate.isoformat()
                    if authuser and getattr(authuser, "registereddate", None)
                    else None,
                    "login_count": getattr(authuser, "logincount", 0) if authuser else 0,
                }
            )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")



def get_candidate_sessions(candidate_id: int, db: Session) -> dict:
    """
    Get sessions with smart name matching - handles common names like 'Sai'
    """
    try:
        from fapi.db.models import Session as SessionModel
        from datetime import datetime, timedelta
        import re
        
        
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            return {"error": "Candidate not found", "sessions": []}
        

        all_words = [word for word in candidate.full_name.split() if len(word) >= 3]
        
    
        common_names = ['sai', 'sri', 'kumar', 'reddy', 'rao', 'prasad']
        
     
        priority_words = []
        common_words = []
        
        for word in all_words:
            if word.lower() in common_names:
                common_words.append(word)
            else:
                priority_words.append(word)
        
        
        search_words = priority_words if priority_words else all_words
        
        if not search_words:
            return {"candidate_id": candidate_id, "candidate_name": candidate.full_name, "sessions": []}
        
        
        one_year_ago = datetime.now() - timedelta(days=365)
        

        recent_sessions = (
            db.query(SessionModel)
            .filter(SessionModel.sessiondate >= one_year_ago)
            .all()
        )
        
        
        matched_sessions = []
        for session in recent_sessions:
            title_text = (session.title or "").lower()
            subject_text = (session.subject or "").lower()
            combined_text = f"{title_text} {subject_text}"
            
            word_found = False
            
          
            for word in priority_words:
                word_lower = word.lower()
                
         
                pattern = r'\b' + re.escape(word_lower) + r'\b'
                if re.search(pattern, combined_text):
                    word_found = True
                    break
                
       
                if len(word_lower) >= 4 and word_lower in combined_text:
                    word_found = True
                    break
            
        
            if not word_found and common_words and not priority_words:
                for word in common_words:
                    word_lower = word.lower()
                    
            
                    pattern = r'\b' + re.escape(word_lower) + r'\b'
                    if re.search(pattern, combined_text):
                        word_found = True
                        break
            
            
            if not word_found and priority_words and common_words:
                priority_matches = 0
                common_matches = 0
                
                
                for word in priority_words:
                    word_lower = word.lower()
                    pattern = r'\b' + re.escape(word_lower) + r'\b'
                    if re.search(pattern, combined_text):
                        priority_matches += 1
                
                
                for word in common_words:
                    word_lower = word.lower()
                    pattern = r'\b' + re.escape(word_lower) + r'\b'
                    if re.search(pattern, combined_text):
                        common_matches += 1
                
                
                if priority_matches >= 1 or (priority_matches + common_matches >= 2):
                    word_found = True
            
            if word_found:
                matched_sessions.append(session)
        
        
        matched_sessions.sort(key=lambda x: x.sessiondate or datetime.min, reverse=True)
        
        
        session_list = []
        for session in matched_sessions:
            session_date_str = None
            if session.sessiondate:
                if isinstance(session.sessiondate, str):
                    session_date_str = session.sessiondate
                else:
                    session_date_str = session.sessiondate.isoformat()
            
            session_data = {
                "session_id": session.sessionid,
                "title": session.title,
                "session_date": session_date_str,
                "type": session.type,
                "subject": session.subject,
                "link": session.link
            }
            session_list.append(session_data)
        
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "sessions": session_list,
            "debug_info": {
                "all_words": all_words,
                "priority_words": priority_words,
                "common_words": common_words,
                "search_strategy": "priority_first" if priority_words else "all_words"
            }
        }
        
    except Exception as e:
        return {"error": str(e), "sessions": []}
