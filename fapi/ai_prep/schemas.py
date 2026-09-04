"""
Data contracts and schemas for the AI Prep Assessment Platform.
Single source of truth for API endpoints (router.py), Core Engines, and Orchestrators.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


# ─── Domain Enums ─────────────────────────────────────────────────────────────

class AssessmentCategoryEnum(str, Enum):
    INTRO = "INTRO"
    JD_INTRO = "JD_INTRO"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    TECHNICAL = "TECHNICAL"
    GENERAL = "GENERAL"


AssessmentTypeEnum = AssessmentCategoryEnum


class DifficultyLevelEnum(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class MediaTypeEnum(str, Enum):
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    VIDEO_AUDIO = "VIDEO_AUDIO"


AssessmentMediaTypeEnum = MediaTypeEnum


class AssessmentStatusEnum(str, Enum):
    TESTING = "TESTING"
    IN_PROGRESS = "IN_PROGRESS"
    EVALUATING = "EVALUATING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EngineOperationEnum(str, Enum):
    START = "START"
    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"


class AnalysisRunStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ─── API Endpoint Requests & Responses ────────────────────────────────────────

class CreateAssessmentRequest(BaseModel):
    candidate_id: Optional[int] = Field(default=None, description="Candidate ID")
    assessment_type: Optional[Any] = Field(default=AssessmentCategoryEnum.TECHNICAL, description="Category of assessment")
    media_type: Optional[Any] = Field(default=None, description="VIDEO or AUDIO")
    assessment_mode: Optional[Any] = Field(default=None, description="VIDEO or AUDIO")
    candidate_resume_id: Optional[int] = Field(default=None, description="Optional resume id")
    job_description_text: Optional[str] = Field(default=None, description="Target job description")
    job_description: Optional[str] = Field(default=None, description="Job description")


class CreateAssessmentResponse(BaseModel):
    id: int
    status: Optional[Any] = AssessmentStatusEnum.IN_PROGRESS
    started_at: Optional[Any] = None
    candidate_id: Optional[Any] = None
    assessment_type: Optional[Any] = None
    media_type: Optional[Any] = None
    assessment_mode: Optional[Any] = None
    youtube_url: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "allow"


class AssessmentResponse(BaseModel):
    id: int
    candidate_id: Optional[Any] = 42
    assessment_type: Optional[Any] = None
    assessment_mode: Optional[Any] = "VIDEO"
    media_type: Optional[Any] = "VIDEO"
    status: Optional[Any] = "IN_PROGRESS"
    job_description: Optional[Any] = None
    youtube_url: Optional[Any] = None
    ip_address: Optional[Any] = None
    user_agent: Optional[Any] = None
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    created_at: Optional[Any] = None
    questions: Optional[List[Any]] = None

    class Config:
        from_attributes = True
        extra = "allow"


class AssessmentListItem(BaseModel):
    id: int
    candidate_id: Optional[Any] = None
    assessment_type: Optional[Any] = None
    media_type: Optional[Any] = None
    assessment_mode: Optional[Any] = None
    status: Optional[Any] = None
    created_at: Optional[Any] = None

    class Config:
        from_attributes = True
        extra = "allow"


class AssessmentListResponse(BaseModel):
    total: int
    items: List[AssessmentListItem] = Field(default_factory=list)


class UpdateAssessmentStatusRequest(BaseModel):
    status: AssessmentStatusEnum


class UpdateAssessmentMediaRequest(BaseModel):
    youtube_url: str


class UpdateMediaUrlRequest(BaseModel):
    youtube_url: str


class SubmitAssessmentDataRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: Union[Dict[str, Any], str] = Field(default_factory=dict)
    audio_telemetry: Dict[str, Any] = Field(default_factory=dict)
    video_telemetry: Dict[str, Any] = Field(default_factory=dict)


# ─── Media Ingestion & Chunking Schemas (BE2) ─────────────────────────────────

class ChunkUploadResponse(BaseModel):
    chunk_number: int
    status: str = "uploaded"
    storage_path: Optional[str] = None
    total_chunks: Optional[int] = None


class ChunksStatusResponse(BaseModel):
    assessment_id: int
    uploaded_chunks: List[int]
    missing_chunks: List[int]
    total_chunks_expected: Optional[int] = None
    is_ready_for_assembly: bool


class AssembleMediaRequest(BaseModel):
    assessment_id: int
    total_chunks: int = Field(gt=0, description="Total expected number of chunks")


class AssembleMediaResponse(BaseModel):
    assessment_id: int
    status: str
    task_id: Optional[str] = None
    message: str


class ProcessingStatusResponse(BaseModel):
    assessment_id: int
    status: str
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None
    youtube_url: Optional[str] = None


class MediaFileResponse(BaseModel):
    id: int
    assessment_id: int
    audio_file_path: Optional[str] = None
    video_file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None

    class Config:
        from_attributes = True


class AnalysisRunResponse(BaseModel):
    id: int
    assessment_id: int
    run_type: str
    status: str
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Question Bank Schemas ───────────────────────────────────────────────────

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
    category: Optional[Any] = None
    sub_category: Optional[Any] = None
    difficulty_level: Optional[Any] = None
    question_text: Optional[Any] = None
    is_active: Optional[bool] = True
    created_at: Optional[Any] = None

    class Config:
        from_attributes = True
        extra = "allow"


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
    assessment_type: Any
    media_type: Any
    status: Any
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
    category: Any
    eligible_questions: List[Dict[str, Any]] = Field(default_factory=list)
    used_question_ids: List[int] = Field(default_factory=list)
