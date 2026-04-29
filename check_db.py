import sys
from sqlalchemy import create_engine, text

# Connection string based on wbl-backend/.env
engine = create_engine("mysql+pymysql://root:root@127.0.0.1:3306/wbl")

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, source, title FROM job_listing WHERE source='jobright.ai' ORDER BY id DESC LIMIT 10"))
    rows = result.fetchall()
    with open("db_output.txt", "w") as f:
        f.write(f"Count: {len(rows)}\n")
        for r in rows:
            f.write(f"{r}\n")

    # Also count total jobright rows
    result = conn.execute(text("SELECT count(*) FROM job_listing WHERE source='jobright.ai'"))
    count = result.scalar()
    with open("db_output.txt", "a") as f:
        f.write(f"Total jobright rows: {count}\n")
