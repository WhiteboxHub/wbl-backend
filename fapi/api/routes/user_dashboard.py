from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fapi.utils.user_dashboard_utils import get_current_user
from fapi.db.models import AuthUserORM

router = APIRouter()

security = HTTPBearer()

@router.get("/user_dashboard")
def read_user_dashboard(
    current_user: AuthUserORM = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return {
        "uname": current_user.uname,
        "full_name": current_user.fullname,
        "phone": current_user.phone,
        "login_count": current_user.logincount,
    }
