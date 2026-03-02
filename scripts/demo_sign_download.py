#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from client import SecureFileSharingClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate signed URL and download file.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--ttl", type=int, default=300)
    parser.add_argument("--out", required=True, help="Output path for downloaded content")
    args = parser.parse_args()

    with SecureFileSharingClient(base_url=args.base_url, user_id=args.user_id) as client:
        signed = client.create_signed_url_for_name(
            filename=args.filename,
            ttl_seconds=args.ttl,
        )
        downloaded = client.download(signed.download_url)

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(downloaded.content)
    file_info = {
        "filename": downloaded.filename,
        "content_type": downloaded.content_type,
        "size_bytes": downloaded.size_bytes,
    }

    print(json.dumps(signed.__dict__, indent=2))
    print(json.dumps(file_info, indent=2))


if __name__ == "__main__":
    main()
