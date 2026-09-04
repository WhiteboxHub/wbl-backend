"""
Configuration settings for AI Prep Platform.
"""

import os


class Settings:
    LOCAL_STORAGE_DIR: str = os.getenv("LOCAL_STORAGE_DIR", "/tmp/aiprep_uploads")


settings = Settings()
