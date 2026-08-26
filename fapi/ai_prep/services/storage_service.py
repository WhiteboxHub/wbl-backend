import abc
import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fapi.ai_prep.config import (
    LOCAL_STORAGE_DIR,
    SIGNED_URL_TTL_MINUTES,
)

logger = logging.getLogger("wbl.ai_prep.storage")


class StorageBackend(abc.ABC):
    """Abstract storage port for local server storage adapters."""

    @abc.abstractmethod
    def upload_bytes(self, storage_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload raw bytes to destination storage path and return the stored URI."""
        pass

    @abc.abstractmethod
    def download_to_file(self, storage_path: str, local_destination_path: str) -> str:
        """Download file from storage path to a local destination file path."""
        pass

    @abc.abstractmethod
    def read_bytes(self, storage_path: str) -> bytes:
        """Read and return raw bytes of stored object."""
        pass

    def download_bytes(self, storage_path: str) -> bytes:
        """Alias for read_bytes."""
        return self.read_bytes(storage_path)

    @abc.abstractmethod
    def delete_file(self, storage_path: str) -> bool:
        """Delete a single file at storage_path. Return True if deleted, False otherwise."""
        pass

    @abc.abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all files with the given path prefix. Return number of deleted files."""
        pass

    @abc.abstractmethod
    def file_exists(self, storage_path: str) -> bool:
        """Check if file exists at storage_path."""
        pass

    @abc.abstractmethod
    def list_files(self, prefix: str) -> List[str]:
        """List all storage paths matching the given prefix."""
        pass

    @abc.abstractmethod
    def generate_signed_url(self, storage_path: str, ttl_minutes: int = SIGNED_URL_TTL_MINUTES) -> str:
        """Generate a time-limited signed URL for accessing the file."""
        pass

    @abc.abstractmethod
    def get_absolute_local_path(self, storage_path: str) -> Optional[str]:
        """Returns absolute filesystem path if available locally, or None."""
        pass


# ----------------------------------------------------------------------
# Local Filesystem Adapter (Dedicated for AIPrep Zero-Cost Ingestion)
# ----------------------------------------------------------------------
class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str = LOCAL_STORAGE_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info("Initialized LocalStorageBackend with root at %s", self.base_dir)

    def _resolve_path(self, storage_path: str) -> str:
        # Sanitize and prevent directory traversal
        clean_path = storage_path.lstrip("/\\").replace("\\", "/")
        full_path = os.path.abspath(os.path.join(self.base_dir, clean_path))
        if not full_path.startswith(self.base_dir):
            raise ValueError(f"Invalid storage path traversal attempt: {storage_path}")
        return full_path

    def upload_bytes(self, storage_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        full_path = self._resolve_path(storage_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)
        logger.debug("Uploaded %d bytes to %s", len(data), storage_path)
        return storage_path

    def download_to_file(self, storage_path: str, local_destination_path: str) -> str:
        full_path = self._resolve_path(storage_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Storage object not found: {storage_path}")
        os.makedirs(os.path.dirname(os.path.abspath(local_destination_path)), exist_ok=True)
        shutil.copyfile(full_path, local_destination_path)
        return local_destination_path

    def read_bytes(self, storage_path: str) -> bytes:
        full_path = self._resolve_path(storage_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Storage object not found: {storage_path}")
        with open(full_path, "rb") as f:
            return f.read()

    def delete_file(self, storage_path: str) -> bool:
        full_path = self._resolve_path(storage_path)
        if os.path.isfile(full_path):
            os.remove(full_path)
            return True
        return False

    def delete_prefix(self, prefix: str) -> int:
        clean_prefix = prefix.lstrip("/\\").replace("\\", "/")
        target_dir = os.path.abspath(os.path.join(self.base_dir, clean_prefix))
        deleted_count = 0
        if os.path.isdir(target_dir):
            for root, _, files in os.walk(target_dir):
                deleted_count += len(files)
            shutil.rmtree(target_dir)
        elif os.path.isfile(target_dir):
            os.remove(target_dir)
            deleted_count = 1
        return deleted_count

    def file_exists(self, storage_path: str) -> bool:
        full_path = self._resolve_path(storage_path)
        return os.path.isfile(full_path)

    def list_files(self, prefix: str) -> List[str]:
        clean_prefix = prefix.lstrip("/\\").replace("\\", "/")
        target_dir = os.path.abspath(os.path.join(self.base_dir, clean_prefix))
        if not os.path.exists(target_dir):
            return []
        
        results = []
        if os.path.isfile(target_dir):
            rel_path = os.path.relpath(target_dir, self.base_dir).replace("\\", "/")
            return [rel_path]

        for root, _, files in os.walk(target_dir):
            for file in sorted(files):
                abs_f = os.path.join(root, file)
                rel_path = os.path.relpath(abs_f, self.base_dir).replace("\\", "/")
                results.append(rel_path)
        return results

    def generate_signed_url(self, storage_path: str, ttl_minutes: int = SIGNED_URL_TTL_MINUTES) -> str:
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        timestamp = int(expires_at.timestamp())
        return f"/api/ai-prep/media/local-stream?path={storage_path}&expires={timestamp}"

    def get_absolute_local_path(self, storage_path: str) -> Optional[str]:
        return self._resolve_path(storage_path)


# ----------------------------------------------------------------------
# Storage Service Factory
# ----------------------------------------------------------------------
_storage_instance: Optional[StorageBackend] = None


def get_storage_service() -> StorageBackend:
    """Singleton factory returning the active LocalStorageBackend instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LocalStorageBackend(base_dir=LOCAL_STORAGE_DIR)
    return _storage_instance
