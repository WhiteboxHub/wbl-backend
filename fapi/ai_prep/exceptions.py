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


class LLMKeyMissingError(AIPrepBaseException):
    """Raised when candidate does not have an active LLM API key."""
    def __init__(self, message: str = "No active LLM API key found for this candidate. Please configure an API key in settings before starting."):
        self.error_code = "LLM_KEY_NOT_CONFIGURED"
        super().__init__(message)


class ResumeMissingError(AIPrepBaseException):
    """Raised when candidate does not have a parsed resume uploaded."""
    def __init__(self, message: str = "No parsed resume found for this candidate. Please upload your resume before starting an assessment."):
        self.error_code = "RESUME_NOT_FOUND"
        super().__init__(message)


class AssessmentOperationError(AIPrepBaseException):
    """Raised when an assessment state machine operation is rejected."""
    def __init__(self, message: str, error_code: str = "OPERATION_REJECTED"):
        self.error_code = error_code
        super().__init__(message)

