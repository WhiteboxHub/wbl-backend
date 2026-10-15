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
from typing import Dict, Any, List, Optional, ClassVar, Tuple
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
        model_size: str = "distil-small.en",
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
        model_size: str = "distil-small.en",
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


class OpenAIWhisperProvider(BaseTranscriptionProvider):
    """
    Transcription provider using OpenAI's cloud Whisper API (whisper-1).
    Offloads heavy model execution from GCP container memory to OpenAI.
    Supports candidate-supplied API keys for zero-company cost.
    Compresses audio via FFmpeg to 64kbps MP3 to guarantee payload size is < 25 MB.
    """
    provider_name: ClassVar[str] = "openai"

    def __init__(self, default_api_key: Optional[str] = None):
        self.default_api_key = default_api_key

    @staticmethod
    def _compress_audio_for_openai(audio_path: str) -> Tuple[str, bool]:
        """
        Compresses large audio files or WAV files to lightweight MP3
        to guarantee staying far under OpenAI's 25 MB payload limit.
        Returns (compressed_path, is_temp).
        """
        import subprocess
        import tempfile

        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        ext = os.path.splitext(audio_path)[1].lower()

        # If already compressed and small, use directly
        if ext in {".mp3", ".opus", ".m4a"} and file_size_mb < 20.0:
            return audio_path, False

        temp_out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_out.close()

        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", "64k",
            "-ar", "16000",
            "-ac", "1",
            temp_out.name,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(temp_out.name) and os.path.getsize(temp_out.name) > 0:
                logger.info(
                    "Compressed audio for OpenAI Whisper: %s (%.1fMB) -> %s (%.1fMB)",
                    audio_path, file_size_mb, temp_out.name, os.path.getsize(temp_out.name) / (1024 * 1024)
                )
                return temp_out.name, True
            else:
                logger.warning("FFmpeg audio compression failed (rc=%s): %s", res.returncode, res.stderr[-200:])
        except Exception as exc:
            logger.warning("FFmpeg compression error: %s - using original file", exc)

        try:
            os.remove(temp_out.name)
        except OSError:
            pass
        return audio_path, False

    def transcribe(
        self,
        audio_path: Optional[str] = None,
        model_size: str = "whisper-1",
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if precomputed_transcript_text is not None and precomputed_word_timestamps is not None:
            logger.info("[OpenAIWhisperProvider] Reusing precomputed transcript & timestamps")
            return {
                "transcript_text": precomputed_transcript_text,
                "word_timestamps": precomputed_word_timestamps,
                "duration": kwargs.get("duration", 0.0),
            }

        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError(f"OpenAIWhisperProvider requires a valid audio_path. Given: {audio_path}")

        api_key = kwargs.get("openai_api_key") or kwargs.get("api_key") or self.default_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise TranscriptionProviderError(
                "OpenAI API key is required for OpenAI Whisper transcription. "
                "Please provide candidate's OpenAI API key."
            )

        from openai import OpenAI
        from .quality_checker import validate_transcript_quality

        target_file, is_temp = self._compress_audio_for_openai(audio_path)

        technical_prompt = (
            "The candidate is answering technical interview questions on software engineering, system design, "
            "Generative AI, RAG, and Agentic AI systems. "
            "Technical vocabulary: FastAPI, Milvus, LangChain, LangGraph, ArgoCD, Kubernetes, MLOps, AWS Bedrock, "
            "Claude Sonnet, Docling, Terraform, microservices, PyTorch, SageMaker, Lambda, S3, ECS, CI/CD, "
            "sentence transformers, vector database, supervisor pattern, MCP, Model Context Protocol, Prometheus, Grafana."
        )

        try:
            client = OpenAI(api_key=api_key)
            with open(target_file, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                    prompt=technical_prompt,
                    language="en",
                )

            full_text = getattr(response, "text", "") or ""
            duration = getattr(response, "duration", 0.0) or 0.0

            word_timestamps: List[Dict[str, Any]] = []
            raw_words = getattr(response, "words", None)
            if raw_words:
                for w in raw_words:
                    word_str = getattr(w, "word", "") or ""
                    if word_str.strip():
                        word_timestamps.append({
                            "word": word_str.strip(),
                            "start": round(float(getattr(w, "start", 0.0)), 2),
                            "end": round(float(getattr(w, "end", 0.0)), 2),
                        })

            # Quality audit
            audit = validate_transcript_quality(full_text, duration, word_timestamps)
            if not audit["passed"]:
                logger.info("Quality checker audit for OpenAI Whisper: %s", audit["warnings"])

            return {
                "transcript_text": audit["cleaned_text"],
                "word_timestamps": word_timestamps,
                "duration": round(float(duration), 2),
                "quality_audit": audit,
            }
        except Exception as exc:
            logger.error("[OpenAIWhisperProvider] Transcription failed: %s", exc, exc_info=True)
            raise TranscriptionProviderError(f"OpenAI Whisper transcription failed: {str(exc)}") from exc
        finally:
            if is_temp and os.path.exists(target_file):
                try:
                    os.remove(target_file)
                except OSError:
                    pass


# Registry of supported providers
PROVIDER_REGISTRY = {
    "whisper": WhisperTranscriptionProvider,
    "openai": OpenAIWhisperProvider,
    "openai_whisper": OpenAIWhisperProvider,
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
