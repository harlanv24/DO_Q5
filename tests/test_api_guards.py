from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_protected_endpoints_require_user_header() -> None:
    filename = f"guard-{uuid4().hex}.txt"

    list_res = client.get("/files")
    assert list_res.status_code == 401

    by_name_res = client.get("/files/by-name", params={"filename": filename})
    assert by_name_res.status_code == 401

    sign_res = client.post("/files/sign-by-name", params={"filename": filename, "ttl": 300})
    assert sign_res.status_code == 401

    upload_res = client.post(
        "/files",
        files={"upload": (filename, b"hello", "text/plain")},
    )
    assert upload_res.status_code == 401


def test_sign_by_name_ttl_bounds_are_enforced() -> None:
    user_id = f"user-{uuid4().hex[:8]}"
    filename = f"ttl-{uuid4().hex}.txt"
    upload = client.post(
        "/files",
        headers={"X-User-Id": user_id},
        files={"upload": (filename, b"ttl-content", "text/plain")},
    )
    assert upload.status_code == 201

    too_small = client.post(
        "/files/sign-by-name",
        headers={"X-User-Id": user_id},
        params={"filename": filename, "ttl": 59},
    )
    assert too_small.status_code == 422

    too_large = client.post(
        "/files/sign-by-name",
        headers={"X-User-Id": user_id},
        params={"filename": filename, "ttl": 86401},
    )
    assert too_large.status_code == 422


def test_cross_user_isolation_for_by_name_and_signing() -> None:
    owner = f"user-{uuid4().hex[:8]}"
    other = f"user-{uuid4().hex[:8]}"
    filename = f"isolation-{uuid4().hex}.txt"

    upload = client.post(
        "/files",
        headers={"X-User-Id": owner},
        files={"upload": (filename, b"secret-data", "text/plain")},
    )
    assert upload.status_code == 201

    other_lookup = client.get(
        "/files/by-name",
        headers={"X-User-Id": other},
        params={"filename": filename},
    )
    assert other_lookup.status_code == 404

    other_sign = client.post(
        "/files/sign-by-name",
        headers={"X-User-Id": other},
        params={"filename": filename, "ttl": 300},
    )
    assert other_sign.status_code == 404
