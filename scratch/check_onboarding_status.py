import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
sys.path.append(r'c:\Users\khaja\P5\wbl-backend')

from fapi.db.database import SessionLocal
from fapi.db import models
from fapi.utils import onboarding_utils

def check_status(email):
    db = SessionLocal()
    try:
        # Check approved files
        files = db.query(models.FileApproval).filter(
            models.FileApproval.email == email,
            models.FileApproval.is_approved == True
        ).all()
        
        state = onboarding_utils.get_or_create_onboarding_state(db, email)
        status = onboarding_utils.serialize_onboarding_state(state)
        print(f"STATUS FOR {email}:")
        import json
        print(json.dumps(status, indent=2))
        
        # Fix status if all approved
        if len([f for f in files if f.document_type in {"id_proof", "address_proof", "work_proof"}]) > 0:
            print("\nID proofs found approved. Fixing state...")
            onboarding_utils.set_id_verification_status(db, email, "verified")
            # Enforce enrollment/placement verified if approved files exist
            if any(f.document_type == "enrollment" for f in files):
                onboarding_utils.mark_agreement_verified(db, email, "enrollment")
            if any(f.document_type == "placement" for f in files):
                onboarding_utils.mark_agreement_verified(db, email, "placement")
            
            db.commit()
            print("Status updated to verified.")
            
            # Recalculate and print final status
            db.refresh(state)
            status = onboarding_utils.serialize_onboarding_state(state)
            print("\nFINAL STATUS:")
            print(json.dumps(status, indent=2))
            
    finally:
        db.close()

if __name__ == "__main__":
    check_status("sonaliojha86@gmail.com")
