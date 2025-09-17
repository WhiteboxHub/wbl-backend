# wbl-backend/fapi/utils/candidate_utils.py

from sqlalchemy.orm import Session, joinedload, selectinload,contains_eager
from sqlalchemy import or_
from fapi.db.database import SessionLocal,get_db
from fapi.db.models import CandidateORM, CandidatePlacementORM,CandidateMarketingORM,CandidateInterview,CandidatePreparation
from fapi.db.schemas import CandidateMarketingCreate, CandidateInterviewCreate,CandidatePlacementUpdate,CandidateMarketingUpdate,CandidateInterviewUpdate,CandidatePreparationCreate, CandidatePreparationUpdate
from fastapi import HTTPException,APIRouter,Depends
from typing import List, Dict,Any
from datetime import date

router = APIRouter()
      
# def get_all_candidates_paginated(
#     db: Session,
#     page: int = 1,
#     limit: int = 0,
#     search: str = None,
#     search_by: str = "all",
#     sort: str = "enrolled_date:desc"  
# ) -> Dict[str, Any]:
#     query = db.query(CandidateORM)

#     if search:
#         if search_by == "id":
#             try:
#                 query = query.filter(CandidateORM.id == int(search))
#             except ValueError:
#                 query = query.filter(CandidateORM.id == -1)
#         elif search_by == "full_name":
#             query = query.filter(CandidateORM.full_name.ilike(f"%{search}%"))
#         elif search_by == "email":
#             query = query.filter(CandidateORM.email.ilike(f"%{search}%"))
#         elif search_by == "phone":
#             query = query.filter(CandidateORM.phone.ilike(f"%{search}%"))
#         else:  # search_by == "all"
#             query = query.filter(
#                 or_(
#                     CandidateORM.full_name.ilike(f"%{search}%"),
#                     CandidateORM.email.ilike(f"%{search}%"),
#                     CandidateORM.phone.ilike(f"%{search}%"),
#                 )
#             )

    
#     if sort:
#         sort_fields = sort.split(",")
#         for field in sort_fields:
#             col, direction = field.split(":")
#             if not hasattr(CandidateORM, col):
#                 raise HTTPException(status_code=400, detail=f"Cannot sort by field: {col}")
#             column = getattr(CandidateORM, col)
#             if direction == "desc":
#                 query = query.order_by(column.desc())
#             else:
#                 query = query.order_by(column.asc())

#     total = query.count()
#     candidates = query.offset((page - 1) * limit).limit(limit).all()

#     data = []
#     for candidate in candidates:
#         item = candidate.__dict__.copy()
#         item.pop('_sa_instance_state', None)
#         data.append(item)

