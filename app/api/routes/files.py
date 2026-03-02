from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, require_user_id
from app.models import AuditAction, AuditEvent, FileRecord, IdempotencyRecord
from app.schemas import FileMetadata, SignedUrlResponse
from app.security import create_download_token
from app.services.storage import compute_upload_sha256, save_upload, write_upload_stream

router = APIRouter(prefix="/files", tags=["files"])


def _get_replayed_upload_result(
    db: Session, user_id: str, idempotency_key: str, request_hash: str
) -> FileRecord:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == "POST /files",
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency conflict detected")
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key was already used with a different upload payload",
        )
    replay_row = db.scalar(
        select(FileRecord).where(
            FileRecord.id == record.file_id,
            FileRecord.user_id == user_id,
        )
    )
    if not replay_row:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Original idempotent upload result is no longer available",
        )
    return replay_row


@router.post("", response_model=FileMetadata, status_code=status.HTTP_201_CREATED)
def upload_file(
    upload: UploadFile = File(...),
    overwrite_if_exists: bool = Header(default=False, alias="X-Overwrite-If-Exists"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    existing_idempotency: IdempotencyRecord | None = None
    request_hash: str | None = None
    if idempotency_key:
        content_type = upload.content_type or "application/octet-stream"
        digest, content_size = compute_upload_sha256(upload)
        request_fingerprint = {
            "filename": upload.filename,
            "content_type": content_type,
            "overwrite_if_exists": overwrite_if_exists,
            "sha256": digest,
            "size_bytes": content_size,
        }
        request_hash = hashlib.sha256(
            json.dumps(request_fingerprint, sort_keys=True).encode("utf-8")
        ).hexdigest()
        existing_idempotency = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.operation == "POST /files",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if existing_idempotency:
            replay_row = _get_replayed_upload_result(
                db=db,
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            return replay_row

    existing = db.scalar(
        select(FileRecord).where(
            FileRecord.user_id == user_id,
            FileRecord.original_name == upload.filename,
        )
    )
    if existing and not overwrite_if_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A file with this name already exists for this user. "
                "Set header X-Overwrite-If-Exists: true to overwrite."
            ),
        )

    if existing and overwrite_if_exists:
        stored_path = Path(existing.stored_path)
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        with stored_path.open("wb") as out:
            size = write_upload_stream(upload=upload, destination=out)
        existing.content_type = upload.content_type or "application/octet-stream"
        existing.size_bytes = size
        existing.updated_at = datetime.now(timezone.utc)
        db.add(
            AuditEvent(
                user_id=user_id,
                file_id=existing.id,
                action=AuditAction.OVERWRITTEN,
                ttl_seconds=0,
            )
        )
        if idempotency_key and request_hash:
            db.add(
                IdempotencyRecord(
                    user_id=user_id,
                    operation="POST /files",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    file_id=existing.id,
                )
            )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if idempotency_key and request_hash:
                return _get_replayed_upload_result(
                    db=db,
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
            raise
        db.refresh(existing)
        return existing

    file_id, safe_name, size = save_upload(user_id=user_id, upload=upload)
    record = FileRecord(
        id=file_id,
        user_id=user_id,
        original_name=safe_name,
        content_type=upload.content_type or "application/octet-stream", # generic raw binary as fallback type
        size_bytes=size,
        stored_path=f"{settings.upload_root}/{user_id}/{file_id}",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    if idempotency_key and request_hash:
        db.add(
            IdempotencyRecord(
                user_id=user_id,
                operation="POST /files",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                file_id=record.id,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and request_hash:
            return _get_replayed_upload_result(
                db=db,
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        raise
    db.refresh(record)
    return record


@router.get("", response_model=list[FileMetadata])
def list_files(user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(FileRecord).where(FileRecord.user_id == user_id)).all()
    return rows


@router.get("/by-name", response_model=FileMetadata)
def get_file_by_name(
    filename: str = Query(..., min_length=1, description="Original filename"),
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(FileRecord).where(FileRecord.original_name == filename, FileRecord.user_id == user_id)
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return row


@router.post("/sign-by-name", response_model=SignedUrlResponse)
def sign_download_link_by_name(
    filename: str = Query(..., min_length=1, description="Original filename"),
    ttl: int = Query(default=300, description="TTL in seconds"),
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    if ttl < settings.min_ttl_seconds or ttl > settings.max_ttl_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"ttl must be between {settings.min_ttl_seconds} and {settings.max_ttl_seconds}",
        )

    row = db.scalar(
        select(FileRecord).where(
            FileRecord.user_id == user_id,
            FileRecord.original_name == filename,
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    token, exp = create_download_token(file_id=row.id, ttl_seconds=ttl)
    db.add(
        AuditEvent(
            user_id=user_id,
            file_id=row.id,
            action=AuditAction.LINK_GENERATED,
            ttl_seconds=ttl,
        )
    )
    db.commit()
    return SignedUrlResponse(download_url=f"/download?token={token}", expires_at_epoch=exp)
