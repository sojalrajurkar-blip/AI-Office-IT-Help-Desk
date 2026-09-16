import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".txt", ".log", ".csv", ".docx", ".xlsx",
}


class StorageService:
    @staticmethod
    def get_upload_dir() -> str:
        base_dir = os.path.abspath(settings.LOCAL_STORAGE_DIR)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @classmethod
    async def save_file(cls, file: UploadFile) -> tuple[str, str, int, str]:
        """Saves an uploaded file safely and returns (file_name, file_path, file_size_bytes, content_type)."""
        original_name = file.filename or "evidence.bin"
        _, ext = os.path.splitext(original_name)
        ext = ext.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is not allowed. Supported extensions: {sorted(list(ALLOWED_EXTENSIONS))}",
            )

        # Generate unique storage filename
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        upload_dir = cls.get_upload_dir()
        file_path = os.path.join(upload_dir, stored_filename)

        size = 0
        async with aiofiles.open(file_path, "wb") as out_file:
            while chunk := await file.read(1024 * 64):  # 64 KB chunks
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    # Clean up file on size exceed
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
                    )
                await out_file.write(chunk)

        content_type = file.content_type or "application/octet-stream"
        return original_name, file_path, size, content_type
