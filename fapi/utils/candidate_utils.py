# wbl-backend/fapi/utils/candidate_utils.py
from sqlalchemy.orm import Session, joinedload, selectinload,contains_eager
from sqlalchemy import or_
from fapi.db.database import SessionLocal,get_db

from fapi.db.models import AuthUserORM, Batch, CandidateORM, CandidatePlacementORM,CandidateMarketingORM,CandidateInterview,CandidatePreparation, EmployeeORM
from fapi.db.schemas import CandidateMarketingCreate, CandidateInterviewCreate,CandidatePlacementUpdate,CandidateMarketingUpdate,CandidateInterviewUpdate,CandidatePreparationCreate, CandidatePreparationUpdate, CandidateInterviewOut

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
    query = db.query(CandidateORM)

    # Apply search filters
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
        else:  # search_by == "all"
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
            if direction == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

    # Get total count
    total = query.count()

    # Handle pagination
    if limit > 0:
        candidates = query.offset((page - 1) * limit).limit(limit).all()
    else:
        candidates = query.all()  # Return all records if limit=0

    # Serialize data
    data = []
    for candidate in candidates:
        item = candidate.__dict__.copy()
        item.pop('_sa_instance_state', None)
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
    print(candidate_data,"*"*200)
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        for key, value in candidate_data.items():
            setattr(candidate, key, value)

        db.flush()

        if getattr(candidate, "move_to_prep", False):
            prep_exists = db.query(CandidatePreparation).filter_by(candidate_id=candidate.id).first()
            if not prep_exists:
                new_prep = CandidatePreparation(
                    candidate_id=candidate.id,
                    start_date=date.today(),
                    status="active"
                )
                db.add(new_prep)

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




# -----------------------------------------------Marketing----------------------------

def get_all_marketing_records(page: int, limit: int) -> Dict:
    db: Session = SessionLocal()
    try:
        total = db.query(CandidateMarketingORM).count()

        records = (
            db.query(CandidateMarketingORM)
            .join(CandidateMarketingORM.candidate)  
            .outerjoin(
                CandidateORM.preparation_records
            )  
            .options(
                joinedload(CandidateMarketingORM.candidate),
                joinedload(CandidateMarketingORM.instructor1),
                joinedload(CandidateMarketingORM.instructor2),
                joinedload(CandidateMarketingORM.instructor3),
                joinedload(CandidateMarketingORM.marketing_manager_obj),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor1),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor2),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor3),
            )
            .order_by(CandidateMarketingORM.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        results_serialized = []
        for r in records:
            candidate = r.candidate
            prep = candidate.preparation_records[-1] if candidate and candidate.preparation_records else None

            record_dict = r.__dict__.copy()
            record_dict.pop("_sa_instance_state", None)
            record_dict["instructor1_name"] = prep.instructor1.name if prep and prep.instructor1 else None
            record_dict["instructor2_name"] = prep.instructor2.name if prep and prep.instructor2 else None
            record_dict["instructor3_name"] = prep.instructor3.name if prep and prep.instructor3 else None

            # Candidate dict
            record_dict["candidate"] = candidate.__dict__ if candidate else None
            if record_dict["candidate"]:
                record_dict["candidate"].pop("_sa_instance_state", None)

            # Marketing manager dict
            record_dict["marketing_manager_obj"] = r.marketing_manager_obj.__dict__ if r.marketing_manager_obj else None
            if record_dict["marketing_manager_obj"]:
                record_dict["marketing_manager_obj"].pop("_sa_instance_state", None)

            results_serialized.append(record_dict)

        return {"page": page, "limit": limit, "total": total, "data": results_serialized}
    finally:
        db.close()



def get_marketing_by_candidate_id(candidate_id: int):
    db: Session = SessionLocal()
    try:
        records = (
            db.query(CandidateMarketingORM)
            .options(
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor1_employee),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor2_employee),
                joinedload(CandidateMarketingORM.candidate)
                .joinedload(CandidateORM.preparation_records)
                .joinedload(CandidatePreparation.instructor3_employee),
            )
            .filter(CandidateMarketingORM.candidate_id == candidate_id)
            .all()
        )
        if not records:
            raise HTTPException(status_code=404, detail="No marketing records found for this candidate")

        results_serialized = []
        for r in records:
            candidate = r.candidate
            prep = candidate.preparation_records[-1] if candidate and candidate.preparation_records else None
            results_serialized.append({
                "id": r.id,
                "candidate_id": r.candidate_id,
                "candidate_name": candidate.full_name if candidate else None,
                "start_date": r.start_date.isoformat() if r.start_date else None,
                "status": r.status,
                "instructor1_name": prep.instructor1_employee.name if prep and prep.instructor1_employee else None,
                "instructor2_name": prep.instructor2_employee.name if prep and prep.instructor2_employee else None,
                "instructor3_name": prep.instructor3_employee.name if prep and prep.instructor3_employee else None,
                "marketing_manager_name": r.marketing_manager_obj.name if r.marketing_manager_obj else None,
                "notes": r.notes,
                "last_mod_datetime": r.last_mod_datetime.isoformat() if r.last_mod_datetime else None
            })

        return {"candidate_id": candidate_id, "data": results_serialized}
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



