import logging
import os
from pathlib import Path
from typing import Optional
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages tenant-isolated physical document file storage on disk."""

    def __init__(self, base_dir: str = settings.DOCUMENT_STORAGE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        tenant_id: uuid.UUID,
        content_hash: str,
        extension: str,
        file_bytes: bytes
    ) -> Path:
        """Saves file into a tenant-isolated subdirectory using content hash and extension."""
        tenant_dir = self.base_dir / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)

        ext = extension if extension.startswith(".") else f".{extension}"
        target_path = tenant_dir / f"{content_hash}{ext}"

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        return target_path

    def get_file_path(
        self,
        tenant_id: uuid.UUID,
        content_hash: str,
        extension: str
    ) -> Optional[Path]:
        """Resolves physical file path if it exists on disk."""
        ext = extension if extension.startswith(".") else f".{extension}"
        target_path = self.base_dir / str(tenant_id) / f"{content_hash}{ext}"
        if target_path.exists():
            return target_path
        return None

    def delete_file(self, file_path_str: str) -> bool:
        """Safely deletes document file from disk if present."""
        try:
            path = Path(file_path_str)
            if path.exists() and path.is_file():
                path.unlink()
                return True
        except Exception as e:
            logger.warning(f"Failed to delete stored file {file_path_str}: {e}")
        return False
