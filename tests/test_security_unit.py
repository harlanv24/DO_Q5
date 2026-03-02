from fastapi import HTTPException

from app.security import create_download_token, verify_download_token


def test_verify_download_token_rejects_invalid_format() -> None:
    try:
        verify_download_token("not-a-valid-token")
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "Invalid token" in str(exc.detail)


def test_verify_download_token_rejects_tampered_signature() -> None:
    token, _ = create_download_token(file_id="unit-file", ttl_seconds=300)
    payload, signature = token.split(".", maxsplit=1)
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = f"{tampered_payload}.{signature}"
    try:
        verify_download_token(tampered)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "Invalid signature" in str(exc.detail)


def test_verify_download_token_rejects_expired_token() -> None:
    token, _ = create_download_token(file_id="unit-file", ttl_seconds=-1)
    try:
        verify_download_token(token)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 410
        assert "expired" in str(exc.detail).lower()
