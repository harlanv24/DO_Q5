import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import settings


def ensure_upload_root() -> Path:
    root = Path(settings.upload_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(user_id: str, upload: UploadFile) -> tuple[str, str, int]:
    root = ensure_upload_root()
    file_id = str(uuid4())
    safe_name = Path(upload.filename or "unnamed.bin").name

    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    stored_path = user_dir / file_id
    size = 0
    with stored_path.open("wb") as out:
        size = write_upload_stream(upload=upload, destination=out)
    return file_id, safe_name, size


def write_upload_stream(upload: UploadFile, destination) -> int:
    size = 0
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        destination.write(chunk)
        size += len(chunk)
    return size


def compute_upload_sha256(upload: UploadFile) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    upload.file.seek(0)
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    upload.file.seek(0)
    return digest.hexdigest(), size
