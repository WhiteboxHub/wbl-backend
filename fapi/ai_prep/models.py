"""SQLAlchemy ORM Models for AI Prep Tool (Assessment Sessions, Telemetry Data, Reports, Questions)."""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from fapi.db.models import Base


class AiPrepAssessmentORM(Base):
    """Core assessment session table."""

    __tablename__ = "ai_prep_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_uuid = Column(String(64), unique=True, nullable=False, index=True)
    candidate_id = Column(Integer, nullable=False, index=True)
    assessment_type = Column(String(50), nullable=False, default="INTRO")
    media_type = Column(String(20), nullable=False, default="VIDEO")
    status = Column(String(50), nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, EVALUATING, COMPLETED, FAILED
    job_description = Column(Text, nullable=True)
    youtube_url = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    data_record = relationship("AiPrepAssessmentDataORM", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    report_record = relationship("AiPrepAssessmentReportORM", back_populates="assessment", uselist=False, cascade="all, delete-orphan")


class AiPrepAssessmentDataORM(Base):
    """Telemetry, raw transcript, and questions submitted for an assessment."""

    __tablename__ = "ai_prep_assessment_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id"), unique=True, nullable=False, index=True)
    questions = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    audio_telemetry = Column(JSON, nullable=True)
    video_telemetry = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    assessment = relationship("AiPrepAssessmentORM", back_populates="data_record")


class AiPrepAssessmentReportORM(Base):
    """Validated evaluation scores and qualitative coaching report from LLM / Scores Engine."""

    __tablename__ = "ai_prep_assessment_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id"), unique=True, nullable=False, index=True)
    audio_evaluation = Column(JSON, nullable=True)
    video_evaluation = Column(JSON, nullable=True)
    transcript_evaluation = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    report_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    assessment = relationship("AiPrepAssessmentORM", back_populates="report_record")


class AiPrepQuestionORM(Base):
    """Question bank repository for AI Prep assessments."""

    __tablename__ = "ai_prep_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False, index=True)  # INTRO, JD_INTRO, RECRUITER, HIRING_MANAGER, SYSTEM_DESIGN, TECHNICAL
    sub_category = Column(String(100), nullable=True)
    difficulty_level = Column(String(20), nullable=False, default="MEDIUM")  # EASY, MEDIUM, HARD, EXPERT
    question_text = Column(Text, nullable=False)
    ideal_answer_rubric = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
