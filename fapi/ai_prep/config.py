"""
AIPrep Configuration Settings
=============================
Zero hardcoded values. All configuration values are loaded via environment variables / settings.
"""
import os
from typing import Optional, Any
from pydantic_settings import BaseSettings
from pydantic import Field


class AiPrepSettings(BaseSettings):
    """Configuration settings for AIPrep media pipeline, YouTube client, and orchestrators."""

    ENV: str = Field(
        default_factory=lambda: os.getenv("ENV", os.getenv("APP_ENV", "local")),
        description="Current runtime environment (local, test, staging, production)",
    )

    # Local Storage Configuration
    LOCAL_STORAGE_BASE_PATH: str = Field(
        default_factory=lambda: os.getenv("AIPREP_LOCAL_STORAGE_PATH", os.getenv("AIPREP_LOCAL_STORAGE_DIR", os.path.join("storage", "aiprep"))),
        description="Root directory for local video/audio chunks and assembled media files",
    )
    LOCAL_STORAGE_DIR: Optional[str] = Field(
        default=None,
        description="Alias for LOCAL_STORAGE_BASE_PATH",
    )
    CHUNK_DURATION_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_CHUNK_DURATION_SECONDS", "30")),
        description="Duration of each recorded video chunk in seconds",
    )
    MAX_CHUNK_SIZE_MB: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_MAX_CHUNK_SIZE_MB", "50")),
        description="Maximum allowed chunk upload size in megabytes",
    )
    MAX_MEDIA_UPLOAD_MB: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_MAX_MEDIA_UPLOAD_MB", "500")),
        description="Maximum allowed direct media upload size in megabytes",
    )
    MAX_AUDIO_UPLOAD_MB: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_MAX_AUDIO_UPLOAD_MB", "100")),
        description="Maximum allowed direct audio recording upload size in megabytes",
    )
    ABANDONED_CHUNK_TTL_HOURS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_ABANDONED_CHUNK_TTL_HOURS", "24")),
        description="Time-to-live in hours before orphan chunks from abandoned sessions are purged",
    )

    # Audio & Video Processing (FFmpeg & DSP)
    FFMPEG_PATH: str = Field(
        default_factory=lambda: os.getenv("FFMPEG_PATH", "ffmpeg"),
        description="Path or binary name for ffmpeg executable",
    )
    AUDIO_SAMPLE_RATE: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_AUDIO_SAMPLE_RATE", "16000")),
        description="Target sample rate for extracted audio.wav (Hz)",
    )
    AUDIO_CHANNELS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_AUDIO_CHANNELS", "1")),
        description="Target channels for extracted audio (1 for mono, 2 for stereo)",
    )

    # YouTube API Configuration (Single Account Unlisted Upload)
    YOUTUBE_API_KEY: Optional[str] = Field(
        default=None,
        description="Google / YouTube Data API key",
    )
    YOUTUBE_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="OAuth2 Client ID for YouTube Upload",
    )
    YOUTUBE_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="OAuth2 Client Secret for YouTube Upload",
    )
    YOUTUBE_REFRESH_TOKEN: Optional[str] = Field(
        default=None,
        description="OAuth2 Refresh Token for automated background uploads",
    )
    YOUTUBE_TOKEN_URI: str = Field(
        default_factory=lambda: os.getenv("YOUTUBE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        description="OAuth2 token URI",
    )
    YOUTUBE_API_SCOPE: str = Field(
        default="https://www.googleapis.com/auth/youtube.upload",
        description="OAuth2 scope for YouTube uploads",
    )
    YOUTUBE_CREDENTIALS_FILE: Optional[str] = Field(
        default=None,
        description="Path to client_secrets.json or credentials file if used",
    )
    YOUTUBE_PRIVACY_STATUS: str = Field(
        default_factory=lambda: os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted"),
        description="Privacy status for assessment videos (strictly unlisted)",
    )
    YOUTUBE_CATEGORY_ID: str = Field(
        default_factory=lambda: os.getenv("AIPREP_YOUTUBE_CATEGORY_ID", os.getenv("YOUTUBE_CATEGORY_ID", "27")),
        description="YouTube video category ID (default: 27 for Education)",
    )
    YOUTUBE_DEFAULT_TAGS: list = Field(
        default_factory=lambda: [t.strip() for t in os.getenv("AIPREP_YOUTUBE_DEFAULT_TAGS", "AIPrep,WhiteboxLearning,PracticeAssessment").split(",") if t.strip()],
        description="Default metadata tags for uploaded assessment videos",
    )
    YOUTUBE_UPLOAD_CHUNK_SIZE_BYTES: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_YOUTUBE_UPLOAD_CHUNK_SIZE_BYTES", str(5 * 1024 * 1024))),
        description="Chunk size in bytes for resumable YouTube media upload",
    )
    STREAMING_CHUNK_SIZE_BYTES: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_STREAMING_CHUNK_SIZE_BYTES", str(64 * 1024))),
        description="Buffer chunk size in bytes for audio/video streaming responses",
    )
    REDIS_URL: Optional[str] = Field(
        default_factory=lambda: os.getenv("REDIS_URL", os.getenv("AIPREP_REDIS_URL")),
        description="Optional Redis connection URL for distributed YouTube quota accounting",
    )
    YOUTUBE_DAILY_QUOTA_LIMIT: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_YOUTUBE_DAILY_QUOTA_LIMIT", os.getenv("YOUTUBE_DAILY_QUOTA_LIMIT", "10000"))),
        description="Daily quota unit limit for YouTube Data API v3 (default: 10000)",
    )
    YOUTUBE_UPLOAD_QUOTA_COST: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_YOUTUBE_UPLOAD_QUOTA_COST", os.getenv("YOUTUBE_UPLOAD_QUOTA_COST", "1600"))),
        description="Quota cost in units for a single YouTube video upload (default: 1600)",
    )
    YOUTUBE_ENABLE_QUOTA_TRACKING: bool = Field(
        default_factory=lambda: os.getenv("AIPREP_YOUTUBE_ENABLE_QUOTA_TRACKING", "true").lower() in ("true", "1", "yes"),
        description="Whether to track and enforce YouTube daily upload quota before dispatching uploads",
    )

    # Storage Cleanup
    CLEANUP_STORAGE_AFTER_UPLOAD: bool = Field(
        default_factory=lambda: os.getenv("AIPREP_CLEANUP_STORAGE_AFTER_UPLOAD", "true").lower() in ("true", "1", "yes"),
        description="Whether to purge local video/audio storage once successfully uploaded to YouTube",
    )

    # SSE / Status Streaming Settings
    SSE_PING_INTERVAL_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_SSE_PING_INTERVAL", "5")),
        description="Ping / status poll interval in seconds for SSE processing streams",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.LOCAL_STORAGE_DIR:
            self.LOCAL_STORAGE_DIR = self.LOCAL_STORAGE_BASE_PATH
        if not self.YOUTUBE_API_KEY:
            self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not self.YOUTUBE_CLIENT_ID:
            self.YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
        if not self.YOUTUBE_CLIENT_SECRET:
            self.YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
        if not self.YOUTUBE_REFRESH_TOKEN:
            self.YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
        if not self.YOUTUBE_CREDENTIALS_FILE:
            self.YOUTUBE_CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS_FILE")

    class Config:
        env_prefix = "AIPREP_"
        case_sensitive = False
        extra = "allow"


# Global settings singleton instance
settings = AiPrepSettings()
