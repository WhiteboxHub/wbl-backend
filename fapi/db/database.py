# wbl-backend/fapi/db/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote

load_dotenv()

# Read from environment variables
raw_password = os.getenv('DB_PASSWORD')
encoded_password = quote(raw_password)

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': raw_password,
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT')),
}

# SQLAlchemy URL (sync engine with pymysql)
DATABASE_URL = (
    f"mysql+pymysql://{db_config['user']}:{encoded_password}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
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
