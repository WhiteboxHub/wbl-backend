import sys
import os
import hashlib
from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.append(r'c:\Users\khaja\P5\wbl-backend')

from fapi.db.database import SessionLocal
from fapi.db import models
from fapi.utils import onboarding_utils

def md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def prepare_walkthrough(email, fullname="Walkthrough Test User"):
    db = SessionLocal()
    try:
        # 1. Setup AuthUser
        auth_user = db.query(models.AuthUserORM).filter(models.AuthUserORM.uname == email).first()
        if not auth_user:
            print(f"Creating AuthUser: {email}")
            auth_user = models.AuthUserORM(
                uname=email,
                passwd=md5_hash("password123"),
                status="active",
                role="candidate",
                fullname=fullname
            )
            db.add(auth_user)
        else:
            print(f"Resetting AuthUser: {email}")
            auth_user.passwd = md5_hash("password123")
            auth_user.status = "active"
            auth_user.role = "candidate"
        
        # 2. Setup Candidate
        candidate = db.query(models.CandidateORM).filter(models.CandidateORM.email == email).first()
        if not candidate:
            print(f"Creating Candidate: {email}")
            candidate = models.CandidateORM(
                email=email,
                full_name=fullname,
                status="active",
                batchid=1 # Assuming batch 1 exists
            )
            db.add(candidate)
        else:
            print(f"Resetting Candidate: {email}")
            candidate.status = "active"
            candidate.full_name = fullname
        
        db.commit()
        db.refresh(candidate)

        # 3. Clean Onboarding State
        state = db.query(models.CandidateOnboardingState).filter(models.CandidateOnboardingState.email == email).first()
        if state:
            print(f"Deleting existing OnboardingState for {email}")
            db.delete(state)
        
        # 4. Clean File Approvals
        db.query(models.FileApproval).filter(models.FileApproval.email == email).delete()
        
        db.commit()
        print("\nSUCCESS: Walkthrough environment ready.")
        print(f"Login: {email} / password123")
        
    finally:
        db.close()

if __name__ == "__main__":
    prepare_walkthrough("test_onboarding@whitebox.com")
