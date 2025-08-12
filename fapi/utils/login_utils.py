# wbl-backend/fapi/utils/login_utils.py
from sqlalchemy.orm import Session
from fapi.utils.db_queries import get_user_by_username, fetch_candidate_id_and_status_by_email
from fapi.utils.auth_utils import verify_md5_hash

async def authenticate_user(uname: str, passwd: str, db: Session):
    user = get_user_by_username(db, uname)
    if not user or not verify_md5_hash(passwd, user.passwd):
        return None

    if uname.lower() == "admin":
        return {**user.__dict__, "candidateid": None}

    if user.status.lower() != "active":
        return "inactive_authuser"

    candidate_info = fetch_candidate_id_and_status_by_email(db, uname)
    if not candidate_info:
        return "not_a_candidate"

    if candidate_info.status.lower() != "active":
        return "inactive_candidate"

    return {**user.__dict__, "candidateid": candidate_info.candidateid}




