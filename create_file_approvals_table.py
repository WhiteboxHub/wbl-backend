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
    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(255), index=True, nullable=False)
    username = Column(String(255), index=True, nullable=False)
    email = Column(String(255), index=True, nullable=False)
    drive_file_id = Column(String(255), nullable=True)
    original_filename = Column(String(512), nullable=False)
    approvals_count = Column(Integer, default=0)
    document_type = Column(String(255), nullable=True)
    is_approved = Column(Boolean, default=False)
    is_declined = Column(Boolean, default=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FileApprovalAction(Base):
    __tablename__ = "file_approval_actions"
    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(255), index=True, nullable=False)
    approver_email = Column(String(255), index=True, nullable=False)
    decision = Column(String(20), nullable=False)
    acted_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

print("Resetting tables (Drop & Create)...")
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

print("Tables created successfully!")



