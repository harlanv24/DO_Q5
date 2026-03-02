# Secure File Sharing REST API (Python)

Minimal FastAPI skeleton for a secure file sharing service with private storage, signed download links, and audit events.

## Stack

- Python 3.12+
- FastAPI
- SQLite + SQLAlchemy
- Pytest

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment

Set these via `.env` (optional):

```env
APP_SIGNING_SECRET=replace-with-a-long-random-secret
APP_DATABASE_URL=sqlite:///./app.db
APP_UPLOAD_ROOT=./data/uploads
```

## Current Endpoints

- `GET /health`
- `POST /files` (multipart field: `upload`, header: `X-User-Id`, optional headers: `X-Overwrite-If-Exists: true`, `Idempotency-Key: <key>`)
- `GET /files` (header: `X-User-Id`)
- `GET /files/by-name?filename=<name>` (header: `X-User-Id`)
- `POST /files/sign-by-name?filename=<name>&ttl=300` (header: `X-User-Id`)
- `GET /download?token=...` (public)

## Python Client SDK

Client lives in `client/secure_file_client.py` and provides an external-facing interface:
- user-bound client instance (`user_id` is set once at construction),
- typed response objects,
- byte-based upload/download methods.

Example:

```python
from client import SecureFileSharingClient

with SecureFileSharingClient(base_url="http://127.0.0.1:8000", user_id="user-123") as client:
    uploaded = client.upload_bytes(
        filename="note.txt",
        content=b"hello",
        overwrite_if_exists=True,
        idempotency_key="upload-note-tx-001",
    )
    signed = client.create_signed_url_for_name(filename="note.txt", ttl_seconds=300)
    downloaded = client.download(signed.download_url)
    print(uploaded.original_name, downloaded.filename, downloaded.size_bytes)
```

## Demo Scripts (Client-Based)

Upload:

```bash
python scripts/demo_upload.py --user-id user-123 --file sample.txt --overwrite
```

Sign + download:

```bash
python scripts/demo_sign_download.py --user-id user-123 --filename sample.txt --out ./demo-output/file.txt
```

End-to-end:

```bash
python scripts/demo_e2e.py --user-id user-123 --file sample.txt --out ./demo-output/result.txt
```

## Design Decisions

- External interface is filename-based for customer ergonomics (`by-name` lookup and signing).
- Internal storage and token resolution use stable `file_id` values for robustness and audit integrity.
- Duplicate filename uploads return `409 Conflict` by default.
- Clients can opt into replacement by sending `X-Overwrite-If-Exists: true` on upload.
- Clients can make uploads retry-safe using `Idempotency-Key` (same key + same payload replays original result).
- Overwrites preserve `created_at`, update `updated_at`, and write an `OVERWRITTEN` audit event.
- Signed URLs are stateless (`file_id` + `exp` + HMAC signature) and remain valid across restarts.

## Test

```bash
pytest -q
```
