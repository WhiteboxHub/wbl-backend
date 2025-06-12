from pydantic import BaseModel, EmailStr
from typing import Optional

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
    visastatus: Optional[str] = None              # already in use; keep as is
    experience: Optional[str] = None              # new field
    education: Optional[str] = None               # new field
    specialization: Optional[str] = None
    referred_by: Optional[str] = None

class ContactForm(BaseModel):
    name: str
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


# class UserCreate(BaseModel):
#     email: str
#     name: str   
#     google_id: str


# Model for Google user creation
class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str

# ---------------------------- Request demo --------------------

# class VendorCreate(BaseModel):
#     full_name: str
#     phone_number: str
#     email: Optional[EmailStr] = None
#     city: Optional[str] = None
#     postal_code: Optional[str] = None
#     address: Optional[str] = None
#     country: Optional[str] = None
#     type: str
#     note: Optional[str] = None

class VendorCreate(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    note: Optional[str] = None