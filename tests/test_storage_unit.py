from io import BytesIO

from fastapi import UploadFile

from app.services.storage import compute_upload_sha256, write_upload_stream


def test_compute_upload_sha256_returns_digest_and_resets_pointer() -> None:
    raw = b"abc123" * 10
    upload = UploadFile(filename="hash.txt", file=BytesIO(raw))

    digest, size = compute_upload_sha256(upload)

    assert size == len(raw)
    assert len(digest) == 64
    # pointer reset lets the caller re-read the full stream.
    assert upload.file.read() == raw


def test_write_upload_stream_writes_all_bytes() -> None:
    raw = b"stream-content"
    upload = UploadFile(filename="stream.txt", file=BytesIO(raw))
    destination = BytesIO()

    written = write_upload_stream(upload=upload, destination=destination)

    assert written == len(raw)
    assert destination.getvalue() == raw
