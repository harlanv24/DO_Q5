#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from client import SecureFileSharingClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a file using the client SDK.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite if filename exists")
    args = parser.parse_args()

    source = Path(args.file)
    with SecureFileSharingClient(base_url=args.base_url, user_id=args.user_id) as client:
        uploaded = client.upload_bytes(
            filename=source.name,
            content=source.read_bytes(),
            overwrite_if_exists=args.overwrite,
        )
    print(json.dumps(uploaded.__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()