def serialize_marketing(record: CandidateMarketingORM) -> dict:
    if not record:
        return None

    record_dict = record.__dict__.copy()
    record_dict.pop("_sa_instance_state", None)

    candidate = record.candidate
    record_dict["candidate"] = candidate.__dict__.copy() if candidate else None
    if record_dict["candidate"]:
        record_dict["candidate"].pop("_sa_instance_state", None)

    record_dict["marketing_manager_obj"] = (
        record.marketing_manager_obj.__dict__.copy() if record.marketing_manager_obj else None
    )
    if record_dict["marketing_manager_obj"]:
        record_dict["marketing_manager_obj"].pop("_sa_instance_state", None)

    for i, rel in enumerate([record.instructor1, record.instructor2, record.instructor3], start=1):
        if rel:
            d = rel.__dict__.copy()
            d.pop("_sa_instance_state", None)
            record_dict[f"instructor{i}"] = d
        else:
            record_dict[f"instructor{i}"] = None

    return record_dict


def update_marketing(record_id: int, payload: CandidateMarketingUpdate) -> Dict:
    db: Session = SessionLocal()
    try:
        record = (
            db.query(CandidateMarketingORM)
            .filter(CandidateMarketingORM.id == record_id) 
            .first()
        )
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

        db.commit()
        db.refresh(record)
        return serialize_marketing(record)
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

def get_placement_by_id(placement_id: int):
    db: Session = SessionLocal()
    try:
        placement = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.id == placement_id).first()
        if not placement:
            raise HTTPException(status_code=404, detail="Placement not found")
        data = placement.__dict__.copy()
        data.pop("_sa_instance_state", None)
        return data
    finally:
        db.close()


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
            .order_by(CandidatePlacementORM.priority.desc()) 
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



def get_placements_by_candidate(candidate_id: int) -> list:
    db: Session = SessionLocal()
    try:
        results = (
            db.query(CandidatePlacementORM, CandidateORM.full_name.label("candidate_name"))
            .join(CandidateORM, CandidatePlacementORM.candidate_id == CandidateORM.id)
            .filter(CandidatePlacementORM.candidate_id == candidate_id)
            .all()
        )
        if not results:
            raise HTTPException(status_code=404, detail="No placements found for this candidate")

        data = []
        for placement, candidate_name in results:
            record = placement.__dict__.copy()
            record["candidate_name"] = candidate_name
            record.pop("_sa_instance_state", None)
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

