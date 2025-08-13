# wbl-backend/fapi/db.py
from fapi.utils.auth_utils import md5_hash,verify_md5_hash,hash_password,verify_reset_token
import mysql.connector
from fastapi import HTTPException, status
from mysql.connector import Error
import os
from typing import Optional,Dict,List
import asyncio
from dotenv import load_dotenv
from datetime import date,datetime,time, timedelta  
from sqlalchemy import create_engine 
from sqlalchemy.orm import sessionmaker , declarative_base
from sqlalchemy.ext.declarative import declarative_base
from fapi.db.models import AuthUserORM
from sqlalchemy.ext.asyncio import AsyncSession ,create_async_engine
from sqlalchemy.future import select
# from fapi.db.models import CourseContent
from urllib.parse import quote
from sqlalchemy.orm import declarative_base
from fapi.db.base import Base

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

# Async SQLAlchemy URL (uses aiomysql)
DATABASE_URL = (
    f"mysql+pymysql://{db_config['user']}:{encoded_password}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

# Async Engine and Session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_username_sync(uname: str):
    with SessionLocal() as session:
        return session.query(AuthUserORM).filter(AuthUserORM.uname == uname).first()



        
async def update_user_password(uname: str, new_password: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        
        # Hash the new password
        hashed_password = md5_hash(new_password)
        # Update the user's password
        query = "UPDATE whitebox_learning.authuser SET passwd = %s WHERE uname = %s;"
        values = (hashed_password, uname)
        
        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    except Error as e:
        # print(f"Error updating password: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error updating password")
    finally:
        cursor.close()
        conn.close()      
        
  
async def update_user_password(email: str, new_password: str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE authuser SET passwd = %s WHERE uname = %s", (hashed_password, email))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
