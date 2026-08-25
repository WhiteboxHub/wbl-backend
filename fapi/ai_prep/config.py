import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Local Server Storage Configuration
LOCAL_STORAGE_DIR: str = os.getenv("AIPREP_LOCAL_STORAGE_DIR", os.path.join(os.getcwd(), "storage", "aiprep"))
SIGNED_URL_TTL_MINUTES: int = int(os.getenv("AIPREP_SIGNED_URL_TTL_MINUTES", "15"))

# Storage Lifecycle & Retention Configuration
AIPREP_RETENTION_DAYS: int = int(os.getenv("AIPREP_RETENTION_DAYS", "90"))
AIPREP_ORPHAN_CHUNK_HOURS: int = int(os.getenv("AIPREP_ORPHAN_CHUNK_HOURS", "24"))

# YouTube Integration Configuration
YOUTUBE_UPLOAD_ENABLED: bool = os.getenv("AIPREP_YOUTUBE_UPLOAD_ENABLED", "true").lower() in ("true", "1", "yes")
YOUTUBE_CLIENT_ID: Optional[str] = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET: Optional[str] = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN: Optional[str] = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_PRIVACY_STATUS: str = os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted")
YOUTUBE_CATEGORY_ID: str = os.getenv("YOUTUBE_CATEGORY_ID", "27")  # 27 = Education

# Celery & Redis Configuration
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_TASK_DEFAULT_QUEUE: str = "ai_prep"

# Assessment Limits
AIPREP_CREATE_LIMIT: int = int(os.getenv("AIPREP_CREATE_LIMIT", "5"))
AIPREP_CREATE_WINDOW_SECONDS: int = int(os.getenv("AIPREP_CREATE_WINDOW_SECONDS", "86400"))