def create_candidate_preparation(db: Session, prep_data: CandidatePreparationCreate):
    if prep_data.email:
        prep_data.email = prep_data.email.lower()
    db_prep = CandidatePreparation(**prep_data.dict(exclude_unset=True))
    db.add(db_prep)
    db.commit()
    db.refresh(db_prep)
    return db_prep


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
    return (
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


##-------------------------------------------------search---------------------------------------------------------------

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
                "id": candidate.id,
                "name": candidate.full_name,
                "email": candidate.email or "No email"
            }
            for candidate in candidates
        ]
    except Exception as e:
        return {"error": str(e)}


def get_candidate_details(candidate_id: int, db: Session):
    try:
        candidate = (
            db.query(CandidateORM)
            .options(
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor1),
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor2),
                selectinload(CandidateORM.preparation_records).joinedload(CandidatePreparation.instructor3),
                selectinload(CandidateORM.marketing_records).joinedload(CandidateMarketingORM.marketing_manager_employee),
                selectinload(CandidateORM.interview_records),
                selectinload(CandidateORM.placement_records)
            )
            .filter(CandidateORM.id == candidate_id)
            .first()
        )

        if not candidate:
            return {"error": "Candidate not found"}
        
      
        batch_name = f"Batch ID: {candidate.batchid}"
        batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
        if batch:
            batch_name = batch.batchname

    
        authuser = None
        if candidate.email:
            authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(candidate.email)).first()

        return {
            "candidate_id": candidate.id,
            "basic_info": {
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "secondary_email": candidate.secondaryemail,
                "secondary_phone": candidate.secondaryphone,
                "linkedin_id": candidate.linkedin_id,
                "status": candidate.status,
                "work_status": candidate.workstatus,
                "education": candidate.education,
                "work_experience": candidate.workexperience,
                "ssn": "-*-" + str(candidate.ssn)[-4:] if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
                "dob": candidate.dob.isoformat() if candidate.dob else None,
                "address": candidate.address,
                "agreement": candidate.agreement,
                "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                "batch_name": batch_name,
                "candidate_folder": getattr(candidate, 'candidate_folder', None),
                "github_link": getattr(candidate, 'github_link', None),
                "notes": candidate.notes
            },
            "emergency_contact": {
                "emergency_contact_name": candidate.emergcontactname,
                "emergency_contact_phone": candidate.emergcontactphone,
                "emergency_contact_email": candidate.emergcontactemail,
                "emergecy_contact_address": candidate.emergcontactaddrs
            },
            "fee_financials": {
                "Fee Paid": candidate.fee_paid,
                "Payment Status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
                "Notes": candidate.notes
            },
            "preparation_records": [
                {
                    "Start Date": prep.start_date.isoformat() if prep.start_date else None,
                    "Instructor 1 Name": prep.instructor1.name if prep.instructor1 else None,
                    "Instructor 2 Name": prep.instructor2.name if prep.instructor2 else None,
                    "Instructor 3 Name": prep.instructor3.name if prep.instructor3 else None,
                    "Tech Rating": prep.tech_rating,
                    "Topics Finished": prep.topics_finished,
                    "Last Modified": prep.last_mod_datetime.isoformat() if prep.last_mod_datetime else None
                }
                for prep in candidate.preparation_records
            ],
            "marketing_records": [
                {
                    "Start Date": marketing.start_date.isoformat() if marketing.start_date else None,
                    "Marketing Manager Name": marketing.marketing_manager_employee.name if marketing.marketing_manager_employee else None,
                    "Notes": marketing.notes,
                    "Last Modified": marketing.last_mod_datetime.isoformat() if marketing.last_mod_datetime else None
                }
                for marketing in candidate.marketing_records
            ],
            "interview_records": [
                {
                    "Company": interview.company,
                    "Interview Date": interview.interview_date.isoformat() if interview.interview_date else None,
                    "Interview Type": interview.type_of_interview,
                    "Mode of Interview": interview.mode_of_interview,
                    "Feedback": interview.feedback,
                    "Recording Link": interview.recording_link,
                    "Notes": interview.notes
                }
                for interview in candidate.interview_records
            ],
            "placement_records": [
                {
                    "Position": placement.position,
                    "Company": placement.company,
                    "Placement Date": placement.placement_date.isoformat() if placement.placement_date else None,
                    "Status": placement.status,
                    "Type": placement.type,
                    "Base Salary Offered": float(placement.base_salary_offered) if placement.base_salary_offered else None,
                    "Benefits": placement.benefits,
                    "Placement Fee Paid": float(placement.fee_paid) if placement.fee_paid else None,
                    "Last Modified": placement.last_mod_datetime.isoformat() if placement.last_mod_datetime else None,
                    "Notes": placement.notes
                }
                for placement in candidate.placement_records
            ],
            "login_access": {
                "Login Count": authuser.logincount if authuser else 0,
                "Last Login": authuser.lastlogin.isoformat() if authuser and getattr(authuser, 'lastlogin', None) else None,
                "Registered Date": authuser.registereddate.isoformat() if authuser and authuser.registereddate else None,
                "Status": authuser.status if authuser else "No Account",
                "Google ID": authuser.googleId if authuser else None
            },
            "miscellaneous": {
                "Notes": candidate.notes,
                "Preparation Active": len(candidate.preparation_records) > 0,
                "Marketing Active": len(candidate.marketing_records) > 0,
                "Placement Active": len(candidate.placement_records) > 0
            }
        }

    except Exception as e:
        return {"error": str(e)}

