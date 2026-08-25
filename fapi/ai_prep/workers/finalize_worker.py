from datetime import datetime
import logging
from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.models import RunTypeEnum, RunStatusEnum, AssessmentStatusEnum, AiPrepAssessmentORM
from fapi.ai_prep.crud.runs import create_analysis_run, update_analysis_run_status
from fapi.db.database import SessionLocal

logger = logging.getLogger("wbl.ai_prep.workers.finalize")


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def finalize_task(self, assessment_id: int):
    """
    Finalize Worker stub: Transitions assessment status to COMPLETED and sets completed_at timestamp.
    """
    logger.info("Executing Finalize Task for assessment %s", assessment_id)
    db = SessionLocal()
    run = create_analysis_run(db, assessment_id, RunTypeEnum.FULL, celery_task_id=getattr(self.request, "id", None))

    try:
        assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")

        assessment.status = AssessmentStatusEnum.COMPLETED
        assessment.completed_at = datetime.utcnow()
        db.commit()

        update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
        logger.info("Assessment %s marked as COMPLETED successfully", assessment_id)
        return {"assessment_id": assessment_id, "status": "COMPLETED"}

    except Exception as exc:
        logger.error("Finalize Task failed for assessment %s: %s", assessment_id, exc)
        update_analysis_run_status(db, run.id, RunStatusEnum.FAILED, error_message=str(exc))
        raise self.retry(exc=exc, countdown=2 ** getattr(self.request, "retries", 1) * 30)

    finally:
        db.close()
