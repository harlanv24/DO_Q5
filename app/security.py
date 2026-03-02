import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw)


def create_download_token(file_id: str, ttl_seconds: int) -> tuple[str, int]:
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl_seconds)
    exp_epoch = int(expires_at.timestamp())
    # bake the TTL into the token so we don't need to query the database on download
    payload = {"file_id": file_id, "exp": exp_epoch}
    payload_b = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = _b64url_encode(payload_b)

    sig = hmac.new(
        settings.signing_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_part = _b64url_encode(sig)
    token = f"{payload_part}.{signature_part}"
    return token, exp_epoch


def verify_download_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    expected = hmac.new(
        settings.signing_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    received = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed expiration")
    if int(datetime.now(tz=timezone.utc).timestamp()) > exp:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link expired")
    return payload