def search_candidates_comprehensive(search_term: str, db: Session) -> List[Dict]:
    """
    Search candidates by name and return comprehensive information for accordion display with proper readable keys
    """
    try:
        candidates = (
            db.query(CandidateORM)
            .filter(CandidateORM.full_name.ilike(f"%{search_term}%"))
            .all()
        )

        if not candidates:
            return []

        results = []

        for candidate in candidates:
            try:
                from fapi.db.models import Batch
                batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
                batch_name = batch.batchname if batch else "Unknown Batch"
            except:
                batch_name = f"Batch ID: {candidate.batchid}"

            authuser = None
            try:
                from fapi.db.models import AuthUserORM
                if candidate.email:
                    authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(candidate.email)).first()
            except:
                pass

            preparation_records = []
            try:
                prep_data = db.query(CandidatePreparation).filter(CandidatePreparation.candidate_id == candidate.id).all()
                for prep in prep_data:
                    try:
                        from fapi.db.models import EmployeeORM
                        inst1_name = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor1_id).first().name if prep.instructor1_id else None
                        inst2_name = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor2_id).first().name if prep.instructor2_id else None
                        inst3_name = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor3_id).first().name if prep.instructor3_id else None

                        prep_record = {
                            "Start Date": prep.start_date.isoformat() if prep.start_date else None,
                            "Instructor 1 Name": inst1_name,
                            "Instructor 2 Name": inst2_name,
                            "Instructor 3 Name": inst3_name,
                            "Rating": prep.rating,
                            "Tech Rating": prep.tech_rating,
                            "Communication": prep.communication,
                            "Years of Experience": prep.years_of_experience,
                            "Current Topics": prep.current_topics,
                            "Last Modified": prep.last_mod_date.isoformat() if prep.last_mod_date else None
                        }
                        preparation_records.append(prep_record)
                    except Exception as e:
                        preparation_records.append({"Error": f"Error loading prep record: {str(e)}"})
            except:
                pass

            marketing_records = []
            try:
                marketing_data = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == candidate.id).all()
                for marketing in marketing_data:
                    try:
                        from fapi.db.models import EmployeeORM
                        manager_name = db.query(EmployeeORM).filter(EmployeeORM.id == marketing.marketing_manager).first().name if marketing.marketing_manager else None

                        marketing_record = {
                            "Start Date": marketing.start_date.isoformat() if marketing.start_date else None,
                            "Marketing Manager Name": manager_name,
                            "Notes": marketing.notes,
                            "Last Modified": marketing.last_mod_date.isoformat() if marketing.last_mod_date else None
                        }
                        marketing_records.append(marketing_record)
                    except Exception as e:
                        marketing_records.append({"Error": f"Error loading marketing record: {str(e)}"})
            except:
                pass

            interview_records = []
            try:
                interview_data = db.query(CandidateInterview).filter(CandidateInterview.candidate_id == candidate.id).all()
                for interview in interview_data:
                    try:
                        interview_record = {
                            "Company": interview.company,
                            "Interview Date": interview.interview_date.isoformat() if interview.interview_date else None,
                            "Interview Type": interview.type_of_interview,
                            "Feedback": interview.feedback,
                            "Recording Link": interview.recording_link,
                            "Notes": interview.notes
                        }
                        interview_records.append(interview_record)
                    except Exception as e:
                        interview_records.append({"Error": f"Error loading interview record: {str(e)}"})
            except:
                pass

            placement_records = []
            try:
                placement_data = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.candidate_id == candidate.id).all()
                for placement in placement_data:
                    try:
                        placement_record = {
                            "Position": placement.position,
                            "Company": placement.company,
                            "Placement Date": placement.placement_date.isoformat() if placement.placement_date else None,
                            "Status": placement.status,
                            "Type": placement.type,
                            "Base Salary Offered": float(placement.base_salary_offered) if placement.base_salary_offered else None,
                            "Benefits": placement.benefits,
                            "Fee Paid": float(placement.fee_paid) if placement.fee_paid else None,
                            "Last Modified": placement.last_mod_date.isoformat() if placement.last_mod_date else None,
                            "Notes": placement.notes
                        }
                        placement_records.append(placement_record)
                    except Exception as e:
                        placement_records.append({"Error": f"Error loading placement record: {str(e)}"})
            except:
                pass

            candidate_data = {
                "Candidate ID": candidate.id,
                "Basic Info": {
                    "Full Name": candidate.full_name,
                    "Email": candidate.email,
                    "Phone": candidate.phone,
                    "Secondary Email": candidate.secondaryemail,
                    "Secondary Phone": candidate.secondaryphone,
                    "LinkedIn ID": candidate.linkedin_id,
                    "Status": candidate.status,
                    "Work Status": candidate.workstatus,
                    "Education": candidate.education,
                    "Work Experience": candidate.workexperience,
                    "SSN": "-*-" + candidate.ssn[-4:] if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
                    "Date of Birth": candidate.dob.isoformat() if candidate.dob else None,
                    "Address": candidate.address,
                    "Agreement": candidate.agreement,
                    "Enrolled Date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                    "Batch Name": batch_name,
                    "Candidate Folder": candidate.candidate_folder,
                    "GitHub Link": candidate.github_link,
                    "Notes": candidate.notes
                },
                "Emergency Contact": {
                    "Emergency Contact Name": candidate.emergcontactname,
                    "Emergency Contact Phone": candidate.emergcontactphone,
                    "Emergency Contact Email": candidate.emergcontactemail,
                    "Emergency Contact Address": candidate.emergcontactaddrs
                },
                "Fee & Financials": {
                    "Fee Paid": candidate.fee_paid,
                    "Payment Status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
                    "Notes": candidate.notes
                },
                "Preparation Records": preparation_records,
                "Marketing Records": marketing_records,
                "Interview Records": interview_records,
                "Placement Records": placement_records,
                "Login & Access": {
                    "Login Count": authuser.logincount if authuser else 0,
                    "Last Login": authuser.lastlogin.isoformat() if authuser and authuser.lastlogin else None,
                    "Registered Date": authuser.registereddate.isoformat() if authuser and authuser.registereddate else None,
                    "Status": authuser.status if authuser else "No Account",
                    "Reset Token": "Set" if authuser and authuser.reset_token else "Not Set",
                    "Google ID": authuser.googleId if authuser else None
                },
                "Miscellaneous": {
                    "Notes": candidate.notes,
                    "Preparation Active": len(preparation_records) > 0,
                    "Marketing Active": len(marketing_records) > 0,
                    "Placement Active": len(placement_records) > 0
                }
            }

            results.append(candidate_data)

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