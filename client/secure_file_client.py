from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class SecureFileSharingError(RuntimeError):
    """Raised when the API returns an error response."""


@dataclass(frozen=True)
class HealthStatus:
    status: str


@dataclass(frozen=True)
class FileMetadata:
    user_id: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "FileMetadata":
        return FileMetadata(
            user_id=data["user_id"],
            original_name=data["original_name"],
            content_type=data["content_type"],
            size_bytes=data["size_bytes"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass(frozen=True)
class SignedDownloadLink:
    download_url: str
    expires_at_epoch: int

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SignedDownloadLink":
        return SignedDownloadLink(
            download_url=data["download_url"],
            expires_at_epoch=data["expires_at_epoch"],
        )


@dataclass(frozen=True)
class DownloadedFile:
    filename: str
    content_type: str
    content: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.content)


class SecureFileSharingClient:
    """
    External-facing SDK for a single authenticated user.

    The SDK hides transport details like auth headers and returns typed objects.
    """

    def __init__(self, base_url: str, user_id: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecureFileSharingClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"X-User-Id": self.user_id}

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail: Any
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise SecureFileSharingError(
                f"API request failed ({response.status_code}): {detail}"
            ) from exc

    @staticmethod
    def _download_path_from_url(download_url: str) -> str:
        parsed = urlparse(download_url)
        if parsed.scheme and parsed.netloc:
            return download_url
        if not download_url.startswith("/"):
            return "/" + download_url
        return download_url

    @staticmethod
    def _filename_from_response(response: httpx.Response) -> str:
        content_disposition = response.headers.get("content-disposition")
        if content_disposition:
            match = re.search(r'filename="([^"]+)"', content_disposition)
            if match:
                return Path(match.group(1)).name
        return "downloaded.bin"

    def health(self) -> HealthStatus:
        response = self._client.get("/health")
        self._raise_for_status(response)
        data = response.json()
        return HealthStatus(status=data.get("status", "unknown"))

    def upload_bytes(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        overwrite_if_exists: bool = False,
        idempotency_key: str | None = None,
    ) -> FileMetadata:
        headers = {
            **self._headers(),
            "X-Overwrite-If-Exists": str(overwrite_if_exists).lower(),
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = self._client.post(
            "/files",
            headers=headers,
            files={"upload": (filename, content, content_type)},
        )
        self._raise_for_status(response)
        return FileMetadata.from_dict(response.json())

    def upload_file(
        self,
        file_path: str | Path,
        content_type: str | None = None,
        overwrite_if_exists: bool = False,
        idempotency_key: str | None = None,
    ) -> FileMetadata:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        payload_content_type = content_type or "application/octet-stream"
        return self.upload_bytes(
            filename=path.name,
            content=path.read_bytes(),
            content_type=payload_content_type,
            overwrite_if_exists=overwrite_if_exists,
            idempotency_key=idempotency_key,
        )

    def list_files(self) -> list[FileMetadata]:
        response = self._client.get("/files", headers=self._headers())
        self._raise_for_status(response)
        return [FileMetadata.from_dict(item) for item in response.json()]

    def get_file(self, filename: str) -> FileMetadata:
        response = self._client.get(
            "/files/by-name",
            headers=self._headers(),
            params={"filename": filename},
        )
        self._raise_for_status(response)
        return FileMetadata.from_dict(response.json())

    def create_signed_url_for_name(
        self, filename: str, ttl_seconds: int = 300
    ) -> SignedDownloadLink:
        response = self._client.post(
            "/files/sign-by-name",
            headers=self._headers(),
            params={"filename": filename, "ttl": ttl_seconds},
        )
        self._raise_for_status(response)
        return SignedDownloadLink.from_dict(response.json())

    def download(self, download_url: str) -> DownloadedFile:
        request_path = self._download_path_from_url(download_url)
        response = self._client.get(request_path)
        self._raise_for_status(response)
        return DownloadedFile(
            filename=self._filename_from_response(response),
            content_type=response.headers.get("content-type", "application/octet-stream"),
            content=response.content,
        )
