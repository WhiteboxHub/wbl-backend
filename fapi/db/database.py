# wbl-backend/fapi/db/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote

load_dotenv()

# Read from environment variables
raw_password = os.getenv('DB_PASSWORD')
if raw_password is None:
    raise ValueError("DB_PASSWORD environment variable is not set")
encoded_password = quote(raw_password)

host = os.getenv('DB_HOST')
if host is None:
    raise ValueError("DB_HOST environment variable is not set")

user = os.getenv('DB_USER')
if user is None:
    raise ValueError("DB_USER environment variable is not set")

database = os.getenv('DB_NAME')
if database is None:
    raise ValueError("DB_NAME environment variable is not set")

port_str = os.getenv('DB_PORT')
if port_str is None:
    raise ValueError("DB_PORT environment variable is not set")
port_int = int(port_str)

# SQLAlchemy URL (sync engine with pymysql)
DATABASE_URL = (
    f"mysql+pymysql://{user}:{encoded_password}"
    f"@{host}:{port_int}/{database}"
)

# Engine and Session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
