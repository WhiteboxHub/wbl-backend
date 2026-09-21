"""Configuration settings and environment variables for AI Prep Tool.
Follows 12-factor application standards with zero hardcoded credentials.
"""
import os

# Local Media Storage Directory
STORAGE_BASE_DIR: str = os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep")
MAX_CHUNK_SIZE: int = int(os.getenv("AIPREP_MAX_CHUNK_SIZE", str(25 * 1024 * 1024)))  # 25 MB
MAX_MEDIA_SIZE: int = int(os.getenv("AIPREP_MAX_MEDIA_SIZE", str(150 * 1024 * 1024)))  # 150 MB

# Media Processing Binaries
FFMPEG_BINARY: str = os.getenv("AIPREP_FFMPEG_PATH", "ffmpeg")
FFPROBE_BINARY: str = os.getenv("AIPREP_FFPROBE_PATH", "ffprobe")
