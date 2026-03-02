from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_idempotency_replays_original_response() -> None:
    filename = f"idem-{uuid4().hex}.txt"
    key = f"key-{uuid4().hex}"
    headers = {"X-User-Id": "idem-user", "Idempotency-Key": key}

    res1 = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"hello world", "text/plain")},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"hello world", "text/plain")},
    )
    assert res2.status_code == 201
    assert res2.json() == res1.json()


def test_upload_idempotency_rejects_different_payload_for_same_key() -> None:
    filename = f"idem-{uuid4().hex}.txt"
    key = f"key-{uuid4().hex}"
    headers = {"X-User-Id": "idem-user", "Idempotency-Key": key}

    res1 = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"original-content", "text/plain")},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"different-content", "text/plain")},
    )
    assert res2.status_code == 409
    assert "Idempotency-Key" in res2.json()["detail"]


def test_upload_without_key_after_idempotent_replay_returns_conflict() -> None:
    filename = f"idem-{uuid4().hex}.txt"
    key = f"key-{uuid4().hex}"
    headers = {"X-User-Id": "idem-user", "Idempotency-Key": key}

    first = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"seed-content", "text/plain")},
    )
    assert first.status_code == 201

    replay = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"seed-content", "text/plain")},
    )
    assert replay.status_code == 201
    assert replay.json() == first.json()

    no_key_retry = client.post(
        "/files",
        headers={"X-User-Id": "idem-user"},
        files={"upload": (filename, b"seed-content", "text/plain")},
    )
    assert no_key_retry.status_code == 409
    assert "X-Overwrite-If-Exists" in no_key_retry.json()["detail"]


def test_upload_without_key_can_overwrite_after_idempotent_replay() -> None:
    filename = f"idem-{uuid4().hex}.txt"
    key = f"key-{uuid4().hex}"
    headers = {"X-User-Id": "idem-user", "Idempotency-Key": key}

    first = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"seed-content", "text/plain")},
    )
    assert first.status_code == 201

    replay = client.post(
        "/files",
        headers=headers,
        files={"upload": (filename, b"seed-content", "text/plain")},
    )
    assert replay.status_code == 201
    assert replay.json() == first.json()

    overwrite = client.post(
        "/files",
        headers={"X-User-Id": "idem-user", "X-Overwrite-If-Exists": "true"},
        files={"upload": (filename, b"new-overwrite-content", "text/plain")},
    )
    assert overwrite.status_code == 201
    assert overwrite.json()["original_name"] == filename
    assert overwrite.json()["size_bytes"] == len(b"new-overwrite-content")
