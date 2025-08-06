

import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from fastapi import HTTPException
from fapi.db.models import AuthUser, LeadORM
from sqlalchemy.inspection import inspect


load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError("Missing one or more DB env variables")

DATABASE_URL = (
    f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session




async def get_user_by_username(db: AsyncSession, username: str):
    try:
        result = await db.execute(select(AuthUser).where(AuthUser.uname == username))
        return result.scalars().first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


async def insert_user(db: AsyncSession, data: dict):
    try:
        valid_columns = {c_attr.key for c_attr in inspect(AuthUser).mapper.column_attrs}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}

        user = AuthUser(**filtered_data)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"User insert error: {str(e)}")

async def insert_lead(db: AsyncSession, data: dict):
    try:
        lead = LeadORM(**data)
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return lead
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lead insert error: {str(e)}")


