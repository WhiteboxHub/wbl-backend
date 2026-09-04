"""
Custom Exceptions for AIPrep
============================
Specialized domain exceptions for media chunk validation, assembly, and upload.
"""
from typing import List, Optional


class AIPrepBaseException(Exception):
    """Base exception for all AIPrep domain errors."""
    pass


class ChunkValidationError(AIPrepBaseException):
    """Raised when an uploaded chunk fails validation."""
    pass


class MissingChunksError(AIPrepBaseException):
    """Raised when sequential assembly is requested but chunks are missing."""
    def __init__(self, missing_chunks: List[int], total_chunks: int):
        self.missing_chunks = missing_chunks
        self.total_chunks = total_chunks
        super().__init__(
            f"Cannot assemble media. Missing chunks: {missing_chunks} of {total_chunks} expected."
        )


class MediaAssemblyError(AIPrepBaseException):
    """Raised when concatenation of video chunks fails."""
    pass


class AudioExtractionError(AIPrepBaseException):
    """Raised when extracting audio.wav from video fails."""
    pass


class YouTubeUploadError(AIPrepBaseException):
    """Raised when uploading video to YouTube fails."""
    pass


class AllYouTubeQuotasExhaustedError(YouTubeUploadError):
    """Raised when all configured YouTube accounts have exhausted their daily upload quota."""
    def __init__(self, seconds_until_reset: int = 86400, total_accounts: int = 0, message: Optional[str] = None):
        self.seconds_until_reset = seconds_until_reset
        self.total_accounts = total_accounts
        msg = message or f"All {total_accounts} YouTube accounts have exhausted their upload quota for today. Quota resets in {seconds_until_reset} seconds."
        super().__init__(msg)



class MediaStorageError(AIPrepBaseException):
    """Raised for filesystem storage errors."""
    pass


class AssessmentNotFoundError(AIPrepBaseException):
    """Raised when assessment ID does not exist."""
    pass
