from datetime import datetime
from urllib.parse import quote
import os

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import declarative_base

load_dotenv()

raw_password = os.getenv("DB_PASSWORD")
if raw_password is None:
    raise ValueError("DB_PASSWORD environment variable is not set")
encoded_password = quote(raw_password)

host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")
database = os.getenv("DB_NAME")
port_str = os.getenv("DB_PORT")

if not all([host, user, database, port_str]):
    raise ValueError("DB_HOST/DB_USER/DB_NAME/DB_PORT must be set in .env")

# Explicit None check for type safety
if port_str is None:
    raise ValueError("DB_PORT environment variable is not set")

port_int = int(port_str)

DATABASE_URL = f"mysql+pymysql://{user}:{encoded_password}@{host}:{port_int}/{database}"

engine = create_engine(DATABASE_URL, echo=True, future=True)
Base = declarative_base()


class FileApproval(Base):
    __tablename__ = "file_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False, unique=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    drive_file_id = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    approvals_count = Column(Integer, nullable=False, default=0)
    is_approved = Column(Boolean, nullable=False, default=False)
    is_declined = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def main():
    print("Creating table file_approvals if not exists...")
    Base.metadata.create_all(engine, tables=[FileApproval.__table__])
    print("Done.")


if __name__ == "__main__":
    main()