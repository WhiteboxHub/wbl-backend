
# wbl-backend\fapi\api\routes\register.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import hashlib
from fapi.db.schemas import UserRegistration
from fapi.db.database import get_db
from fapi.utils import register_utils
from fapi.utils.register_utils import get_db



router = APIRouter()

def md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

@router.post("/api/signup", status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    user: UserRegistration,
    db: AsyncSession = Depends(get_db)
):
    existing_user = await register_utils.get_user_by_username(db, user.uname)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    user_data = user.dict()
    user_data["passwd"] = md5_hash(user.passwd)
    user_data["registereddate"] = user_data.get("registereddate") or datetime.utcnow()
    user_data["fullname"] = user_data.get("fullname") or user_data.get("uname")

    user_record = await register_utils.insert_user(db, user_data)

    lead_data = {
        "full_name": user_data["fullname"],
        "phone": user_data.get("phone"),
        "email": user_data.get("uname"),
        "address": user_data.get("address"),
        "workstatus": None,
        "status": "Open",
        "visa_status": user_data.get("visa_status"),
        "experience": user_data.get("experience"),
        "education": user_data.get("education"),
        "referby": user_data.get("referby"),
        "specialization": user_data.get("specialization")
    }

    await register_utils.insert_lead(db, lead_data)

    return {
        "message": "User registered successfully",
        "user_id": user_record.id
    }



