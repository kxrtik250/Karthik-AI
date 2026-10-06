import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional, Set, Tuple
from fastapi import UploadFile

from app.config import settings

# Supported extensions and MIME types
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".txt": "txt",
    ".md": "md",
}

MIME_TYPE_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
}


class StorageService:
    def __init__(self, upload_dir: str = settings.upload_dir):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = settings.max_file_size_mb * 1024 * 1024

    def validate_file_type(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate if the file extension is supported. Returns (is_valid, normalized_file_type)."""
        suffix = Path(filename).suffix.lower()
        if suffix in SUPPORTED_EXTENSIONS:
            return True, SUPPORTED_EXTENSIONS[suffix]
        return False, None

    async def save_upload_file(self, file: UploadFile) -> Tuple[str, str, int, str]:
        """
        Reads, calculates SHA-256 checksum, checks size limit, and saves to disk.
        Returns: (saved_filename, saved_file_path, file_size, checksum_hex)
        """
        hasher = hashlib.sha256()
        total_size = 0
        chunks = []

        while True:
            chunk = await file.read(1024 * 1024)  # 1MB buffer
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > self.max_bytes:
                raise ValueError(
                    f"File size exceeds maximum allowed size of {settings.max_file_size_mb} MB"
                )
            hasher.update(chunk)
            chunks.append(chunk)

        checksum = hasher.hexdigest()

        # Generate unique storage filename
        suffix = Path(file.filename or "file").suffix.lower()
        unique_name = f"{uuid.uuid4()}{suffix}"
        dest_path = self.upload_dir / unique_name

        with open(dest_path, "wb") as f:
            for chunk in chunks:
                f.write(chunk)

        # Reset upload file cursor
        await file.seek(0)

        return unique_name, str(dest_path), total_size, checksum

    def delete_file(self, file_path: str) -> bool:
        """Removes the file from local disk if it exists."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
        except Exception:
            pass
        return False


storage_service = StorageService()
