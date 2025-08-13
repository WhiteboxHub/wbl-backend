from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal 
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class UserCreate(BaseModel):
    uname: str
    passwd: str

# -----------------------------------------------------

class AuthUserORM(Base):
    __tablename__ = "authuser"

    id = Column(Integer, primary_key=True, index=True)
    uname = Column(String(50), unique=True, nullable=False, default="")
    passwd = Column(String(32), nullable=False)
    team = Column(String(255))
    status = Column(String(255), default="inactive")
    lastlogin = Column(DateTime)
    logincount = Column(Integer)
    fullname = Column(String(50))
    address = Column(String(50))
    phone = Column(String(20))
    state = Column(String(45))
    zip = Column(String(45))
    city = Column(String(45))
    country = Column(String(45))
    message = Column(Text)
    registereddate = Column(DateTime)
    level3date = Column(DateTime)
    lastmoddatetime = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    demo = Column(String(1), default="N")
    enddate = Column(Date, default="1990-01-01")
    googleId = Column(String(255))
    reset_token = Column(String(255))
    token_expiry = Column(DateTime)
    role = Column(String(100))
    visa_status = Column(String(50))
    experience = Column(String(100))
    education = Column(String(255))
    referby = Column(String(100))
    specialization = Column(String(255))
    notes = Column(Text)


# ----------------------------------------------
class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str



    
# ------------------------------------------- Leads----------------------------------------
class LeadORM(Base):
    __tablename__ = "lead"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    entry_date = Column(DateTime)
    phone = Column(String(20))
    email = Column(String(255), nullable=False)
    workstatus = Column(String(50))
    status = Column(String(50))
    secondary_email = Column(String(255))
    secondary_phone = Column(String(20))
    address = Column(String(255))
    closed_date = Column(Date)
    notes = Column(String(500))
    last_modified = Column(DateTime)
    massemail_unsubscribe = Column(String(5))
    massemail_email_sent = Column(String(5))
    moved_to_candidate = Column(Boolean)

# -------------------------------------------------------------------------------



# .......................................NEW INNOVAPATH..............................


class TalentSearch(Base):
    __tablename__ = "talent_search"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    role = Column(String(50))
    experience = Column(Integer)
    location = Column(String(100))
    availability = Column(String(50))
    skills = Column(Text)


class Vendor(Base):
    __tablename__ = "vendor"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(50))
    email = Column(String(255), unique=True)
    city = Column(String(50))
    postal_code = Column(String(20))
    address = Column(Text)
    country = Column(String(50))
    type = Column(Enum(
        'client',
        'third-party-vendor',
        'implementation-partner',
        'sourcer',
        'IP_REQUEST_DEMO'
    ))
    created_at = Column(TIMESTAMP, server_default=func.now())

    
# ------------------------------------------



class UnsubscribeUser(Base):
    __tablename__ = "massemail"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    remove = Column(String(1), default='N') 




# ----------------------------------------Candidate------------------------------------
class CandidateORM(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=True)
    enrolled_date = Column(Date, nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    status = Column(String(20), nullable=True)  # No ENUM used
    workstatus = Column(String(50), nullable=True)  # No ENUM used
    education = Column(String(200), nullable=True)
    workexperience = Column(String(200), nullable=True)
    ssn = Column(String(11), nullable=True)
    agreement = Column(String(1), default="N", nullable=True)
    secondaryemail = Column(String(100), nullable=True)
    secondaryphone = Column(String(45), nullable=True)
    address = Column(String(300), nullable=True)
    linkedin_id = Column(String(100), nullable=True)
    dob = Column(Date, nullable=True)
    emergcontactname = Column(String(100), nullable=True)
    emergcontactemail = Column(String(100), nullable=True)
    emergcontactphone = Column(String(100), nullable=True)
    emergcontactaddrs = Column(String(300), nullable=True)
    fee_paid = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    batchid = Column(Integer, nullable=False)



# --------------------------------------Candidate_Marketing-------------------------------


class CandidateMarketingORM(Base):
    __tablename__ = "candidate_marketing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # candidate_id = Column(Integer, ForeignKey("candidate.candidateid", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer)
    # primary_instructor_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    primary_instructor_id = Column(Integer)
    # sec_instructor_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    sec_instructor_id = Column(Integer)
    # marketing_manager = Column(Integer, ForeignKey("employee.id"), nullable=True)
    marketing_manager = Column(Integer)
    start_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(Enum('active', 'break', 'not responding'), nullable=False)
    last_mod_datetime = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


# --------------------------------------Candidate_Placement-------------------------------

class CandidatePlacementORM(Base):
    __tablename__ = "candidate_placement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # candidate_id = Column(Integer, ForeignKey("candidate.candidateid", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer)
    position = Column(String(255), nullable=True)
    company = Column(String(200), nullable=False)
    placement_date = Column(Date, nullable=False)
    type = Column(Enum('Company', 'Client', 'Vendor', 'Implementation Partner'), nullable=True)
    status = Column(Enum('scheduled', 'cancelled'), nullable=False)
    base_salary_offered = Column(DECIMAL(10, 2), nullable=True)
    benefits = Column(Text, nullable=True)
    fee_paid = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, default=None, onupdate=None)
