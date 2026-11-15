import hashlib
import io
import os
from pathlib import Path
import re
from typing import BinaryIO, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import FinTrustBaseException


class FileValidationError(FinTrustBaseException):
    """Raised when file validation (extension, MIME, magic bytes, size) fails."""
    pass


class DuplicateDocumentError(FinTrustBaseException):
    """Raised when a document with identical content hash already exists for the tenant."""
    pass


class FileValidationService:
    """Enterprise file validation: MIME, extensions, magic bytes, size limits, and sanitization."""

    MAGIC_BYTES = {
        "pdf": b"%PDF-",
        "docx": b"PK\x03\x04",
    }

    # Executable or script extensions that must never precede allowed extensions (e.g. file.exe.pdf)
    DANGEROUS_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".sh", ".py", ".js", ".vbs", ".ps1", ".msi", ".dll", ".so", ".bin"
    }

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Strips dangerous characters, separators, and path traversal sequences from user filenames."""
        # Normalize separators
        clean_name = filename.replace("\\", "/").strip()
        clean_name = os.path.basename(clean_name)
        
        # Remove any null bytes or non-printable characters
        clean_name = re.sub(r"[^\w\s\.-]", "_", clean_name)
        
        # Prevent hidden files
        clean_name = clean_name.lstrip(".")
        
        # Defend against double extension tricks (e.g., invoice.exe.pdf)
        parts = clean_name.split(".")
        if len(parts) > 2:
            for part in parts[1:-1]:
                if f".{part.lower()}" in cls.DANGEROUS_EXTENSIONS:
                    raise FileValidationError(f"Dangerous file extension pattern detected: '.{part}'")

        return clean_name or "uploaded_document"

    @classmethod
    def validate_file(
        cls,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> Tuple[str, str, int, str]:
        """Validates file constraints: extension, MIME type, magic bytes, and size.
        
        Returns:
            Tuple of (sanitized_filename, validated_mime, file_size, content_hash)
        """
        file_size = len(file_bytes)
        if file_size == 0:
            raise FileValidationError("Uploaded file is empty (0 bytes).")

        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise FileValidationError(
                f"File size ({actual_mb:.1f} MB) exceeds maximum allowed limit ({max_mb} MB)."
            )

        sanitized_name = cls.sanitize_filename(filename)
        suffix = Path(sanitized_name).suffix.lower()

        if suffix not in settings.ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file extension '{suffix}'. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )

        # Magic bytes and content integrity verification
        if suffix == ".pdf":
            if not file_bytes.startswith(cls.MAGIC_BYTES["pdf"]):
                raise FileValidationError("File corrupt or invalid: missing valid PDF signature (%PDF-).")
            validated_mime = "application/pdf"
        elif suffix == ".docx":
            if not file_bytes.startswith(cls.MAGIC_BYTES["docx"]):
                raise FileValidationError("File corrupt or invalid: missing valid DOCX (PK) zip signature.")
            validated_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif suffix in [".txt", ".md"]:
            # Check for binary null bytes indicative of non-text file
            null_count = file_bytes[:1024].count(b"\x00")
            if null_count > 0:
                raise FileValidationError("Text/Markdown file contains invalid binary content.")
            try:
                file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise FileValidationError("Text file is not valid UTF-8 encoded text.")
            validated_mime = "text/plain" if suffix == ".txt" else "text/markdown"
        else:
            raise FileValidationError(f"Unhandled file type for extension: {suffix}")

        content_hash = hashlib.sha256(file_bytes).hexdigest()

        return sanitized_name, validated_mime, file_size, content_hash
