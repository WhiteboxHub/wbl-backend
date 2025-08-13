from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal 
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base ,relationship
from pydantic import BaseModel 



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
    phone = Column(String(20))
    address = Column(String(50))
    city = Column(String(45))
    zip = Column(String(45))
    country = Column(String(45))
    message = Column(Text)
    registereddate = Column(DateTime)
    level3date = Column(DateTime)
    lastmoddatetime = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    demo = Column(String(1), default="N")
    enddate = Column(Date, default="1990-01-01")
    visa_status = Column(String(50))
    education = Column(String(255))
    experience = Column(String(100))
    specialization = Column(String(255))
    referby = Column(String(100))


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


# ---------------------------- Innovapath - Request demo --------------------

class VendorCreate(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    note: Optional[str] = None
# --------------------------------------------------------------------------

class RecentPlacement(BaseModel):
    id: int
    candidate_name: str
    company: str
    position: str
    placement_date: str


class RecentInterview(BaseModel):
    candidate_name: str
    candidate_role: Optional[str] = None
    interview_time: str
    interview_date: str
    interview_mode: Optional[str] = None
    client_name: Optional[str] = None
    interview_location: Optional[str] = None
    
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

class PlacementBase(BaseModel):
    candidate_id: Optional[int]
    candidate_name: Optional[str]
    candidate_email: Optional[str]
    company: Optional[str]
    client_id: Optional[int]
    batch: Optional[str]
    # placed_date: Optional[date]
    placement_date: Optional[date]
    status: Optional[str]
    marketing_email_address: Optional[str]
    vendor_or_client_name: Optional[str]
    vendor_or_client_contact: Optional[str]
    start_date: Optional[date]
    position: Optional[str]
    amount_paid: Optional[float]
    work_authorization: Optional[str]
    experience_in_resume: Optional[str]
    role: Optional[str]
    job_location: Optional[str]
    terms_and_conditions: Optional[str]
    notes: Optional[str]
    candidate_profile_folder: Optional[str]
    placement_verified: Optional[bool] = False
    joining_letter_url: Optional[str]


class PlacementCreate(PlacementBase):
    pass


class PlacementUpdate(PlacementBase):
    pass


class Placement(PlacementBase):
    id: int

    class Config:
        orm_mode = True



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

    
# ------------------------------------------

class UnsubscribeRequest(BaseModel):
    email: str



class VendorBase(BaseModel):
    id: Optional[int]
    full_name: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    type: Optional[str] = None
    note: Optional[str] = None
    last_contacted: Optional[date] = None
class VendorCreate(VendorBase):
    pass

class VendorUpdate(VendorBase):
    pass

class VendorResponse(VendorBase):
    id: int  # correct usage in Pydantic

    class Config:
        from_attributes = True  


# ----------------------------------------Candidate------------------------------------
class CandidateORM(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=True)
    enrolled_date = Column(Date, nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    status = Column(String(20), nullable=True)  
    workstatus = Column(String(50), nullable=True)  
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
    company = Column(String(200), nullable=False)
    placement_date = Column(Date, nullable=False)
    type = Column(Enum('Company', 'Client', 'Vendor', 'Implementation Partner'), nullable=True)
    status = Column(Enum('scheduled', 'cancelled'), nullable=False)
    base_salary_offered = Column(DECIMAL(10, 2), nullable=True)
    benefits = Column(Text, nullable=True)
    fee_paid = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, default=None, onupdate=None)

# ======================================================Resources===============================
class CourseContent(Base):
    __tablename__ = "course_content"

    id = Column(Integer, primary_key=True, index=True)
    Fundamentals = Column(String(255), nullable=True)
    AIML = Column(String(255), nullable=False)
    UI = Column(String(255), nullable=True)
    QE = Column(String(255), nullable=True)


# class Session(Base):
#     __tablename__ = 'session'
#     sessionid = Column(Integer, primary_key=True)
#     subject_id = Column(Integer, ForeignKey('subject.id'))
#     type = Column(String(100))
#     sessiondate = Column(DateTime)
#     title = Column(String(255))
#     link = Column(String(500))
    


# class CourseSubject(Base):
#     __tablename__ = 'course_subject'
#     id = Column(Integer, primary_key=True)
#     course_id = Column(Integer, ForeignKey("course.id"))
#     subject_id = Column(Integer, ForeignKey("subject.id"))
   


# class Course(Base):
#     __tablename__ = 'course'
#     id = Column(Integer, primary_key=True)
#     alias = Column(String(50))


class CourseMaterial(Base):
    __tablename__ = "course_material"

    id = Column(Integer, primary_key=True, index=True)
    subjectid = Column(Integer, nullable=False, default=0)
    courseid = Column(Integer, nullable=False)
    name = Column(String(250), nullable=False)
    description = Column(String(500))
    type = Column(String(1), nullable=False, default='P')
    link = Column(String(500), nullable=False)
    sortorder = Column(Integer, nullable=False, default=9999)
# ========================


class Course(Base):
    __tablename__ = "course"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    alias = Column(String(100), unique=True)
    subjects = relationship("CourseSubject", back_populates="course")
    batches = relationship("Batch", back_populates="course")

class Subject(Base):
    __tablename__ = "subject"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    course_subjects = relationship("CourseSubject", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject")
    sessions = relationship("Session", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject_rel")  # 


class CourseSubject(Base):
    __tablename__ = "course_subject"
    subject_id = Column(Integer, ForeignKey("subject.id"), primary_key=True)
    course_id = Column(Integer, ForeignKey("course.id"), primary_key=True)
    lastmoddatetime = Column(DateTime)

    course = relationship("Course", back_populates="subjects")
    subject = relationship("Subject", back_populates="course_subjects")

class Batch(Base):
    __tablename__ = "batch"
    batchid = Column(Integer, primary_key=True, index=True)
    batchname = Column(String(255))
    courseid = Column(Integer, ForeignKey("course.id"))

    course = relationship("Course", back_populates="batches")
    recording_batches = relationship("RecordingBatch", back_populates="batch")

class Recording(Base):
    __tablename__ = "recording"
    id = Column(Integer, primary_key=True, index=True)
    batchname = Column(String(255))
    description = Column(Text)
    type = Column(String(50))
    classdate = Column(DateTime)
    link = Column(String(1024))
    videoid = Column(String(255))
    subject = Column(String(255))
    filename = Column(String(255))
    lastmoddatetime = Column(DateTime)
    new_subject_id = Column(Integer, ForeignKey("subject.id"))

    subject_rel = relationship("Subject", back_populates="recordings")  
    recording_batches = relationship("RecordingBatch", back_populates="recording")



class RecordingBatch(Base):
    __tablename__ = "recording_batch"
    recording_id = Column(Integer, ForeignKey("recording.id"), primary_key=True)
    batch_id = Column(Integer, ForeignKey("batch.batchid"), primary_key=True)

    recording = relationship("Recording", back_populates="recording_batches")
    batch = relationship("Batch", back_populates="recording_batches")
class Session(Base):
    __tablename__ = "session"
    sessionid = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(1024))
    videoid = Column(String(255))
    # subject = Column(String(255))
    type = Column(String(50))
    sessiondate = Column(DateTime)
    lastmoddatetime = Column(DateTime)
    subject_id = Column(Integer, ForeignKey("subject.id"))

    subject = relationship("Subject", back_populates="sessions")