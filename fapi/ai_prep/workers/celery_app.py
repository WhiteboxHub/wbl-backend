import logging
from fapi.ai_prep.config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_DEFAULT_QUEUE,
)

logger = logging.getLogger("wbl.ai_prep.celery")

try:
    from celery import Celery

    celery_app = Celery(
        "ai_prep_workers",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
        include=[
            "fapi.ai_prep.workers.tasks",
            "fapi.ai_prep.workers.stt_worker",
            "fapi.ai_prep.workers.audio_worker",
            "fapi.ai_prep.workers.vision_worker",
            "fapi.ai_prep.workers.llm_worker",
            "fapi.ai_prep.workers.youtube_worker",
            "fapi.ai_prep.workers.finalize_worker",
        ]
    )

    from celery.schedules import crontab

    celery_app.conf.update(
        task_default_queue=CELERY_TASK_DEFAULT_QUEUE,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_routes={
            "fapi.ai_prep.workers.*": {"queue": CELERY_TASK_DEFAULT_QUEUE},
        },
        task_annotations={
            "fapi.ai_prep.workers.youtube_worker.upload_video_to_youtube_task": {
                "rate_limit": "10/m"  # Throttle YouTube uploads to avoid API bursts
            }
        },
        beat_schedule={
            "cleanup-expired-media-nightly": {
                "task": "fapi.ai_prep.workers.tasks.cleanup_expired_media_task",
                "schedule": crontab(hour=2, minute=0),  # Runs nightly at 02:00 AM UTC
                "args": (90, 24),  # 90-day retention for session audio, 24-hour cleanup for orphan chunks
                "options": {"queue": CELERY_TASK_DEFAULT_QUEUE},
            }
        }
    )
    logger.info("Celery app initialized with queue: %s", CELERY_TASK_DEFAULT_QUEUE)

except ImportError:
    logger.warning("Celery library not available; creating mock celery task runner.")

    class _MockRequest:
        id = "mock-task-id"
        retries = 0

    class _MockTask:
        def __init__(self, func, bind=False):
            self.func = func
            self.bind = bind
            self.request = _MockRequest()

        def delay(self, *args, **kwargs):
            class _AsyncResult:
                id = "mock-task-id"
            if self.bind:
                self.func(self, *args, **kwargs)
            else:
                self.func(*args, **kwargs)
            return _AsyncResult()

        def apply_async(self, args=(), kwargs=None, **options):
            kwargs = kwargs or {}
            return self.delay(*args, **kwargs)

        def s(self, *args, **kwargs):
            return self

        def __call__(self, *args, **kwargs):
            if self.bind:
                return self.func(self, *args, **kwargs)
            return self.func(*args, **kwargs)

        def retry(self, exc=None, countdown=0, max_retries=3):
            raise exc

    class _MockCeleryApp:
        def task(self, *args, **kwargs):
            bind = kwargs.get("bind", False)
            def decorator(f):
                return _MockTask(f, bind=bind)
            return decorator

    celery_app = _MockCeleryApp()
