"""
SQLAlchemy ORM Models for AI Prep Assessment Platform.
Strictly matches Migration V134 (4 primary tables).
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    Enum as SQLAEnum,
    ForeignKey,
    JSON,
    func,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from fapi.db.models import Base
from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    DifficultyLevelEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
)


class AiPrepQuestionBankORM(Base):
    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    category = Column(
        SQLAEnum(
            AssessmentCategoryEnum,
            values_callable=lambda x: [e.value for e in x],
            name="aiprep_category_enum",
        ),
        nullable=False,
        index=True,
    )
    sub_category = Column(String(100), nullable=True)
    difficulty_level = Column(
        SQLAEnum(
            DifficultyLevelEnum,
            values_callable=lambda x: [e.value for e in x],
            name="aiprep_difficulty_enum",
        ),
        nullable=False,
        default=DifficultyLevelEnum.MEDIUM,
    )
    question_text = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(category = 'TECHNICAL' AND sub_category IS NOT NULL) OR (category <> 'TECHNICAL' AND sub_category IS NULL)",
            name="chk_qb_subcategory",
        ),
    )


class AiPrepAssessmentORM(Base):
    __tablename__ = "ai_prep_assessment"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    candidate_id = Column(BigInteger, nullable=False, index=True)
    assessment_type = Column(
        SQLAEnum(
            AssessmentCategoryEnum,
            values_callable=lambda x: [e.value for e in x],
            name="aiprep_assessment_type_enum",
        ),
        nullable=False,
        index=True,
    )
    media_type = Column(
        SQLAEnum(
            MediaTypeEnum,
            values_callable=lambda x: [e.value for e in x],
            name="aiprep_media_type_enum",
        ),
        nullable=False,
    )
    status = Column(
        SQLAEnum(
            AssessmentStatusEnum,
            values_callable=lambda x: [e.value for e in x],
            name="aiprep_status_enum",
        ),
        nullable=False,
        default=AssessmentStatusEnum.IN_PROGRESS,
        index=True,
    )
    job_description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    youtube_url = Column(Text, nullable=True)

    # Relationships
    assessment_data = relationship(
        "AiPrepAssessmentDataORM",
        back_populates="assessment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    assessment_report = relationship(
        "AiPrepAssessmentReportORM",
        back_populates="assessment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AiPrepAssessmentDataORM(Base):
    __tablename__ = "ai_prep_assessment_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(
        BigInteger,
        ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    questions = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    audio_telemetry = Column(JSON, nullable=True)
    video_telemetry = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assessment = relationship("AiPrepAssessmentORM", back_populates="assessment_data")


class AiPrepAssessmentReportORM(Base):
    __tablename__ = "ai_prep_assessment_report"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(
        BigInteger,
        ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    audio_evaluation = Column(JSON, nullable=True)
    video_evaluation = Column(JSON, nullable=True)
    transcript_evaluation = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assessment = relationship("AiPrepAssessmentORM", back_populates="assessment_report")
