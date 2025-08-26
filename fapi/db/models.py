from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal 
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP,Enum as SQLAEnum, func, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, relationship
import enum



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
    __table_args__ = {"extend_existing": True}

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
    massemail_unsubscribe = Column(Boolean, nullable=True)
    massemail_email_sent = Column(Boolean, nullable=True)
    moved_to_candidate = Column(Boolean,server_default='0')


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



class VendorTypeEnum(str, enum.Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"
    contact_from_ip = "contact-from-ip"

class Vendor(Base):
    __tablename__ = "vendor"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(50))
    secondary_phone = Column(String(50))
    email = Column(String(255), unique=True, index=True)
    type = Column(
        SQLAEnum(
            VendorTypeEnum,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        server_default=VendorTypeEnum.client.value
    )
    note = Column(Text)
    linkedin_id = Column(String(255))
    company_name = Column(String(255))
    location = Column(String(255))
    city = Column(String(50))
    postal_code = Column(String(20))
    address = Column(Text)
    country = Column(String(50))
    # vendor_type = Column(
    #     SQLAEnum(
    #         VendorTypeEnum,
    #         values_callable=lambda x: [e.value for e in x]
    #     ),
    #     nullable=True
    # )
    status = Column(
        SQLAEnum(
            "active",
            "working",
            "not_useful",
            "do_not_contact",
            "inactive",
            "prospect",
            name="vendorstatusenum"
        ),
        default="prospect"
    )
    linkedin_connected = Column(
        SQLAEnum("YES", "NO", name="yesnoenum"),
        default="NO"
    )
    intro_email_sent = Column(
        SQLAEnum("YES", "NO", name="yesnoenum2"),
        default="NO"
    )
    intro_call = Column(
        SQLAEnum("YES", "NO", name="yesnoenum3"),
        default="NO"
    )
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    
# ------------------------------------------



class UnsubscribeUser(Base):
    __tablename__ = "massemail"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    remove = Column(String(1), default='N') 



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
    interviews = relationship(
        "CandidateInterview", 
        back_populates="candidate",
        foreign_keys="[CandidateInterview.candidate_id]"
    )

# --------------------------------------Candidate_Marketing-------------------------------


class CandidateMarketingORM(Base):
    __tablename__ = "candidate_marketing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id =Column(Integer)
    marketing_manager = Column(Integer)
    start_date = Column(Date,nullable=False)
    notes=Column(Text,nullable=True)
    status=Column(Enum('active','break','not responding'), nullable=False)
    last_mod_datetime = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    # candidate_id = Column(Integer)
#--------------------------------Candidate interview--------------------------------


   
# --------------------------------------Candidate_Placement-------------------------------

class CandidatePlacementORM(Base):
    __tablename__ = "candidate_placement"

    id = Column(Integer, primary_key=True, autoincrement=True)

    candidate_id = Column(Integer, ForeignKey("candidateid", ondelete="CASCADE"), nullable=False)
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



# -------------------- Enums --------------------


    
class VendorContactExtractsORM(Base):
    __tablename__ = "vendor_contact_extracts"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, unique=False)
    phone = Column(String(50), nullable=True)
    linkedin_id = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    moved_to_vendor = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

# 
# -------------------- ORM: vendor-daily-activity --------------------
class YesNoEnum(str, enum.Enum):
    YES = "YES"
    NO = "NO"

class DailyVendorActivityORM(Base):
    __tablename__ = "vendor_daily_activity"

    activity_id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendor.id"), nullable=False)
    application_date = Column(Date, nullable=True)
    linkedin_connected = Column(SQLAEnum(YesNoEnum), nullable=True)
    contacted_on_linkedin = Column(SQLAEnum(YesNoEnum), nullable=True)
    notes = Column(String(1000), nullable=True)
    employee_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CourseContent(Base):
    __tablename__ = "course_content"

    id = Column(Integer, primary_key=True, index=True)
    Fundamentals = Column(String(255), nullable=True)
    AIML = Column(String(255), nullable=False)
    UI = Column(String(255), nullable=True)
    QE = Column(String(255), nullable=True)



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
    


# ----------------------Resources--------------------


