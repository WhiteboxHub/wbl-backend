from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import time, date, datetime
# from .db import Base, engine, get_db

class UserCreate(BaseModel):
    uname: str
    passwd: str


class UserRegistration(BaseModel):
    uname: str
    passwd: str
    dailypwd: Optional[str] = None
    team: Optional[str] = None
    level: Optional[str] = None
    instructor: Optional[str] = None
    override: Optional[str] = None
    status: Optional[str] = None
    lastlogin: Optional[str] = None
    logincount: Optional[str] = None
    # firstname: Optional[str] = None
    # lastname: Optional[str] = None
    firstname: Optional[str] = Field(None, alias="firstName")
    lastname: Optional[str] = Field(None, alias="lastName")
    fullname: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    Zip: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    registereddate: Optional[str] = None
    level3date: Optional[str] = None
    last: Optional[str] = None
    visastatus: Optional[str] = Field(None, alias="visaStatus")  # with alias
    experience: Optional[str] = None
    education: Optional[str] = None
    specialization: Optional[str] = None
    referred_by: Optional[str] = Field(None, alias="referredBy")  # with alias

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True


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


class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str


# ---------------------------- Request demo --------------------

class VendorCreate(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    note: Optional[str] = None


class RecentPlacement(BaseModel):
    id: int
    candidate_name: str
    company: str
    position: str
    placement_date: str


class RecentInterview(BaseModel):
    id: int
    candidate_name: str
    candidate_role: Optional[str]
    interview_time: time
    interview_date: date
    interview_mode: Optional[str]
    client_name: Optional[str]
    interview_location: Optional[str]
    created_at: datetime

# .......................................NEW INNOVAPATH..............................


class CandidateMarketingBaseModel(BaseModel):
    candidate_id: int
    full_name: str
    email: str
    phone: str
    role: str
    experience: int
    location: str
    availability: str
    skills: str

# class CandidateMarketingCreate(CandidateMarketingBase):
    # pass

class CandidateMarketing(CandidateMarketingBaseModel):
    id: int
    
    class Config:
        orm_mode = True