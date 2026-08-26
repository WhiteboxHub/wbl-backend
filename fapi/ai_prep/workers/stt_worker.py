import logging
from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.models import RunTypeEnum, RunStatusEnum, AiPrepTranscriptORM
from fapi.ai_prep.crud.runs import create_analysis_run, update_analysis_run_status
from fapi.ai_prep.crud.media import get_media_by_assessment_id
from fapi.db.database import SessionLocal

logger = logging.getLogger("wbl.ai_prep.workers.stt")


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def stt_task(self, assessment_id: int):
    """
    STT Worker stub: Transcribes audio.wav into text and word timestamps.
    """
    logger.info("Executing STT Task for assessment %s", assessment_id)
    db = SessionLocal()
    run = create_analysis_run(db, assessment_id, RunTypeEnum.STT, celery_task_id=getattr(self.request, "id", None))

    try:
        media = get_media_by_assessment_id(db, assessment_id)
        if not media or not media.audio_file_path:
            raise FileNotFoundError(f"No audio file path recorded for assessment {assessment_id}")

        # Stub transcript result
        sample_transcript = (
            "Hello, thank you for having me. I am an AI Engineer with experience in building "
            "production RAG pipelines and deploying fine-tuned LLM models. In my previous role, "
            "I designed an automated retrieval pipeline that reduced latency by 35 percent."
        )
        sample_segments = [
            {"word": "Hello", "start": 0.1, "end": 0.5},
            {"word": "thank", "start": 0.6, "end": 0.9},
            {"word": "you", "start": 1.0, "end": 1.2},
            {"word": "for", "start": 1.3, "end": 1.5},
            {"word": "having", "start": 1.6, "end": 1.9},
            {"word": "me", "start": 2.0, "end": 2.2},
        ]

        # Save to ai_prep_transcripts
        existing_tx = db.query(AiPrepTranscriptORM).filter(AiPrepTranscriptORM.assessment_id == assessment_id).first()
        if existing_tx:
            existing_tx.transcript_text = sample_transcript
            existing_tx.word_timestamps_json = sample_segments
        else:
            tx = AiPrepTranscriptORM(
                assessment_id=assessment_id,
                transcript_text=sample_transcript,
                word_timestamps_json=sample_segments
            )
            db.add(tx)
        db.commit()

        update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
        return {"assessment_id": assessment_id, "status": "COMPLETED"}

    except Exception as exc:
        logger.error("STT Task failed for assessment %s: %s", assessment_id, exc)
        update_analysis_run_status(db, run.id, RunStatusEnum.FAILED, error_message=str(exc))
        raise self.retry(exc=exc, countdown=2 ** getattr(self.request, "retries", 1) * 30)

    finally:
        db.close()
