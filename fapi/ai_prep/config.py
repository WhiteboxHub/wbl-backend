"""
AIPrep Configuration Settings (Strictly BE2)
============================================
Zero hardcoded values. All configuration values are loaded via environment variables.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class AiPrepSettings(BaseSettings):
    """Configuration settings for AIPrep BE2 media pipeline and orchestrator."""

    ENV: str = Field(
        default_factory=lambda: os.getenv("ENV", "local"),
        description="Current runtime environment (local, test, staging, production)",
    )

    # Local Storage Configuration
    LOCAL_STORAGE_BASE_PATH: str = Field(
        default_factory=lambda: os.getenv("AIPREP_LOCAL_STORAGE_PATH", os.path.join("storage", "ai_prep")),
        description="Root directory for local video/audio chunks and assembled media files",
    )
    CHUNK_DURATION_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_CHUNK_DURATION_SECONDS", "30")),
        description="Duration of each recorded video chunk in seconds",
    )
    MAX_CHUNK_SIZE_MB: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_MAX_CHUNK_SIZE_MB", "50")),
        description="Maximum allowed chunk upload size in megabytes",
    )
    ABANDONED_CHUNK_TTL_HOURS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_ABANDONED_CHUNK_TTL_HOURS", "24")),
        description="Time-to-live in hours before orphan chunks from abandoned sessions are purged",
    )

    # Audio & Video Processing (BE2 Media Extraction)
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

    # YouTube API Configuration (BE2 Unlisted Video Upload)
    YOUTUBE_API_KEY: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOUTUBE_API_KEY"),
        description="Google / YouTube Data API key",
    )
    YOUTUBE_CLIENT_ID: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOUTUBE_CLIENT_ID"),
        description="OAuth2 Client ID for YouTube Upload",
    )
    YOUTUBE_CLIENT_SECRET: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOUTUBE_CLIENT_SECRET"),
        description="OAuth2 Client Secret for YouTube Upload",
    )
    YOUTUBE_REFRESH_TOKEN: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOUTUBE_REFRESH_TOKEN"),
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
        default_factory=lambda: os.getenv("YOUTUBE_CREDENTIALS_FILE"),
        description="Path to client_secrets.json or service account credentials if used",
    )
    YOUTUBE_PRIVACY_STATUS: str = Field(
        default_factory=lambda: os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted"),
        description="Privacy status for assessment videos (strictly unlisted)",
    )
    YOUTUBE_ACCOUNTS_JSON: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOUTUBE_ACCOUNTS_JSON"),
        description="JSON array of YouTube account credentials for sequential quota rotation",
    )
    YOUTUBE_DAILY_UPLOAD_LIMIT_PER_ACCOUNT: int = Field(
        default_factory=lambda: int(os.getenv("YOUTUBE_DAILY_UPLOAD_LIMIT_PER_ACCOUNT", "6")),
        description="Default max uploads per account before sequential failover (1600 units/upload out of 10k daily quota)",
    )
    YOUTUBE_QUOTA_RESET_HOUR_UTC: int = Field(
        default_factory=lambda: int(os.getenv("YOUTUBE_QUOTA_RESET_HOUR_UTC", "8")),
        description="Hour UTC when YouTube daily quota resets (08:00 UTC = 00:00 PST Midnight)",
    )


    # SSE / Status Streaming Settings
    SSE_PING_INTERVAL_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("AIPREP_SSE_PING_INTERVAL", "5")),
        description="Ping / status poll interval in seconds for SSE processing streams",
    )

    class Config:
        env_prefix = "AIPREP_"
        case_sensitive = False
        extra = "allow"


# Global settings singleton instance
settings = AiPrepSettings()

