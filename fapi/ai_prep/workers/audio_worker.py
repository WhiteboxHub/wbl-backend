import logging
from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.models import RunTypeEnum, RunStatusEnum, AiPrepAudioTelemetryORM, BackgroundNoiseLevelEnum
from fapi.ai_prep.crud.runs import create_analysis_run, update_analysis_run_status
from fapi.db.database import SessionLocal

logger = logging.getLogger("wbl.ai_prep.workers.audio")


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def audio_analysis_task(self, assessment_id: int):
    """
    Audio Analysis Worker stub: Extracts speech metrics from audio.wav (WPM, silence, volume, filler words).
    """
    logger.info("Executing Audio Analysis Task for assessment %s", assessment_id)
    db = SessionLocal()
    run = create_analysis_run(db, assessment_id, RunTypeEnum.AUDIO, celery_task_id=getattr(self.request, "id", None))

    try:
        existing_audio = db.query(AiPrepAudioTelemetryORM).filter(
            AiPrepAudioTelemetryORM.assessment_id == assessment_id
        ).first()

        if existing_audio:
            existing_audio.avg_volume_db = -18.5
            existing_audio.background_noise_level = BackgroundNoiseLevelEnum.LOW
            existing_audio.clipping_detected = False
            existing_audio.silence_ratio_pct = 14.2
            existing_audio.filler_words_per_min = 2
            existing_audio.speaking_pace_wpm = 138
        else:
            audio_record = AiPrepAudioTelemetryORM(
                assessment_id=assessment_id,
                avg_volume_db=-18.5,
                background_noise_level=BackgroundNoiseLevelEnum.LOW,
                clipping_detected=False,
                silence_ratio_pct=14.2,
                filler_words_per_min=2,
                speaking_pace_wpm=138
            )
            db.add(audio_record)
        db.commit()

        update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
        return {"assessment_id": assessment_id, "status": "COMPLETED"}

    except Exception as exc:
        logger.error("Audio Task failed for assessment %s: %s", assessment_id, exc)
        update_analysis_run_status(db, run.id, RunStatusEnum.FAILED, error_message=str(exc))
        raise self.retry(exc=exc, countdown=2 ** getattr(self.request, "retries", 1) * 30)

    finally:
        db.close()