#     return {"data": data, "total": total, "page": page, "limit": limit}


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
    try:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        for key, value in candidate_data.items():
            setattr(candidate, key, value)
        db.commit()  
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
        results = (
            db.query(CandidateMarketingORM)
            .options(
                joinedload(CandidateMarketingORM.candidate),
                joinedload(CandidateMarketingORM.instructor1),
                joinedload(CandidateMarketingORM.instructor2),
                joinedload(CandidateMarketingORM.instructor3),
                joinedload(CandidateMarketingORM.marketing_manager_obj),
            )
            .order_by(CandidateMarketingORM.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return {"page": page, "limit": limit, "total": total, "data": results}
    finally:
        db.close()


# Get marketing by candidate ID
def get_marketing_by_candidate_id(candidate_id: int):
    db: Session = SessionLocal()
    try:
        records = (
            db.query(CandidateMarketingORM)
            .options(
                joinedload(CandidateMarketingORM.candidate),
                joinedload(CandidateMarketingORM.instructor1),
                joinedload(CandidateMarketingORM.instructor2),
                joinedload(CandidateMarketingORM.instructor3),
                joinedload(CandidateMarketingORM.marketing_manager_obj),
            )
            .filter(CandidateMarketingORM.candidate_id == candidate_id)
            .all()
        )
        if not records:
            raise HTTPException(status_code=404, detail="No marketing records found for this candidate")
        return {"candidate_id": candidate_id, "data": records}
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


def update_marketing(record_id: int, payload: CandidateMarketingUpdate) -> Dict:
    db: Session = SessionLocal()
    try:
        # Lookup by candidate_id
        record = (
            db.query(CandidateMarketingORM)
            .filter(CandidateMarketingORM.candidate_id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Marketing record not found")

        update_data = payload.dict(exclude_unset=True)

        for key, value in update_data.items():
            # Skip relationship fields (dicts)
            if isinstance(value, dict):
                continue

            if hasattr(record, key):
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
            # .order_by(CandidatePlacementORM.id.desc())
            .order_by(CandidatePlacementORM.priority.desc())  # ORDER BY priority
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
            CandidatePlacementORM.id == placement_id   # use id, not candidate_id
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

# def create_candidate_interview(db: Session, interview: CandidateInterviewCreate):
#     data = interview.dict()

#     # Normalize interviewer_emails to lowercase if provided
#     if data.get("interviewer_emails"):
#         data["interviewer_emails"] = ",".join(
#             [email.strip().lower() for email in data["interviewer_emails"].split(",")]
#         )

#     db_obj = CandidateInterview(**data)
#     db.add(db_obj)
#     db.commit()
#     db.refresh(db_obj)
#     return db_obj


def create_candidate_interview(db: Session, interview: CandidateInterviewCreate):
    data = interview.dict()

    # Normalize interviewer_emails to lowercase if provided
    if data.get("interviewer_emails"):
        data["interviewer_emails"] = ",".join(
            [email.strip().lower() for email in data["interviewer_emails"].split(",")]
        )

    # URL field is already included in `data` via dict()
    db_obj = CandidateInterview(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_candidate_interviews(db: Session, skip: int = 0, limit: int = 100):
    return db.query(CandidateInterview).options(contains_eager(CandidateInterview.candidate)) .join(CandidateORM, CandidateInterview.candidate_id == CandidateORM.id).offset(skip).limit(limit).all()


def get_candidate_interview(db: Session, interview_id: int):
    return db.query(CandidateInterview).options(joinedload(CandidateInterview.candidate)).filter(CandidateInterview.id == interview_id).first()


def update_candidate_interview(db: Session, interview_id: int, updates: CandidateInterviewUpdate):
    db_obj = db.query(CandidateInterview).options(joinedload(CandidateInterview.candidate)) .join(CandidateORM, CandidateInterview.candidate_id == CandidateORM.id).filter(CandidateInterview.id == interview_id).first()
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
    db_obj = db.query(CandidateInterview).filter(CandidateInterview.id == interview_id).first()
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
            joinedload(CandidatePreparation.candidate),
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

##-------------------------------------------------search---------------------------------------------------------------
# def search_candidates_comprehensive(search_term: str, db: Session) -> List[Dict]:
#     """
#     Search candidates by name and return comprehensive information for accordion display
#     """
#     try:
#         # Search candidates by name (case-insensitive, partial match)
#         candidates = (
#             db.query(CandidateORM)
#             .filter(CandidateORM.full_name.ilike(f"%{search_term}%"))
#             .all()
#         )
        
#         if not candidates:
#             return []
        
#         results = []
        
#         for candidate in candidates:
#             # Get batch name - Fix the import and query
#             try:
#                 from fapi.db.models import Batch
#                 batch = db.query(Batch).filter(Batch.batchid == candidate.batchid).first()
#                 batch_name = batch.batchname if batch else "Unknown Batch"
#             except:
#                 batch_name = f"Batch ID: {candidate.batchid}"
            
#             # Get authuser info (join by email)
#             authuser = None
#             try:
#                 from fapi.db.models import AuthUserORM
#                 if candidate.email:
#                     authuser = db.query(AuthUserORM).filter(AuthUserORM.uname.ilike(candidate.email)).first()
#             except:
#                 pass
            
#             # Get preparation records with error handling
#             preparation_records = []
#             try:
#                 prep_data = db.query(CandidatePreparation).filter(CandidatePreparation.candidate_id == candidate.id).all()
#                 for prep in prep_data:
#                     # Get instructor names safely
#                     try:
#                         from fapi.db.models import EmployeeORM
#                         inst1_name = None
#                         inst2_name = None
#                         inst3_name = None
                        
#                         if prep.instructor1_id:
#                             inst1 = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor1_id).first()
#                             inst1_name = inst1.name if inst1 else None
                        
#                         if prep.instructor2_id:
#                             inst2 = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor2_id).first()
#                             inst2_name = inst2.name if inst2 else None
                            
#                         if prep.instructor3_id:
#                             inst3 = db.query(EmployeeORM).filter(EmployeeORM.id == prep.instructor3_id).first()
#                             inst3_name = inst3.name if inst3 else None
                        
#                         prep_record = {
#                             "start_date": prep.start_date.isoformat() if prep.start_date else None,
#                             "status": prep.status,
#                             "instructor1_name": inst1_name,
#                             "instructor2_name": inst2_name, 
#                             "instructor3_name": inst3_name,
#                             "rating": prep.rating,
#                             "tech_rating": prep.tech_rating,
#                             "communication": prep.communication,
#                             "years_of_experience": prep.years_of_experience,
#                             "topics_finished": prep.topics_finished,
#                             "current_topics": prep.current_topics,
#                             "target_date_of_marketing": prep.target_date_of_marketing.isoformat() if prep.target_date_of_marketing else None,
#                             "notes": prep.notes,
#                             "last_mod_date": prep.last_mod_date.isoformat() if prep.last_mod_date else None
                            
#                         }
#                         preparation_records.append(prep_record)
#                     except Exception as e:
#                         # Add record with error info
#                         preparation_records.append({"error": f"Error loading prep record: {str(e)}"})
#             except:
#                 pass
            
#             # Get marketing records with error handling
#             marketing_records = []
#             try:
#                 marketing_data = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == candidate.id).all()
#                 for marketing in marketing_data:
#                     try:
#                         from fapi.db.models import EmployeeORM
#                         manager_name = None
#                         if marketing.marketing_manager:
#                             manager = db.query(EmployeeORM).filter(EmployeeORM.id == marketing.marketing_manager).first()
#                             manager_name = manager.name if manager else None
                        
#                         marketing_record = {
#                             "start_date": marketing.start_date.isoformat() if marketing.start_date else None,
#                             "status": marketing.status,
#                             "marketing_manager_name": manager_name,
#                             "notes": marketing.notes,
#                             "last_mod_date": marketing.last_mod_date.isoformat() if marketing.last_mod_date else None
#                         }
#                         marketing_records.append(marketing_record)
#                     except Exception as e:
#                         marketing_records.append({"error": f"Error loading marketing record: {str(e)}"})
#             except:
#                 pass
            
#             # Get interview records with error handling
#             interview_records = []
#             try:
#                 interview_data = db.query(CandidateInterview).filter(CandidateInterview.candidate_id == candidate.id).all()
#                 for interview in interview_data:
#                     try:
#                         interview_record = {
#                             "company": interview.company,
#                             "interview_date": interview.interview_date.isoformat() if interview.interview_date else None,
#                             "interview_type": interview.interview_type,
#                             "status": interview.status,
#                             "feedback": interview.feedback,
#                             "recording_link": interview.recording_link,
#                             "notes": interview.notes
#                         }
#                         interview_records.append(interview_record)
#                     except Exception as e:
#                         interview_records.append({"error": f"Error loading interview record: {str(e)}"})
#             except:
#                 pass
            
#             # Get placement records with error handling  
#             placement_records = []
#             try:
#                 placement_data = db.query(CandidatePlacementORM).filter(CandidatePlacementORM.candidate_id == candidate.id).all()
#                 for placement in placement_data:
#                     try:
#                         placement_record = {
#                             "position": placement.position,
#                             "company": placement.company,
#                             "placement_date": placement.placement_date.isoformat() if placement.placement_date else None,
#                             "status": placement.status,
#                             "type": placement.type,
#                             "base_salary_offered": float(placement.base_salary_offered) if placement.base_salary_offered else None,
#                             "benefits": placement.benefits,
#                             "fee_paid": float(placement.fee_paid) if placement.fee_paid else None,
#                             "last_mod_date": placement.last_mod_date.isoformat() if placement.last_mod_date else None,
#                             "notes": placement.notes
#                         }
#                         placement_records.append(placement_record)
#                     except Exception as e:
#                         placement_records.append({"error": f"Error loading placement record: {str(e)}"})
#             except:
#                 pass
            
#             # Compile comprehensive candidate data with safe date conversions
#             candidate_data = {
#                 "candidate_id": candidate.id,
                
#                 # Section 1: Basic Information
#                 "basic_info": {
#                     "full_name": candidate.full_name,
#                     "email": candidate.email,
#                     "phone": candidate.phone,
#                     "secondaryemail": candidate.secondaryemail,
#                     "secondaryphone": candidate.secondaryphone,
#                     "linkedin_id": candidate.linkedin_id,
#                     "status": candidate.status,
#                     "workstatus": candidate.workstatus,
#                     "education": candidate.education,
#                     "workexperience": candidate.workexperience,
#                     "ssn": "***-**-" + candidate.ssn[-4:] if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
#                     "dob": candidate.dob.isoformat() if candidate.dob else None,
#                     "address": candidate.address,
#                     "agreement": candidate.agreement,
#                     "enrolled_date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
#                     "batch_name": batch_name,
#                     "candidate_folder": candidate.candidate_folder,
#                     "notes": candidate.notes
#                 },
                
#                 # Section 2: Emergency Contact
#                 "emergency_contact": {
#                     "emergcontactname": candidate.emergcontactname,
#                     "emergcontactphone": candidate.emergcontactphone,
#                     "emergcontactemail": candidate.emergcontactemail,
#                     "emergcontactaddrs": candidate.emergcontactaddrs
#                 },
                
#                 # Section 3: Fee & Financials
#                 "fee_financials": {
#                     "fee_paid": candidate.fee_paid,
#                     "payment_status": "Paid" if candidate.fee_paid and candidate.fee_paid > 0 else "Pending",
#                     "notes": candidate.notes
#                 },
                
#                 # Section 4-7: Tables (1-to-many)
#                 "preparation_records": preparation_records,
#                 "marketing_records": marketing_records,
#                 "interview_records": interview_records,
#                 "placement_records": placement_records,
                
#                 # Section 8: Login & Access Info
#                 "login_access": {
#                     "logincount": authuser.logincount if authuser else 0,
#                     "lastlogin": authuser.lastlogin.isoformat() if authuser and authuser.cd  else None,
#                     "registereddate": authuser.registereddate.isoformat() if authuser and authuser.registereddate else None,
#                     "status": authuser.status if authuser else "No Account",
#                     "reset_token": "Set" if authuser and authuser.reset_token else "Not Set",
#                     "googleId": authuser.googleId if authuser else None
#                 },
                
#                 # Section 9: Miscellaneous
#                 "miscellaneous": {
#                     "notes": candidate.notes,
#                     "preparation_active": len(preparation_records) > 0,
#                     "marketing_active": len(marketing_records) > 0,
#                     "placement_active": len(placement_records) > 0
#                 }
#             }
            
#             results.append(candidate_data)
        
#         return results
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")



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
                            "Status": prep.status,
                            "Instructor 1 Name": inst1_name,
                            "Instructor 2 Name": inst2_name,
                            "Instructor 3 Name": inst3_name,
                            "Rating": prep.rating,
                            "Tech Rating": prep.tech_rating,
                            "Communication": prep.communication,
                            "Years of Experience": prep.years_of_experience,
                            "Topics Finished": prep.topics_finished,
                            "Current Topics": prep.current_topics,
                            "Target Date of Marketing": prep.target_date_of_marketing.isoformat() if prep.target_date_of_marketing else None,
                            "Notes": prep.notes,
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
                            "Status": marketing.status,
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
                    "SSN": "***-**-" + candidate.ssn[-4:] if candidate.ssn and len(str(candidate.ssn)) >= 4 else "Not Provided",
                    "Date of Birth": candidate.dob.isoformat() if candidate.dob else None,
                    "Address": candidate.address,
                    "Agreement": candidate.agreement,
                    "Enrolled Date": candidate.enrolled_date.isoformat() if candidate.enrolled_date else None,
                    "Batch Name": batch_name,
                    "Candidate Folder": candidate.candidate_folder,
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