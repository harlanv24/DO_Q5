from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    user_id: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SignedUrlResponse(BaseModel):
    download_url: str
    expires_at_epoch: int