class Course(Base):
    __tablename__ = "course"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255))
    alias = Column(String(100), unique=True)
    description = Column(Text, nullable=True)  
    syllabus = Column(Text, nullable=True)     
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now) 
    subjects = relationship("CourseSubject", back_populates="course")
    batches = relationship("Batch", back_populates="course")

class Subject(Base):
    __tablename__ = "subject"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255))
    description = Column(String(300), nullable=False)  
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now)  
    course_subjects = relationship("CourseSubject", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject")
    sessions = relationship("Session", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject_rel")  




class CourseSubject(Base):
    __tablename__ = "course_subject"
    subject_id = Column(Integer, ForeignKey("subject.id"), primary_key=True)
    course_id = Column(Integer, ForeignKey("course.id"), primary_key=True)
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    course = relationship("Course", back_populates="subjects")
    subject = relationship("Subject", back_populates="course_subjects")

    # --------------------------------------------------------

# class Batch(Base):
#     __tablename__ = "batch"
#     batchid = Column(Integer, primary_key=True, index=True)
#     batchname = Column(String(255))
#     courseid = Column(Integer, ForeignKey("course.id"))
#     course = relationship("Course", back_populates="batches")
#     recording_batches = relationship("RecordingBatch", back_populates="batch")

class Batch(Base):
    __tablename__ = "batch"


    batchid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batchname = Column(String(100), nullable=False)
    orientationdate = Column(Date, nullable=True)
    subject = Column(String(45), nullable=False, default="ML")
    startdate = Column(Date, nullable=True)
    enddate = Column(Date, nullable=True)
    lastmoddatetime = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    courseid = Column(Integer, ForeignKey("course.id"), nullable=True)

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



# ========================Employee===========================

class EmployeeORM(Base):
    __tablename__ = "employee"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    address = Column(String(255))
    state = Column(String(150))
    dob = Column(Date)
    startdate = Column(Date)
    instructor = Column(Integer)
    enddate = Column(DateTime)
    notes = Column(Text)
    status = Column(Integer)
    aadhaar = Column(String(50))  # changed to String, Aadhaar isn’t really an int



class CandidateInterview(Base):
    __tablename__ = "candidate_interview"
    
# class CandidateInterview(Base):
#     __tablename__ = "candidate_interview"
    
    # id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"))
    # company = Column(String(200))
    # interview_date = Column(DateTime, nullable=False)
    # feedback = Column(String(50))  # Positive, Negative, No Response
    # notes = Column(Text)
    
    candidate = relationship("CandidateORM", back_populates="interviews")

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # candidate_id = Column(Integer, nullable=False)   
    candidate_name = Column(String(200), nullable=True)
    company = Column(String(200), nullable=False)
    interviewer_emails = Column(Text, nullable=True)
    interviewer_contact = Column(Text, nullable=True)  
    interview_date = Column(Date, nullable=False)

    interview_type = Column(
        Enum("Phone", "Virtual", "In Person", "Assessment", name="interview_type_enum"),
        nullable=True
    )

    recording_link = Column(String(500), nullable=True)
    status = Column(String(100), nullable=True)   

    feedback = Column(
        Enum("Negative", "Positive", "No Response", "Cancelled", name="feedback_enum"),
        nullable=True
    )

    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )


class CandidateStatus(str, enum.Enum):
    active = "active"
    break_ = "break"
    not_responding = "not responding"
    inactive = "inactive"


class CandidatePreparation(Base):
    __tablename__ = "candidate_preparation"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, nullable=False)
    batch = Column(String(100), nullable=True)
    start_date = Column(Date, nullable=True)
    status = Column(Enum('active','break','not responding','inactive'), nullable=False)
    instructor1_id = Column(Integer, nullable=True)
    instructor2_id = Column(Integer, nullable=True)
    instructor3_id = Column(Integer, nullable=True)
    rating = Column(String(50), nullable=True)
    tech_rating = Column(String(50), nullable=True)
    communication = Column(String(50), nullable=True)
    years_of_experience = Column(String(50), nullable=True)
    topics_finished = Column(Text, nullable=True)
    current_topics = Column(Text, nullable=True)
    target_date_of_marketing = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, nullable=True)