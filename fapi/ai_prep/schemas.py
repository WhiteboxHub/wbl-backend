"""
Data contracts and schemas for the AI Prep Assessment Platform.
Single source of truth for API endpoints (router.py), Core Engines, and Orchestrators.
Strictly derived from contracts/all_json_schemas.json specification.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ─── Domain Enums ─────────────────────────────────────────────────────────────

class AssessmentCategoryEnum(str, Enum):
    INTRO = "INTRO"
    JD_INTRO = "JD_INTRO"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    TECHNICAL = "TECHNICAL"


class DifficultyLevelEnum(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class MediaTypeEnum(str, Enum):
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


class AssessmentStatusEnum(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EngineOperationEnum(str, Enum):
    START = "START"
    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"


# ─── API Endpoint Requests & Responses ────────────────────────────────────────

class CreateAssessmentRequest(BaseModel):
    candidate_id: int
    assessment_type: AssessmentCategoryEnum
    media_type: MediaTypeEnum
    job_description: Optional[str] = None


class CreateAssessmentResponse(BaseModel):
    id: int
    status: AssessmentStatusEnum = AssessmentStatusEnum.IN_PROGRESS
    started_at: Optional[datetime] = None
    candidate_id: Optional[int] = None
    assessment_type: Optional[AssessmentCategoryEnum] = None
    media_type: Optional[MediaTypeEnum] = None
    youtube_url: Optional[str] = None


class SubmitAssessmentDataRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: Dict[str, Any] = Field(default_factory=dict)
    audio_telemetry: Dict[str, Any] = Field(default_factory=dict)
    video_telemetry: Dict[str, Any] = Field(default_factory=dict)


class UpdateMediaUrlRequest(BaseModel):
    youtube_url: str


class AssessmentListItem(BaseModel):
    id: int
    assessment_type: str
    media_type: str
    status: str
    created_at: Optional[datetime] = None


class AssessmentListResponse(BaseModel):
    items: List[AssessmentListItem] = Field(default_factory=list)
    total: int


class QuestionBankCreateRequest(BaseModel):
    category: AssessmentCategoryEnum
    sub_category: Optional[str] = None
    difficulty_level: DifficultyLevelEnum = DifficultyLevelEnum.MEDIUM
    question_text: str
    is_active: bool = True


class QuestionBankUpdateRequest(BaseModel):
    sub_category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevelEnum] = None
    question_text: Optional[str] = None
    is_active: Optional[bool] = None


class QuestionBankResponse(BaseModel):
    id: int
    category: str
    sub_category: Optional[str] = None
    difficulty_level: str
    question_text: str
    is_active: bool
    created_at: Optional[datetime] = None


class QuestionListResponse(BaseModel):
    items: List[QuestionBankResponse] = Field(default_factory=list)
    total: int


# ─── Assessment Engine Domain Contracts ────────────────────────────────────────

class AssessmentInfoContract(BaseModel):
    assessment_id: Optional[int] = None
    candidate_id: int
    assessment_type: AssessmentCategoryEnum
    media_type: MediaTypeEnum
    status: AssessmentStatusEnum = AssessmentStatusEnum.IN_PROGRESS
    job_description: Optional[str] = None


class TestingInfoContract(BaseModel):
    completed: bool = False
    passed: bool = False


class SessionInfoContract(BaseModel):
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class QuestionItemContract(BaseModel):
    question_id: int
    question_text: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[str] = None


class TranscriptDataContract(BaseModel):
    full_text: str = ""
    segments: List[Dict[str, Any]] = Field(default_factory=list)


class AssessmentEngineInputContract(BaseModel):
    assessment: AssessmentInfoContract
    operation: EngineOperationEnum = EngineOperationEnum.START
    testing: Optional[TestingInfoContract] = None
    session: Optional[SessionInfoContract] = None
    questions: List[QuestionItemContract] = Field(default_factory=list)
    transcript: Optional[TranscriptDataContract] = None


class AssessmentEngineErrorContract(BaseModel):
    code: str
    message: str


class AssessmentEngineOutputContract(BaseModel):
    success: bool
    status: AssessmentStatusEnum
    qa_context: Optional[str] = None
    error: Optional[AssessmentEngineErrorContract] = None
    errors: List[AssessmentEngineErrorContract] = Field(default_factory=list)


class OrchestratorToAssessmentEngineContract(BaseModel):
    assessment_type: AssessmentCategoryEnum
    questions: List[QuestionItemContract]
    transcript: TranscriptDataContract


class AssessmentEngineQAContextOutputContract(BaseModel):
    qa_context: str


# ─── Core Engine Boundary Models (Sub-engines Spoke 3) ─────────────────────────

class AudioEnginePayload(BaseModel):
    audio_telemetry: Dict[str, Any]


class AudioEngineOutput(BaseModel):
    audio_context: str


class VideoEnginePayload(BaseModel):
    video_telemetry: Dict[str, Any]


class VideoEngineOutput(BaseModel):
    video_context: str


class EvalEnginePayload(BaseModel):
    audio_context: Optional[str] = ""
    video_context: Optional[str] = ""
    qa_context: str


class EvalEnginePromptOutput(BaseModel):
    system_prompt: str
    user_prompt: str
    response_format: str = "json_object"


class ScoresEnginePayload(BaseModel):
    raw_llm_json_string: str


class ParsedReportOutput(BaseModel):
    audio_evaluation: Dict[str, Any] = Field(default_factory=dict)
    video_evaluation: Dict[str, Any] = Field(default_factory=dict)
    transcript_evaluation: Dict[str, Any] = Field(default_factory=dict)


class ScoresEngineOutput(BaseModel):
    is_valid: bool
    parsed_report: Optional[ParsedReportOutput] = None
    error: Optional[str] = None


# ─── Core Engine 1: Assessment Engine Boundary Models ─────────────────────────

class AssessmentStateInput(BaseModel):
    assessment_id: int
    candidate_id: int
    assessment_type: AssessmentCategoryEnum
    media_type: MediaTypeEnum
    status: AssessmentStatusEnum
    job_description: Optional[str] = None


class TestingStateInput(BaseModel):
    completed: bool = False
    passed: bool = False


class SessionStateInput(BaseModel):
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class QuestionStateInput(BaseModel):
    question_id: Optional[int] = None
    question_number: Optional[int] = None


class AssessmentEngineInput(BaseModel):
    assessment: AssessmentStateInput
    operation: EngineOperationEnum
    testing: Optional[TestingStateInput] = None
    session: Optional[SessionStateInput] = None
    question: Optional[QuestionStateInput] = None


class AssessmentEngineError(BaseModel):
    code: str
    message: str


class AssessmentEngineOutput(BaseModel):
    success: bool
    assessment: Optional[Dict[str, Any]] = None
    error: Optional[AssessmentEngineError] = None


class QuestionSelectionInput(BaseModel):
    category: AssessmentCategoryEnum
    eligible_questions: List[Dict[str, Any]] = Field(default_factory=list)
    used_question_ids: List[int] = Field(default_factory=list)


