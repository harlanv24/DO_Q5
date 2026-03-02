#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from client import SecureFileSharingClient


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end demo using the Python client.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", default="demo-user")
    parser.add_argument("--file", required=True)
    parser.add_argument("--ttl", type=int, default=300)
    parser.add_argument("--out", default="./demo-output/downloaded.bin")
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        raise FileNotFoundError(f"Input file does not exist: {source}")

    with SecureFileSharingClient(base_url=args.base_url, user_id=args.user_id) as client:
        upload = client.upload_bytes(
            filename=source.name,
            content=source.read_bytes(),
        )
        signed = client.create_signed_url_for_name(
            filename=upload.original_name,
            ttl_seconds=args.ttl,
        )
        downloaded_file = client.download(signed.download_url)

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(downloaded_file.content)

    result = {
        "uploaded_filename": upload.original_name,
        "signed_url": signed.download_url,
        "downloaded_file": {
            "filename": downloaded_file.filename,
            "content_type": downloaded_file.content_type,
            "size_bytes": downloaded_file.size_bytes,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
