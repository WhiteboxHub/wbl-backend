"""SQLAlchemy ORM Models for AI Prep Tool (Assessment Sessions, Telemetry Data, Reports, Questions).
Aligned strictly with Migration V134 DDL.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Enum,
)
from sqlalchemy.orm import relationship

from fapi.db.models import Base


class AiPrepAssessmentORM(Base):
    """Core assessment session table (ai_prep_assessment)."""

    __tablename__ = "ai_prep_assessment"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    candidate_id = Column(BigInteger, nullable=False, index=True)
    assessment_type = Column(
        Enum(
            "INTRO",
            "JD_INTRO",
            "RECRUITER",
            "HIRING_MANAGER",
            "SYSTEM_DESIGN",
            "TECHNICAL",
            name="assessment_category_enum",
        ),
        nullable=False,
        default="INTRO",
        index=True,
    )
    media_type = Column(
        Enum("AUDIO", "VIDEO", name="assessment_media_type_enum"),
        nullable=False,
        default="VIDEO",
    )
    status = Column(
        Enum(
            "IN_PROGRESS",
            "EVALUATING",
            "COMPLETED",
            "FAILED",
            name="assessment_status_enum",
        ),
        nullable=False,
        default="IN_PROGRESS",
        index=True,
    )
    job_description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    youtube_url = Column(Text, nullable=True)

    data_record = relationship(
        "AiPrepAssessmentDataORM",
        back_populates="assessment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    report_record = relationship(
        "AiPrepAssessmentReportORM",
        back_populates="assessment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        self._assessment_uuid = kwargs.pop("assessment_uuid", None)
        super().__init__(**kwargs)

    @property
    def assessment_uuid(self) -> Optional[str]:
        return getattr(self, "_assessment_uuid", None) or (str(self.id) if self.id is not None else None)

    @assessment_uuid.setter
    def assessment_uuid(self, val: Optional[str]):
        self._assessment_uuid = val


class AiPrepAssessmentDataORM(Base):
    """Telemetry, raw transcript, and questions submitted for an assessment."""

    __tablename__ = "ai_prep_assessment_data"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    assessment_id = Column(
        BigInteger,
        ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    questions = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    audio_telemetry = Column(JSON, nullable=True)
    video_telemetry = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    assessment = relationship("AiPrepAssessmentORM", back_populates="data_record")


class AiPrepAssessmentReportORM(Base):
    """Validated evaluation scores and qualitative coaching report from LLM / Scores Engine."""

    __tablename__ = "ai_prep_assessment_report"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    assessment_id = Column(
        BigInteger,
        ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    audio_evaluation = Column(JSON, nullable=True)
    video_evaluation = Column(JSON, nullable=True)
    transcript_evaluation = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    assessment = relationship("AiPrepAssessmentORM", back_populates="report_record")

    def __init__(self, **kwargs):
        self._overall_score = kwargs.pop("overall_score", None)
        self._report_data = kwargs.pop("report_data", None)
        super().__init__(**kwargs)

    @property
    def overall_score(self) -> Optional[float]:
        return getattr(self, "_overall_score", None)

    @overall_score.setter
    def overall_score(self, val: Optional[float]):
        self._overall_score = val

    @property
    def report_data(self) -> Optional[dict]:
        return getattr(self, "_report_data", None)

    @report_data.setter
    def report_data(self, val: Optional[dict]):
        self._report_data = val


class AiPrepQuestionORM(Base):
    """Question bank repository for AI Prep assessments (ai_prep_question_bank)."""

    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(
        Enum(
            "INTRO",
            "JD_INTRO",
            "RECRUITER",
            "HIRING_MANAGER",
            "SYSTEM_DESIGN",
            "TECHNICAL",
            name="qb_category_enum",
        ),
        nullable=False,
        index=True,
    )
    sub_category = Column(String(100), nullable=True)
    difficulty_level = Column(
        Enum("EASY", "MEDIUM", "HARD", "EXPERT", name="qb_difficulty_enum"),
        nullable=False,
        default="MEDIUM",
    )
    question_text = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __init__(self, **kwargs):
        self._ideal_answer_rubric = kwargs.pop("ideal_answer_rubric", None)
        super().__init__(**kwargs)

    @property
    def ideal_answer_rubric(self) -> Optional[str]:
        return getattr(self, "_ideal_answer_rubric", None)

    @ideal_answer_rubric.setter
    def ideal_answer_rubric(self, val: Optional[str]):
        self._ideal_answer_rubric = val


# Compatibility aliases
AiPrepQuestionBankORM = AiPrepQuestionORM
AiPrepAssessment = AiPrepAssessmentORM
AiPrepAssessmentData = AiPrepAssessmentDataORM
AiPrepAssessmentReport = AiPrepAssessmentReportORM
AiPrepQuestionBank = AiPrepQuestionORM
