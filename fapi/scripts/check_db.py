from fapi.db.database import DATABASE_URL
from sqlalchemy import create_engine, text
engine = create_engine(DATABASE_URL)
res = engine.connect().execute(text("SELECT id, uid, document_type, is_approved, approvals_count FROM file_approvals WHERE uid='UID_1776293040608'"))
print("LATEST RECORDS:")
for r in res:
    print(dict(r._mapping))
