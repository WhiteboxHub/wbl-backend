"""
Transcription Provider Abstraction Layer for AI Prep Audio Engine.

Supports configurable transcription providers:
- whisper (Faster-Whisper local backend - default)
- socket (Socket/WebSocket streaming STT adapter)
- browser (Browser Web Speech API / frontend STT adapter)
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, ClassVar
from .stt import transcribe_audio

logger = logging.getLogger("wbl.ai_prep.audio_engine.providers")


class TranscriptionProviderError(Exception):
    """Base exception for transcription provider failures."""
    pass


class InvalidProviderConfigError(TranscriptionProviderError):
    """Raised when an unsupported provider name is specified in configuration."""
    pass


class BaseTranscriptionProvider(ABC):
    """
    Abstract base interface for all transcription providers.
    Every provider must return a normalized dictionary:
    {
        "transcript_text": str,
        "word_timestamps": List[Dict[str, Any]],
        "duration": float
    }
    """
    provider_name: ClassVar[str] = "base"

    @abstractmethod
    def transcribe(
        self,
        audio_path: Optional[str] = None,
        model_size: str = "base",
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Transcribe audio or adapt pre-generated transcript into normalized structure."""
        pass


class WhisperTranscriptionProvider(BaseTranscriptionProvider):
    """Primary provider using Faster-Whisper locally on CPU/GPU."""
    provider_name: ClassVar[str] = "whisper"

    def transcribe(
        self,
        audio_path: Optional[str] = None,
        model_size: str = "base",
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        # Reuse precomputed transcript and word timestamps if provided (skips redundant Whisper run)
        if precomputed_transcript_text is not None and precomputed_word_timestamps is not None:
            logger.info("[WhisperProvider] Reusing precomputed live STT transcript & word timestamps (skipping duplicate Whisper run)")
            return {
                "transcript_text": precomputed_transcript_text,
                "word_timestamps": precomputed_word_timestamps,
                "duration": kwargs.get("duration", 0.0),
            }

        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError(f"WhisperProvider requires a valid audio_path. Given: {audio_path}")

        logger.info(f"[WhisperProvider] Transcribing audio file: {audio_path} (model: {model_size})")
        try:
            result = transcribe_audio(audio_path=audio_path, model_size=model_size)
            return {
                "transcript_text": result.get("transcript_text", ""),
                "word_timestamps": result.get("word_timestamps", []),
                "duration": result.get("duration", 0.0),
            }
        except Exception as e:
            logger.error(f"[WhisperProvider] Transcription failed for {audio_path}: {e}", exc_info=True)
            raise TranscriptionProviderError(f"Whisper transcription failed: {str(e)}") from e


class SocketTranscriptionProvider(BaseTranscriptionProvider):
    """
    Adapter for Socket / WebSocket streaming transcription.
    Connects to external or internal WebSocket STT streaming services.
    """
    provider_name: ClassVar[str] = "socket"

    def __init__(self, socket_endpoint: Optional[str] = None):
        self.socket_endpoint = socket_endpoint or os.getenv("SOCKET_STT_ENDPOINT", "ws://localhost:8080/stt")

    def transcribe(
        self,
        audio_path: Optional[str] = None,
        model_size: str = "base",
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        # If the socket service pushed completed results during the session, adapt them
        if precomputed_transcript_text is not None:
            logger.info("[SocketProvider] Consuming completed transcript stream from socket session")
            return {
                "transcript_text": precomputed_transcript_text,
                "word_timestamps": precomputed_word_timestamps or [],
                "duration": kwargs.get("duration", 0.0),
            }

        logger.warning(
            f"[SocketProvider] Live Socket STT service integration point reached. "
            f"Configured endpoint: {self.socket_endpoint}. Audio file: {audio_path}."
        )
        raise TranscriptionProviderError(
            "SocketProvider: Live WebSocket STT streaming service is not connected yet."
        )


class BrowserTranscriptionProvider(BaseTranscriptionProvider):
    """
    Consumes browser-generated transcripts (e.g. Web Speech API) sent by the frontend.
    Avoids running duplicate backend STT when browser transcript is provided.
    """
    provider_name: ClassVar[str] = "browser"

    def transcribe(
        self,
        audio_path: Optional[str] = None,
        model_size: str = "base",
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if precomputed_transcript_text is None or precomputed_transcript_text == "":
            logger.warning("[BrowserProvider] No browser-generated transcript was supplied in request.")
            return {
                "transcript_text": "",
                "word_timestamps": [],
                "duration": 0.0
            }

        logger.info(f"[BrowserProvider] Successfully consuming browser transcript ({len(precomputed_transcript_text)} chars)")
        return {
            "transcript_text": precomputed_transcript_text,
            "word_timestamps": precomputed_word_timestamps or [],
            "duration": kwargs.get("duration", 0.0),
        }


# Registry of supported providers
PROVIDER_REGISTRY = {
    "whisper": WhisperTranscriptionProvider,
    "socket": SocketTranscriptionProvider,
    "browser": BrowserTranscriptionProvider,
}

_PROVIDER_CACHE: Dict[str, BaseTranscriptionProvider] = {}


def get_transcription_provider(provider_name: Optional[str] = None) -> BaseTranscriptionProvider:
    """
    Factory to instantiate/retrieve the configured transcription provider (singleton cached).
    Reads TRANSCRIPTION_PROVIDER from environment if not explicitly passed.
    """
    selected = (provider_name or os.getenv("TRANSCRIPTION_PROVIDER", "whisper")).strip().lower()
    
    if selected not in _PROVIDER_CACHE:
        provider_cls = PROVIDER_REGISTRY.get(selected)
        if not provider_cls:
            valid_options = ", ".join(PROVIDER_REGISTRY.keys())
            raise InvalidProviderConfigError(
                f"Unsupported TRANSCRIPTION_PROVIDER: '{selected}'. Supported providers are: [{valid_options}]"
            )
        _PROVIDER_CACHE[selected] = provider_cls()
        logger.info(f"Initialized & Cached Transcription Provider: '{selected}'")

    return _PROVIDER_CACHE[selected]
