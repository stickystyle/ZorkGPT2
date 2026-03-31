#!/usr/bin/env python3
"""Upload viewer/index.html to the S3 bucket.

Usage:
    python scripts/deploy_viewer.py <bucket-name> [--prefix PREFIX]
"""
import argparse
import sys
from pathlib import Path

import boto3


def main():
    parser = argparse.ArgumentParser(description="Deploy ZorkBurr viewer to S3")
    parser.add_argument("bucket", help="S3 bucket name")
    parser.add_argument("--prefix", default="", help="Key prefix (e.g. 'zorkburr/')")
    args = parser.parse_args()

    viewer_path = Path(__file__).parent.parent / "viewer" / "index.html"
    if not viewer_path.exists():
        print(f"Error: {viewer_path} not found", file=sys.stderr)
        sys.exit(1)

    s3 = boto3.client("s3")
    key = f"{args.prefix}index.html"

    print(f"Uploading {viewer_path} -> s3://{args.bucket}/{key}")
    s3.put_object(
        Bucket=args.bucket,
        Key=key,
        Body=viewer_path.read_bytes(),
        ContentType="text/html",
        CacheControl="public, max-age=300",
    )
    print("Done.")


if __name__ == "__main__":
    main()
