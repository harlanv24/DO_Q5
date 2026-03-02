from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import FileRecord
from app.security import verify_download_token

router = APIRouter(tags=["downloads"])


@router.get("/download")
def download_file(token: str = Query(...), db: Session = Depends(get_db)):
    payload = verify_download_token(token)
    file_id = payload.get("file_id")
    if not isinstance(file_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    row = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    path = Path(row.stored_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file missing")

    return FileResponse(
        path=path,
        media_type=row.content_type,
        filename=row.original_name,
    )
