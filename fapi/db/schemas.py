from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime


Base = declarative_base()

class LeadORM(Base):
    __tablename__ = "leads_new"

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
# --------------------------------------------------------candidate-------------------------------------------------------


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
