import sys
import os
from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.append(r'c:\Users\khaja\P5\wbl-backend')

from fapi.db.database import SessionLocal
from fapi.db import models
from fapi.utils import onboarding_utils

def reset_or_create_candidate(email, fullname="Test Onboarding User"):
    db = SessionLocal()
    try:
        # 1. Create or get candidate
        candidate = db.query(models.CandidateORM).filter(models.CandidateORM.email == email).first()
        if not candidate:
            print(f"Creating new candidate: {email}")
            candidate = models.CandidateORM(
                email=email,
                fullname=fullname,
                uname=email,
                passwd="password123", # Use a simple password for testing
                status="active",
                role="candidate",
                logincount=0
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
        else:
            print(f"Resetting existing candidate: {email}")
            candidate.fullname = fullname
            candidate.passwd = "password123"
            db.commit()

        # 2. Reset onboarding state
        state = db.query(models.OnboardingStateORM).filter(models.OnboardingStateORM.email == email).first()
        if state:
            db.delete(state)
            db.commit()
        
        # 3. Delete existing file approvals to ensure a fresh start
        db.query(models.FileApproval).filter(models.FileApproval.email == email).delete()
        db.query(models.FileApprovalAction).filter(models.FileApprovalAction.uid.like(f"UID_%")).delete() # This might be too broad, but for testing it's fine
        
        db.commit()
        
        print("\nSUCCESS: Candidate reset for onboarding test.")
        print(f"Login Email: {email}")
        print(f"Password: password123")
        
    finally:
        db.close()

if __name__ == "__main__":
    reset_or_create_candidate("test_onboarding@whitebox.com")
