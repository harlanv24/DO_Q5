from app.security import create_download_token, verify_download_token


def test_sign_and_verify_token_roundtrip() -> None:
    token, exp = create_download_token(file_id="abc123", ttl_seconds=300)
    payload = verify_download_token(token)
    assert payload["file_id"] == "abc123"
    assert payload["exp"] == exp
