from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fapi.db.database import SessionLocal
from fapi.db.models import LeadORM,CandidateORM
from typing import Dict,Any
from fastapi import HTTPException
from sqlalchemy import func
from fapi.db.models import LeadORM,CandidateORM
from datetime import datetime
from fapi.db.schemas import LeadCreate
from typing import Optional
from sqlalchemy.exc import SQLAlchemyError
import logging

logger=logging.getLogger(__name__)

def fetch_all_leads_paginated(page: int, limit: int) -> Dict[str, any]:
    db: Session = SessionLocal()
    try:
        total = db.query(func.count(LeadORM.id)).scalar()
        offset = (page - 1) * limit

        leads = (
            db.query(LeadORM)
            .order_by(LeadORM.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Convert SQLAlchemy models to dict
        leads_data = [lead.__dict__ for lead in leads]
        for lead in leads_data:
            lead.pop('_sa_instance_state', None)  # remove SQLAlchemy internal data

        return {"page": page, "limit": limit, "total": total, "data": leads_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()




def get_lead_by_id(lead_id: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        lead_dict = lead.__dict__.copy()
        lead_dict.pop("_sa_instance_state", None)

        for field in ["entry_date", "closed_date", "last_modified"]:
            if lead_dict.get(field):
                lead_dict[field] = lead_dict[field].isoformat()

        return lead_dict
    finally:
        session.close()

     
def create_lead(lead_data: LeadCreate) -> LeadORM:
    session = SessionLocal()
    try:
        lead_dict = lead_data.dict()

        # Provide fallback for entry_date and last_modified
        if not lead_dict.get("entry_date"):
            lead_dict["entry_date"] = datetime.utcnow()
        if not lead_dict.get("last_modified"):
            lead_dict["last_modified"] = datetime.utcnow()

        new_lead = LeadORM(**lead_dict)
        session.add(new_lead)
        session.commit()
        session.refresh(new_lead)
        return new_lead
    finally:
        session.close()


def update_lead(lead_id: int, lead_data: LeadCreate) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        for key, value in lead_data.dict(exclude_unset=True).items():
            setattr(lead, key, value)

        session.commit()
        session.refresh(lead)

        lead_dict = lead.__dict__.copy()
        lead_dict.pop("_sa_instance_state", None)
        return lead_dict
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

def get_lead_info_mark_move_to_candidate_true(lead_id: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        #  Check if already moved
        if lead.moved_to_candidate:
            logger.warning(f"Lead already moved to candidate: {lead.id}")
            return {"message": "Already moved to candidate", "lead_id": lead.id, "already_moved": True}

        lead.moved_to_candidate = True
        session.commit()
        session.refresh(lead)

        lead_dict = lead.__dict__.copy()
        lead_dict.pop("_sa_instance_state", None)
        return lead_dict
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# def create_candidate_from_lead(lead: LeadORM) -> Any:
#     session = SessionLocal()
#     try:
#         normalized_email = lead["email"].strip().lower()
#         # Check if a candidate with the same email already exists
#         existing_candidate = session.query(CandidateORM).filter(CandidateORM.email == normalized_email).first()
#         print(f"found existing as {existing_candidate}")
#         if existing_candidate:
#             raise HTTPException(status_code=400, detail="Candidate with this email already exists")

#         # Create CandidateORM object from lead data
#         candidate = CandidateORM(
#             full_name=lead['full_name'],
#             enrolled_date=lead['entry_date'],  # Mapping entry_date from lead to enrolled_date in candidate
#             email=normalized_email,
#             phone=lead['phone'],
#             status='active',
#             workstatus=lead['workstatus'],
#             education=None,                # Not present in lead, set to None or default
#             workexperience=None,          # Not present in lead
#             ssn=None,
#             agreement=None,
#             secondaryemail=lead['secondary_email'],
#             secondaryphone=lead['secondary_phone'],
#             address=lead['address'],
#             linkedin_id=None,
#             dob=None,
#             emergcontactname=None,
#             emergcontactemail=None,
#             emergcontactphone=None,
#             emergcontactaddrs=None,
#             fee_paid=None,
#             notes=lead['notes'],
#             batchid=99
#         )

#         # Add to session and commit
#         session.add(candidate)
#         session.commit()
#         session.refresh(candidate)

#         return {
#             "message": "Success! Lead moved to candidate ",
#             "candidate_id": candidate.id,
#             "success":True
#         }

#     except IntegrityError as e:
#         print(e)
#         session.rollback()
#         raise HTTPException(status_code=400, detail="Email must be unique. A candidate with this email already exists.")
#     except Exception as e:
#         session.rollback()
#         raise HTTPException(status_code=500, detail=f"Error creating candidate: {str(e)}")
#     finally:
#         session.close()
VALID_WORKSTATUS = ['Citizen', 'Visa', 'Permanent resident', 'EAD', 'Waiting for Status']

def create_candidate_from_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        normalized_email = lead["email"].strip().lower()
        existing_candidate = session.query(CandidateORM).filter(
            CandidateORM.email == normalized_email
        ).first()
        if existing_candidate:
            raise HTTPException(status_code=400, detail="Candidate with this email already exists")

        # Validate workstatus
        workstatus_value = lead.get('workstatus')
        if workstatus_value not in VALID_WORKSTATUS:
            workstatus_value = 'Waiting for Status'

        candidate = CandidateORM(
            full_name=lead['full_name'],
            enrolled_date=lead.get('entry_date') or datetime.utcnow(),
            email=normalized_email,
            phone=lead.get('phone'),
            status='active',
            workstatus=workstatus_value,
            education=None,
            workexperience=None,
            ssn=None,
            agreement='N',
            secondaryemail=lead.get('secondary_email'),
            secondaryphone=lead.get('secondary_phone'),
            address=lead.get('address'),
            linkedin_id=None,
            dob=None,
            emergcontactname=None,
            emergcontactemail=None,
            emergcontactphone=None,
            emergcontactaddrs=None,
            fee_paid=None,
            notes=lead.get('notes'),
            batchid=99
        )

        session.add(candidate)
        session.commit()
        session.refresh(candidate)

        # Only now mark lead as moved
        lead_obj = session.query(LeadORM).filter(LeadORM.id == lead['id']).first()
        if lead_obj:
            lead_obj.moved_to_candidate = True
            session.commit()
            session.refresh(lead_obj)

        return {"message": "Success! Lead moved to candidate", "candidate_id": candidate.id, "success": True}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating candidate: {str(e)}")
    finally:
        session.close()



def check_and_reset_moved_to_candidate(lead_id: int) -> str:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        if lead.moved_to_candidate:
            lead.moved_to_candidate = False
            session.commit()
            session.refresh(lead)

        return {
                "email": lead.email,
                "phone": lead.phone
            }

    except Exception as e:
        session.rollback()
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        session.close()


def delete_candidate_by_email_and_phone(email: str, phone: Optional[str] = None) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        normalized_email = email.strip().lower()

        # Fetch all candidates with matching email (case-insensitive)
        candidates = session.query(CandidateORM).filter(
            func.lower(CandidateORM.email) == normalized_email
        ).all()

        if not candidates:
            raise HTTPException(status_code=404, detail="No candidate found with the given email")

        # If only one candidate found, delete directly
        if len(candidates) == 1:
            session.delete(candidates[0])
            session.commit()
            return {
                "message": "Candidate deleted successfully",
                "candidate_id": candidates[0].id,
                "success":True
            }

        # If multiple found, phone is required
        if not phone:
            raise HTTPException(
                status_code=400,
                detail="Multiple candidates found with this email. Please provide phone to disambiguate."
            )

        # Find match by phone
        matching_candidate = next((c for c in candidates if c.phone == phone), None)
        if not matching_candidate:
            raise HTTPException(
                status_code=404,
                detail="No candidate found with the provided email and phone combination."
            )

        session.delete(matching_candidate)
        session.commit()
        return {
            "message": "Candidate deleted successfully",
            "candidate_id": matching_candidate.id,
            "success":True
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting candidate: {str(e)}")
    finally:
        session.close()


def delete_lead(lead_id: int) -> Dict[str, str]:
    session = SessionLocal()
    try:
        lead = session.query(LeadORM).filter(LeadORM.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        session.delete(lead)
        session.commit()
        return {"message": "Lead deleted successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



def move_lead_to_candidate(lead_id: int, db: Session):
    """Debugging-enhanced version of the move function"""
    debug_info = {
        'start_time': datetime.utcnow(),
        'lead_id': lead_id,
        'steps': [],
        'errors': []
    }
    
    try:
        # Step 1: Fetch lead
        debug_info['steps'].append('Fetching lead from database')
        lead = db.query(LeadORM).filter(LeadORM.id == lead_id).first()
        
        if not lead:
            debug_info['errors'].append('Lead not found')
            logger.error(f"Debug - Lead not found: {debug_info}")
            raise HTTPException(status_code=404, detail="Lead not found")

        debug_info['lead_data'] = {
            'id': lead.id,
            'full_name': lead.full_name,
            'email': lead.email,
            'moved_to_candidate': lead.moved_to_candidate
        }

        # Step 2: Check if already moved
        if lead.moved_to_candidate:
            debug_info['steps'].append('Lead already moved to candidate')
            logger.info(f"Debug - Lead already moved: {debug_info}")
            return {
                "message": "Already moved to candidate",
                "lead_id": lead.id,
                "already_moved": True,
                "debug": debug_info
            }

        # Step 3: Prepare candidate data
        debug_info['steps'].append('Preparing candidate data')
        candidate_data = {
            'full_name': lead.full_name,
            'email': lead.email,
            'phone': lead.phone,
            'address': lead.address,
            'workstatus': lead.workstatus,
            'entry_date': lead.entry_date or datetime.utcnow(),
            'status': 'active',
            'notes': lead.notes,
            'batchid': 1, 
            'enrolled_date': datetime.utcnow().date(),
            'agreement': 'N'
        }
        debug_info['candidate_data'] = candidate_data

     
        debug_info['steps'].append('Creating candidate record')
        new_candidate = CandidateORM(**candidate_data)
        db.add(new_candidate)
    
        
        debug_info['steps'].append('Pre-commit verification')
        debug_info['pre_commit'] = {
            'new_candidate_id': getattr(new_candidate, 'id', None),
            'lead_moved_status': lead.moved_to_candidate
        }

      
        lead.moved_to_candidate = True
        debug_info['steps'].append('Lead marked for update')

        debug_info['steps'].append('Committing transaction')
        db.commit()
        
       
        debug_info['steps'].append('Refreshing objects')
        db.refresh(lead)
        db.refresh(new_candidate)
        debug_info['post_commit'] = {
            'new_candidate_id': new_candidate.id,
            'lead_moved_status': lead.moved_to_candidate,
            'candidate_created_at': new_candidate.entry_date
        }

        debug_info['end_time'] = datetime.utcnow()
        debug_info['success'] = True
        logger.info(f"Debug - Successfully moved lead: {debug_info}")

        return {
            "message": "Lead moved to candidate successfully",
            "lead_id": lead.id,
            "candidate_id": new_candidate.id,
            "debug_info": debug_info  # Include debug info in response for testing
        }

    except SQLAlchemyError as e:
        db.rollback()
        debug_info['errors'].append(f"Database error: {str(e)}")
        debug_info['end_time'] = datetime.utcnow()
        debug_info['success'] = False
        logger.error(f"Debug - Database error: {debug_info}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Database error",
                "debug_info": debug_info
            }
        )
    except Exception as e:
        db.rollback()
        debug_info['errors'].append(f"Unexpected error: {str(e)}")
        debug_info['end_time'] = datetime.utcnow()
        debug_info['success'] = False
        logger.error(f"Debug - Unexpected error: {debug_info}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "debug_info": debug_info
            }
        )