"""
AIPrep External Service Clients
"""
from fapi.ai_prep.clients.youtube_client import (
    youtube_client,
    YouTubeClient,
    YouTubeUploadError,
)

__all__ = [
    "youtube_client",
    "YouTubeClient",
    "YouTubeUploadError",
]
