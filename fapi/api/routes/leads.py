from fastapi import APIRouter, Query, Path,HTTPException,FastAPI
from typing import Dict, Any
from fapi.db.schemas import LeadSchema, LeadCreate
from fapi.utils.lead_utils import fetch_all_leads_paginated, get_lead_by_id, create_lead, update_lead, delete_lead,check_and_reset_moved_to_candidate
import logging

from fapi.utils.lead_utils import delete_lead,delete_candidate_by_email_and_phone,create_candidate_from_lead,get_lead_info_mark_move_to_candidate_true
logger=logging.getLogger(__name__)

router= APIRouter()




@router.get("/leads", summary="Get all leads (paginated)")
async def get_all_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    return fetch_all_leads_paginated(page, limit)


@router.get("/leads/{lead_id}")
def read_lead(lead_id: int = Path(...)) -> Dict[str, Any]:
    return get_lead_by_id(lead_id)


@router.post("/leads", response_model=LeadSchema)
def create_new_lead(lead: LeadCreate):
    return create_lead(lead)


@router.put("/leads/{lead_id}")
def update_existing_lead(lead_id: int, lead: LeadCreate) -> Dict[str, Any]:
    return update_lead(lead_id, lead)


@router.delete("/leads/{lead_id}")
def delete_existing_lead(lead_id: int) -> Dict[str, str]:
    return delete_lead(lead_id)


@router.post("/leads/movetocandidate/{lead_id}")
def move_to_candidate_endpoint(lead_id: int):
    logger.info(f"Starting move_to_candidate for lead_id: {lead_id}")
    
    try:
       
        logger.info("Beginning database transaction")
        
        logger.info(f"Querying lead with id: {lead_id}")
        leaddata = get_lead_info_mark_move_to_candidate_true(lead_id)
        print(" here2")
      
        if leaddata.get("already_moved",False):
            logger.info(f"Lead already moved: ID={leaddata['lead_id']}, AlreadyMoved={leaddata['already_moved']}")
            raise HTTPException(status_code=404, detail=leaddata["message"])

        
        
        
        logger.info("Creating new candidate record")
        
        create_candidate = create_candidate_from_lead(leaddata)
        
        if create_candidate['success']:
        
            logger.info(" New candidate added to session")
            
          
            logger.info(f"Lead marked as moved: {leaddata['id']}")
            
            
            logger.info(" Committing transaction...")
            
            logger.info("Transaction committed successfully")
            return {
            "message": "Lead moved to candidate successfully",
            "lead_id": leaddata['id'],
            "candidate_id": create_candidate['candidate_id']
            }
    except HTTPException as he:
        
        raise he

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/leads/movetocandidate/{lead_id}")
def delete_candidate_move(lead_id : int):
    try:
        data = check_and_reset_moved_to_candidate(lead_id)
       
        res = delete_candidate_by_email_and_phone(data['email'],data['phone'])
        print(res)
        if res['success']:
            return {
            "message": "Candidate deleted successfully",
            "candidate_id": res['candidate_id'],
            }
        else:
            raise Exception
    except HTTPException as he:
        
        raise he

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")