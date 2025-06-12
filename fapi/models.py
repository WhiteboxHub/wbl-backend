# # from pydantic import BaseModel, Field
# from pydantic import BaseModel, EmailStr
# from typing import Optional
#  # Combine first and last names to form fullname
# fullname = f"{user.firstname.strip()} {user.lastname.strip()}"

# class UserCreate(BaseModel):
#     uname: str
#     passwd: str

# class UserRegistration(BaseModel):
#     uname: str
#     passwd: str
#     dailypwd: Optional[str] = None
#     team: Optional[str] = None
#     level: Optional[str] = None
#     instructor: Optional[str] = None
#     override: Optional[str] = None
#     status: Optional[str] = None
#     lastlogin: Optional[str] = None
#     logincount: Optional[str] = None
#     fullname: Optional[str] = None
#     # firstname: Optional[str] = None
#     # lastname: Optional[str] = None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     city: Optional[str] = None
#     Zip: Optional[str] = None
#     country: Optional[str] = None
#     message: Optional[str] = None
#     registereddate: Optional[str] = None
#     level3date: Optional[str] = None
#     last: Optional[str] = None
#     visastatus: Optional[str] = None              # already in use; keep as is
#     experience: Optional[str] = None              # new field
#     education: Optional[str] = None               # new field
#     specialization: Optional[str] = None
#     referred_by: Optional[str] = None

# # class UserRegistration(BaseModel):
# #     uname: str
# #     passwd: str
# #     dailypwd: Optional[str] = None
# #     team: Optional[str] = None
# #     level: Optional[str] = None
# #     instructor: Optional[str] = None
# #     override: Optional[str] = None
# #     status: Optional[str] = None
# #     lastlogin: Optional[str] = None
# #     logincount: Optional[str] = None
# #     fullname: Optional[str] = None
# #     phone: Optional[str] = None
# #     address: Optional[str] = None
# #     city: Optional[str] = None
# #     Zip: Optional[str] = None
# #     country: Optional[str] = None
# #     message: Optional[str] = None
# #     registereddate: Optional[str] = None
# #     level3date: Optional[str] = None
# #     last: Optional[str] = None
# #     visastatus: Optional[str] = Field(None, alias="visaStatus")   # fix alias
# #     experience: Optional[str] = None
# #     education: Optional[str] = None
# #     specialization: Optional[str] = None
# #     referred_by: Optional[str] = Field(None, alias="referredBy")  # fix alias

#     class Config:
#         allow_population_by_field_name = True

# class ContactForm(BaseModel):
#     firstName: str
#     lastName: str
#     email: str
#     phone: str
#     message: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class EmailRequest(BaseModel):
#     email: EmailStr

# class ResetPasswordRequest(BaseModel):
#     email: EmailStr

# class ResetPassword(BaseModel):
#     token: str
#     new_password: str


# # class UserCreate(BaseModel):
# #     email: str
# #     name: str   
# #     google_id: str


# # Model for Google user creation
# class GoogleUserCreate(BaseModel):
#     name: str
#     email: str
#     google_id: str

from pydantic import BaseModel, EmailStr, Field
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
