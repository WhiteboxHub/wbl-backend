from fastapi import APIRouter, Depends
from fapi.db.schemas import UserOut
from fapi.utils.user_dashboard_utils import get_current_user

router = APIRouter()

@router.get("/user_dashboard", response_model=UserOut)
def read_user_dashboard(
    current_user: UserOut = Depends(get_current_user)
):
    return current_user
