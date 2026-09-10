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

class AssessmentTypeItem(BaseModel):
    type: str
    title: str
    category: str
    description: str
    supported_media: List[str] = Field(default_factory=lambda: ["AUDIO", "VIDEO"])
    is_active: bool = True
    questions_count: int = 1
    icon: Optional[str] = None
    difficulty_levels: List[str] = Field(default_factory=lambda: ["EASY", "MEDIUM", "HARD"])


class AssessmentTypeListResponse(BaseModel):
    items: List[AssessmentTypeItem] = Field(default_factory=list)
    total: int


class LLMKeyStatusResponse(BaseModel):
    candidate_id: int
    has_active_key: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    supports_voice: bool = False
    status: str  # "VALID", "INACTIVE", "MISSING", "FAILURE"
    message: str


class ResumeStatusResponse(BaseModel):
    candidate_id: int
    has_resume: bool
    status: str  # "VALID", "MISSING"
    message: str
    last_updated: Optional[str] = None


class AssessmentErrorDetail(BaseModel):
    error_code: str
    detail: str
    missing_requirements: Optional[List[str]] = None


class CreateAssessmentRequest(BaseModel):
    candidate_id: Optional[int] = None
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
    questions: Optional[List[Dict[str, Any]]] = None


class SubmitAssessmentRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: Dict[str, Any] = Field(default_factory=dict)
    audio_telemetry: Dict[str, Any] = Field(default_factory=dict)
    video_telemetry: Dict[str, Any] = Field(default_factory=dict)


class SubmitAssessmentResponse(BaseModel):
    assessment_id: int
    status: str
    message: str
    report: Optional[Dict[str, Any]] = None


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
    category: Optional[AssessmentCategoryEnum] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevelEnum] = None
    question_text: Optional[str] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_subcategory_update(self):
        if self.category is not None:
            if self.category == AssessmentCategoryEnum.TECHNICAL and not self.sub_category:
                raise ValueError("sub_category is required when category is updated to TECHNICAL")
            if self.category != AssessmentCategoryEnum.TECHNICAL and self.sub_category is not None:
                self.sub_category = None
        return self


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


# ─── Media Ingestion & Chunking Schemas (BE2) ─────────────────────────────────

class MediaTaskStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TaskStatusEnum = MediaTaskStatusEnum
AnalysisRunStatusEnum = MediaTaskStatusEnum
AssessmentTypeEnum = AssessmentCategoryEnum
AssessmentMediaTypeEnum = MediaTypeEnum
AssessmentResponse = CreateAssessmentResponse


class ChunkUploadResponse(BaseModel):
    chunk_number: int
    status: str = "uploaded"
    storage_path: str
    total_chunks: Optional[int] = None


class ChunkStatusResponse(BaseModel):
    assessment_id: int
    total_chunks_expected: Optional[int] = None
    uploaded_chunks_count: int
    uploaded_chunk_numbers: List[int]
    missing_chunk_numbers: List[int]
    is_complete: bool


class AssembleMediaRequest(BaseModel):
    total_chunks: int = Field(..., ge=1, description="Total number of chunks to assemble")


class AssembleMediaResponse(BaseModel):
    assessment_id: int
    status: str
    assembled_video_path: str
    extracted_audio_path: str
    file_size_bytes: int
    dispatched_tasks: List[str] = Field(default_factory=list)


class ProcessingStatusResponse(BaseModel):
    assessment_id: int
    status: str
    progress_percentage: int
    active_step: Optional[str] = None
    tasks: Dict[str, str] = Field(default_factory=dict)
    youtube_url: Optional[str] = None
    error_message: Optional[str] = None


class MediaFileResponse(BaseModel):
    id: int
    assessment_id: int
    audio_file_path: Optional[str] = None
    video_file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None


class MediaTaskRunResponse(BaseModel):
    id: int
    assessment_id: int
    task_type: str
    status: str
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


