from fastapi import APIRouter, Depends
from fapi.utils.user_dashboard_utils import get_current_user
from fapi.db.models import AuthUserORM

router = APIRouter()

@router.get("/user_dashboard")
def read_user_dashboard(current_user: AuthUserORM = Depends(get_current_user)):
    return {
        "uname": current_user.uname,
        # "email": current_user.address,  # change to actual email field if exists
        "full_name": current_user.fullname,
        "phone": current_user.phone
    }
