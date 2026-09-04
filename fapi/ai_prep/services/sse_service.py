"""
Server-Sent Events (SSE) Processing Status Stream Service
=========================================================
Generates async SSE data streams and single-shot snapshots
for monitoring background pipeline progress.
"""
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.orm import Session

from fapi.ai_prep.config import settings
from fapi.ai_prep.models import AiPrepAssessment, AiPrepAnalysisRun, AssessmentStatusEnum
from fapi.db.database import SessionLocal

logger = logging.getLogger(__name__)


class SSEService:
    """Streams step-by-step progress via Server-Sent Events."""

    def get_status_snapshot(self, assessment_id: int, db: Session) -> Dict[str, Any]:
        """Calculates percentage and step snapshot based on DB state."""
        assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
        if not assessment:
            return {
                "assessment_id": assessment_id,
                "status": "NOT_FOUND",
                "progress_percentage": 0,
                "current_step": "UNKNOWN",
                "error_message": "Assessment not found",
            }

        runs = (
            db.query(AiPrepAnalysisRun)
            .filter(AiPrepAnalysisRun.assessment_id == assessment_id)
            .order_by(AiPrepAnalysisRun.id.asc())
            .all()
        )

        total_steps = max(len(runs), 1)
        completed_runs = [r for r in runs if r.status == "COMPLETED"]
        failed_runs = [r for r in runs if r.status == "FAILED"]
        running_runs = [r for r in runs if r.status == "RUNNING"]

        if assessment.status == AssessmentStatusEnum.COMPLETED.value:
            progress = 100
            current_step = "COMPLETED"
        elif failed_runs or assessment.status == AssessmentStatusEnum.FAILED.value:
            progress = min(90, int((len(completed_runs) / total_steps) * 100))
            current_step = "FAILED"
        elif running_runs:
            progress = min(95, int(((len(completed_runs) + 0.5) / total_steps) * 100))
            current_step = running_runs[0].run_type
        elif completed_runs:
            progress = min(95, int((len(completed_runs) / total_steps) * 100))
            current_step = f"{completed_runs[-1].run_type}_COMPLETED"
        else:
            progress = 10
            current_step = "MEDIA_ASSEMBLED"

        error_msg = failed_runs[0].error_message if failed_runs else None

        return {
            "assessment_id": assessment_id,
            "status": assessment.status,
            "progress_percentage": progress,
            "current_step": current_step,
            "error_message": error_msg,
            "youtube_url": assessment.youtube_url,
        }

    async def stream_assessment_progress(self, assessment_id: int) -> AsyncGenerator[str, None]:
        """Yields SSE events formatted as `data: {...}\n\n` until complete or failed."""
        logger.info("Starting SSE progress stream for assessment %s", assessment_id)
        while True:
            db = SessionLocal()
            try:
                snapshot = self.get_status_snapshot(assessment_id, db)
                payload = json.dumps(snapshot)
                yield f"data: {payload}\n\n"

                # Terminal conditions
                if snapshot["status"] in {AssessmentStatusEnum.COMPLETED.value, AssessmentStatusEnum.FAILED.value, "NOT_FOUND"}:
                    logger.info("Ending SSE stream for assessment %s (terminal status: %s)", assessment_id, snapshot["status"])
                    break
            finally:
                db.close()

            await asyncio.sleep(settings.SSE_PING_INTERVAL_SECONDS)


sse_service = SSEService()
