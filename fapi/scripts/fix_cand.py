from datetime import datetime
from fapi.db.database import SessionLocal
from fapi.db.models import CandidateORM, AuthUserORM

db = SessionLocal()
email = "sonaliojha86@gmail.com"

cand = db.query(CandidateORM).filter(CandidateORM.email == email).first()
if cand:
    cand.enrolled_date = datetime.now()
    
# also clear logincount and lastlogin just in case
user = db.query(AuthUserORM).filter(AuthUserORM.uname == email).first()
if user:
    user.lastlogin = None
    user.logincount = 0

db.commit()
db.close()
print("Fixed candidate enrolled date to today.")
