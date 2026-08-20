from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from fapi.ai_prep.models import (
    AssessmentTypeEnum, AssessmentModeEnum, AssessmentStatusEnum,
    CoachingBandEnum, DifficultyLevelEnum, QuestionCategoryEnum,
    ConsentTypeEnum, RunStatusEnum
)


# ----------------------------------------------------------------------
# Assessment Schemas
# ----------------------------------------------------------------------
class CreateAssessmentRequest(BaseModel):
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum = AssessmentModeEnum.VIDEO_AUDIO
    candidate_resume_id: Optional[int] = None
    job_description_text: Optional[str] = None


class UpdateAssessmentStatusRequest(BaseModel):
    status: AssessmentStatusEnum


class QuestionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    question_text: str
    difficulty_level: DifficultyLevelEnum
    category: Optional[QuestionCategoryEnum] = None
    sub_category: Optional[str] = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    candidate_resume_id: Optional[int] = None
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum
    status: AssessmentStatusEnum
    attempt_number: int
    job_description_text: Optional[str] = None
    questions: List[QuestionSummaryOut] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AssessmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum
    status: AssessmentStatusEnum
    attempt_number: int
    coaching_band: Optional[CoachingBandEnum] = None
    created_at: datetime


class AssessmentListResponse(BaseModel):
    items: List[AssessmentListItem]
    total: int


# ----------------------------------------------------------------------
# Media Schemas (BE2)
# ----------------------------------------------------------------------
class ChunkUploadResponse(BaseModel):
    chunk_number: int
    storage_path: str


class ChunksStatusResponse(BaseModel):
    assessment_id: int
    uploaded_chunks: List[int]
    total_uploaded: int
    highest_chunk_number: int
    missing_chunks: List[int]


class AssembleMediaRequest(BaseModel):
    assessment_id: int
    total_chunks: int = Field(..., ge=1, description="Total number of chunks to assemble")


class AssembleMediaResponse(BaseModel):
    assessment_id: int
    status: str = "PROCESSING"
    task_id: Optional[str] = None


class MediaFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    audio_file_path: str
    video_file_path: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_youtube: bool = False
    youtube_video_id: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    created_at: datetime


# ----------------------------------------------------------------------
# Processing Status Schemas
# ----------------------------------------------------------------------
class ProcessingStepsStatus(BaseModel):
    stt: RunStatusEnum = RunStatusEnum.QUEUED
    audio: RunStatusEnum = RunStatusEnum.QUEUED
    vision: RunStatusEnum = RunStatusEnum.QUEUED
    llm: RunStatusEnum = RunStatusEnum.QUEUED
    youtube_upload: RunStatusEnum = RunStatusEnum.QUEUED
    finalize: RunStatusEnum = RunStatusEnum.QUEUED


class ProcessingStatusResponse(BaseModel):
    status: AssessmentStatusEnum
    steps: ProcessingStepsStatus


# ----------------------------------------------------------------------
# Hardware Check Schemas
# ----------------------------------------------------------------------
class HardwareCheckRequest(BaseModel):
    assessment_id: int
    browser_info: Optional[str] = None
    os_info: Optional[str] = None
    camera_permission: bool = False
    mic_permission: bool = False
    speaker_ok: bool = False
    bandwidth_kbps: int = 0
    yolo_model_enabled: bool = False


class HardwareCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    camera_permission: bool
    mic_permission: bool
    speaker_ok: bool
    bandwidth_kbps: int
    yolo_model_enabled: bool
    tested_at: datetime


# ----------------------------------------------------------------------
# Consent Schemas
# ----------------------------------------------------------------------
class ConsentRequest(BaseModel):
    candidate_id: int
    consent_type: ConsentTypeEnum
    consented: bool


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    consent_type: ConsentTypeEnum
    consented: bool
    consented_at: datetime
    revoked_at: Optional[datetime] = None


# ----------------------------------------------------------------------
# Report Schemas (Contract 3)
# ----------------------------------------------------------------------
class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    overall_score: int
    coaching_band: CoachingBandEnum
    formula_explanation: str
    scores_breakdown_json: Dict[str, Any]
    technical_analysis_json: Dict[str, Any]
    non_technical_analysis_json: Dict[str, Any]
    coaching_suggestions_json: Optional[List[Dict[str, Any]]] = None
    signal_timeline_json: Optional[List[Dict[str, Any]]] = None
    transcript_evidence_json: Optional[List[Dict[str, Any]]] = None
    gaps_to_validate_json: Optional[List[Dict[str, Any]]] = None
    improvements_json: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
