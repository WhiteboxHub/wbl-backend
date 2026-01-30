from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, func, Text, Enum
from fapi.db.models import Base
import enum

class PrimaryRoleEnum(str, enum.Enum):
    ML_ENGINEER = 'Machine Learning Engineer'
    AI_ENGINEER = 'AI Engineer'
    DATA_SCIENTIST = 'Data Scientist'
    RESEARCH_SCIENTIST = 'Research Scientist'
    MLOPS_ENGINEER = 'MLOps Engineer'
    NLP_ENGINEER = 'NLP Engineer'
    CV_ENGINEER = 'Computer Vision Engineer'
    AI_PRODUCT_MANAGER = 'AI Product Manager'
    OTHER = 'Other'

class EmploymentTypeEnum(str, enum.Enum):
    FULL_TIME = 'Full-Time'
    PART_TIME = 'Part-Time'
    CONTRACT = 'Contract'
    FREELANCE = 'Freelance'
    INTERNSHIP = 'Internship'

class AvailabilityTimelineEnum(str, enum.Enum):
    IMMEDIATE = 'Immediate'
    WITHIN_1_MONTH = 'Within 1 Month'
    FROM_1_TO_3_MONTHS = '1–3 Months'
    OVER_3_MONTHS = '3+ Months'

class AITalentOutreachORM(Base):
    __tablename__ = "ai_talent_outreach"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(45), nullable=False)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    
    linkedin_url = Column(String(255), nullable=False)
    github_url = Column(String(255), nullable=True)
    portfolio_url = Column(String(255), nullable=True)
    resume_file = Column(String(255), nullable=True)
    
    primary_role = Column(
        Enum(PrimaryRoleEnum, values_callable=lambda x: [e.value for e in x]), 
        nullable=True
    )
    years_experience = Column(Integer, nullable=True) # TINYINT in SQL, Integer is fine
    
    employment_type = Column(
        Enum(EmploymentTypeEnum, values_callable=lambda x: [e.value for e in x]), 
        nullable=True
    )
    
    availability_timeline = Column(
        Enum(AvailabilityTimelineEnum, values_callable=lambda x: [e.value for e in x]), 
        nullable=True
    )
    
    core_ai_skills = Column(Text, nullable=True)
    ai_domains = Column(Text, nullable=True)
    
    preferred_location = Column(String(255), nullable=True)
    compensation_range = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    entry_date = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    last_modified = Column(
        TIMESTAMP, 
        nullable=False, 
        server_default=func.current_timestamp(), 
        onupdate=func.current_timestamp()
    )
