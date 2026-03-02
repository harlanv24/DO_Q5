from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.security import create_download_token


client = TestClient(app)


def test_download_rejects_malformed_token() -> None:
    res = client.get("/download", params={"token": "bad-token"})
    assert res.status_code == 401


def test_download_rejects_invalid_signature() -> None:
    token, _ = create_download_token(file_id="file-123", ttl_seconds=300)
    payload, signature = token.split(".", maxsplit=1)
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = f"{tampered_payload}.{signature}"

    res = client.get("/download", params={"token": tampered})
    assert res.status_code == 401


def test_download_returns_404_for_valid_token_with_missing_file() -> None:
    token, _ = create_download_token(file_id=f"missing-{uuid4().hex}", ttl_seconds=300)
    res = client.get("/download", params={"token": token})
    assert res.status_code == 404
