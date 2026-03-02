from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_demo_e2e_flow_upload_sign_and_download() -> None:
    user_id = f"user-{uuid4().hex[:8]}"
    filename = f"demo-{uuid4().hex}.txt"
    original = b"hello from integration flow"

    upload = client.post(
        "/files",
        headers={"X-User-Id": user_id},
        files={"upload": (filename, original, "text/plain")},
    )
    assert upload.status_code == 201
    assert upload.json()["original_name"] == filename

    signed = client.post(
        "/files/sign-by-name",
        headers={"X-User-Id": user_id},
        params={"filename": filename, "ttl": 300},
    )
    assert signed.status_code == 200
    download_url = signed.json()["download_url"]
    assert download_url.startswith("/download?token=")

    download = client.get(download_url)
    assert download.status_code == 200
    assert download.content == original


def test_demo_flow_overwrite_then_downloads_latest_content() -> None:
    user_id = f"user-{uuid4().hex[:8]}"
    filename = f"demo-{uuid4().hex}.txt"
    first = b"old-content"
    second = b"new-content-after-overwrite"

    first_upload = client.post(
        "/files",
        headers={"X-User-Id": user_id},
        files={"upload": (filename, first, "text/plain")},
    )
    assert first_upload.status_code == 201

    overwrite = client.post(
        "/files",
        headers={"X-User-Id": user_id, "X-Overwrite-If-Exists": "true"},
        files={"upload": (filename, second, "text/plain")},
    )
    assert overwrite.status_code == 201
    assert overwrite.json()["size_bytes"] == len(second)

    signed = client.post(
        "/files/sign-by-name",
        headers={"X-User-Id": user_id},
        params={"filename": filename, "ttl": 300},
    )
    assert signed.status_code == 200

    downloaded = client.get(signed.json()["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content == second
