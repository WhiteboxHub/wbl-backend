from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.utils.user_dashboard_utils import get_current_user
from fapi.db.models import AuthUserORM, CandidateORM
from fapi.db.database import get_db

router = APIRouter()

security = HTTPBearer()

@router.get("/user_dashboard")
def read_user_dashboard(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    candidate = db.query(CandidateORM).filter(CandidateORM.email == current_user.uname).first()
    
    return {
        "uname": current_user.uname,
        "full_name": current_user.fullname,
        "phone": current_user.phone,
        "login_count": current_user.logincount,
        "candidate_id": candidate.id if candidate else None,
    }