from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.workers.tasks import process_assessment, run_assessment_pipeline_sync
from fapi.ai_prep.workers.stt_worker import stt_task
from fapi.ai_prep.workers.audio_worker import audio_analysis_task
from fapi.ai_prep.workers.vision_worker import vision_task
from fapi.ai_prep.workers.llm_worker import llm_analysis_task
from fapi.ai_prep.workers.youtube_worker import upload_video_to_youtube_task
from fapi.ai_prep.workers.finalize_worker import finalize_task

__all__ = [
    "celery_app",
    "process_assessment",
    "run_assessment_pipeline_sync",
    "stt_task",
    "audio_analysis_task",
    "vision_task",
    "llm_analysis_task",
    "upload_video_to_youtube_task",
    "finalize_task",
]
