import json
from fapi.db.database import SessionLocal
from fapi.db.models import CandidateOnboardingState, CandidateORM
from fapi.utils.onboarding_utils import serialize_onboarding_state

def debug_candidate():
    db = SessionLocal()
    email = "sonaliojha86@gmail.com"

    cand = db.query(CandidateORM).filter(CandidateORM.email == email).first()
    if cand:
        print(f"Candidate Enrolled Date: {cand.enrolled_date}")

    state = db.query(CandidateOnboardingState).filter(CandidateOnboardingState.email == email).first()
    if state:
        print("\n--- ONBOARDING STATE IN DB ---")
        # Use a list of column names to avoid NameError
        cols = [c.name for c in state.__table__.columns]
        data = {k: getattr(state, k) for k in cols}
        
        # Convert datetime objects to string for json serialization
        for k, v in data.items():
            if hasattr(v, "isoformat"):
                data[k] = v.isoformat()
        
        print(json.dumps(data, indent=2))
        
        print("\n--- SERIALIZED OUTCOME ---")
        print(json.dumps(serialize_onboarding_state(state), indent=2))
    else:
        print(f"\nNo CandidateOnboardingState found for {email}")
        
    db.close()

if __name__ == "__main__":
    debug_candidate()
