from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from fapi.ai_prep.models import (
    AssessmentTypeEnum, AssessmentModeEnum, AssessmentStatusEnum,
    CoachingBandEnum, DifficultyLevelEnum, QuestionDifficultyEnum,
    QuestionCategoryEnum, BackgroundNoiseLevelEnum, ConsentTypeEnum,
    RunTypeEnum, RunStatusEnum, AnalysisRunTypeEnum, AnalysisRunStatusEnum,
    DeletionRequestStatusEnum
)


# ----------------------------------------------------------------------
# Assessment Schemas
# ----------------------------------------------------------------------
class CreateAssessmentRequest(BaseModel):
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum = AssessmentModeEnum.VIDEO_AUDIO
    candidate_resume_id: Optional[int] = None
    job_description_text: Optional[str] = None


AssessmentCreate = CreateAssessmentRequest


class UpdateAssessmentStatusRequest(BaseModel):
    status: AssessmentStatusEnum
    is_paused: bool = False


AssessmentStatusUpdate = UpdateAssessmentStatusRequest


class QuestionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int = 1
    question_text: str
    difficulty_level: DifficultyLevelEnum = DifficultyLevelEnum.MEDIUM
    category: Optional[QuestionCategoryEnum] = None
    sub_category: Optional[str] = None


AssessmentQuestionSchema = QuestionSummaryOut


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
    coaching_band: Optional[CoachingBandEnum] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


AssessmentResponse = AssessmentOut


class AssessmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum
    status: AssessmentStatusEnum
    attempt_number: int
    coaching_band: Optional[CoachingBandEnum] = None
    created_at: datetime
    is_paused: bool = False


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


class MediaFileCreate(BaseModel):
    assessment_id: int
    audio_file_path: str
    video_file_path: Optional[str] = None
    duration_seconds: int = 0
    file_size_bytes: int = 0


MediaFileResponse = MediaFileOut


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


HardwareCheckCreate = HardwareCheckRequest


class HardwareCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    browser_info: Optional[str] = None
    os_info: Optional[str] = None
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
    candidate_id: Optional[int] = None
    consent_type: ConsentTypeEnum
    consented: bool = True


ConsentCreate = ConsentRequest


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
    formula_explanation: Optional[str] = None
    scores_breakdown_json: Dict[str, Any]
    technical_analysis_json: Dict[str, Any]
    non_technical_analysis_json: Dict[str, Any]
    coaching_suggestions_json: Optional[Any] = None
    signal_timeline_json: Optional[Any] = None
    transcript_evidence_json: Optional[Any] = None
    gaps_to_validate_json: Optional[Any] = None
    improvements_json: Optional[Any] = None
    created_at: datetime


# ----------------------------------------------------------------------
# Question Bank Schemas
# ----------------------------------------------------------------------
class QuestionBankCreate(BaseModel):
    category: QuestionCategoryEnum
    sub_category: str
    difficulty_level: DifficultyLevelEnum = DifficultyLevelEnum.MEDIUM
    question_text: str
    ideal_answer_rubric: Optional[str] = None
    relevant_skills_json: Optional[List[str]] = None
    is_active: bool = True


class QuestionBankResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: QuestionCategoryEnum
    sub_category: str
    difficulty_level: DifficultyLevelEnum
    question_text: str
    ideal_answer_rubric: Optional[str] = None
    relevant_skills_json: Optional[List[str]] = None
    is_active: bool = True
    created_at: datetime


class QuestionListResponse(BaseModel):
    items: List[QuestionBankResponse]
    total: int


# ----------------------------------------------------------------------
# Transcript Schemas
# ----------------------------------------------------------------------
class TranscriptCreate(BaseModel):
    assessment_id: int
    transcript_text: str
    word_timestamps_json: Optional[Dict[str, Any]] = None


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    transcript_text: str
    word_timestamps_json: Optional[Dict[str, Any]] = None
    created_at: datetime


# ----------------------------------------------------------------------
# Vision Telemetry Schemas
# ----------------------------------------------------------------------
class VisionTelemetryCreate(BaseModel):
    assessment_id: int
    face_visible_pct: float = 0.0
    head_nods_count: int = 0
    frame_stability_score: float = 0.0
    snapshots_json: Optional[List[Dict[str, Any]]] = None


class VisionTelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    face_visible_pct: float
    head_nods_count: int
    frame_stability_score: float
    snapshots_json: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


# ----------------------------------------------------------------------
# Audio Telemetry Schemas
# ----------------------------------------------------------------------
class AudioTelemetryCreate(BaseModel):
    assessment_id: int
    avg_volume_db: float = 0.0
    background_noise_level: BackgroundNoiseLevelEnum = BackgroundNoiseLevelEnum.LOW
    clipping_detected: bool = False
    silence_ratio_pct: float = 0.0
    filler_words_per_min: int = 0
    speaking_pace_wpm: int = 0


class AudioTelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    avg_volume_db: float
    background_noise_level: BackgroundNoiseLevelEnum
    clipping_detected: bool
    silence_ratio_pct: float
    filler_words_per_min: int
    speaking_pace_wpm: int
    created_at: datetime


# ----------------------------------------------------------------------
# Share Grant Schemas
# ----------------------------------------------------------------------
class ShareGrantCreate(BaseModel):
    assessment_id: int
    expires_in_days: int = 7


class ShareGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    shared_by_candidate_id: int
    share_token: str
    expires_at: datetime
    created_at: datetime


# ----------------------------------------------------------------------
# Deletion Request Schemas
# ----------------------------------------------------------------------
class DeletionRequestCreate(BaseModel):
    notes: Optional[str] = None


class DeletionRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    requested_at: datetime
    completed_at: Optional[datetime] = None
    status: DeletionRequestStatusEnum
    notes: Optional[str] = None


# ----------------------------------------------------------------------
# Analysis Run Schemas
# ----------------------------------------------------------------------
class AnalysisRunCreate(BaseModel):
    assessment_id: int
    run_type: RunTypeEnum


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    run_type: RunTypeEnum
    status: RunStatusEnum
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardAssessment(BaseModel):
    id: int
    assessment_type: AssessmentTypeEnum
    status: AssessmentStatusEnum
    coaching_band: Optional[CoachingBandEnum] = None
    overall_score: Optional[int] = None
    created_at: datetime


# 17. Analytics Dashboard Schemas (Week 2)
class ExecutiveSummary(BaseModel):
    total_assessments: int
    completed: int
    latest_coaching_band: Optional[CoachingBandEnum] = None
    band_trend: List[CoachingBandEnum] = []
    average_overall_score: float = 0.0
    assessments: List[DashboardAssessment] = []


class RadarChartData(BaseModel):
    llm_architecture: float = 0.0
    rag_systems: float = 0.0
    ml_fundamentals: float = 0.0
    system_design: float = 0.0
    code_quality: float = 0.0
    ai_ethics: float = 0.0


class CommunicationTimepoint(BaseModel):
    assessment_id: int
    date: datetime
    wpm: int
    filler_per_min: int
    silence_pct: float


class DashboardResponse(BaseModel):
    executive_summary: ExecutiveSummary
    radar: RadarChartData
    communication_trend: List[CommunicationTimepoint]


# 18. GDPR Deletion Request Schemas (Week 3)
class DeletionRequestCreate(BaseModel):
    candidate_id: int


class DeletionRequestResponse(BaseModel):
    id: int
    candidate_id: int
    status: str
    requested_at: datetime
    completed_at: Optional[datetime] = None
    deleted_bytes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
