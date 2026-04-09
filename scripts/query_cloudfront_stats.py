#!/usr/bin/env python3
"""Dump raw CloudFront access logs + CloudWatch metrics for the viewer distribution.

Writes three files to --out-dir (default data/cloudfront/):
  - requests-<from>-to-<to>.jsonl : one JSON object per request, fields named per
    CloudFront's '#Fields:' header (e.g. 'c-ip', 'cs(Referer)', 'x-edge-location').
  - metrics-<from>-to-<to>.json   : hourly CloudWatch aggregates (Requests,
    BytesDownloaded, 4xx/5xx/TotalErrorRate).
  - manifest.json                 : window, sources, counts, output filenames.

No aggregation — raw data so downstream questions can be answered without
re-querying AWS.

Usage:
    uv run --extra s3 scripts/query_cloudfront_stats.py [--days 7]
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

DISTRIBUTION_ID = "E206ZNKA20ZUPT"
LOGS_PREFIX = "cf-logs/"
CLOUDFRONT_METRIC_REGION = "us-east-1"  # CloudFront metrics always live here
DEFAULT_OUT_DIR = Path(__file__).parent.parent / "data" / "cloudfront"

# CloudFront log fields that are integer-valued when not '-'
INT_FIELDS = {
    "sc-bytes",
    "sc-status",
    "cs-bytes",
    "c-port",
    "sc-content-len",
    "sc-range-start",
    "sc-range-end",
}
# Float-valued fields
FLOAT_FIELDS = {"time-taken", "time-to-first-byte"}


def resolve_logs_bucket(override: str | None) -> str:
    if override:
        return override
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    return f"zorkgpt-access-logs-{account_id}"


def list_log_objects(s3, bucket: str, since: datetime) -> list[dict]:
    paginator = s3.get_paginator("list_objects_v2")
    objects: list[dict] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=LOGS_PREFIX):
        for obj in page.get("Contents", []):
            if obj["LastModified"] >= since:
                objects.append(obj)
    return objects


def parse_log_body(body: bytes) -> tuple[list[str], list[list[str]]]:
    """Return (field_names, rows). Handles the '#Version:' / '#Fields:' header."""
    text = gzip.decompress(body).decode("utf-8", errors="replace")
    fields: list[str] = []
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("#Fields:"):
            fields = line[len("#Fields:") :].strip().split()
            continue
        if line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return fields, rows


def coerce(field: str, value: str):
    if value == "-" or value == "":
        return None
    if field in INT_FIELDS:
        try:
            return int(value)
        except ValueError:
            return value
    if field in FLOAT_FIELDS:
        try:
            return float(value)
        except ValueError:
            return value
    return value


def row_to_record(fields: list[str], row: list[str]) -> dict:
    rec: dict = {}
    date_val = time_val = None
    for name, raw in zip(fields, row):
        if name == "date":
            date_val = raw
            continue
        if name == "time":
            time_val = raw
            continue
        rec[name] = coerce(name, raw)
    if date_val and time_val:
        # CloudFront logs are always UTC
        try:
            ts = datetime.strptime(f"{date_val} {time_val}", "%Y-%m-%d %H:%M:%S")
            rec["timestamp"] = ts.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            rec["timestamp"] = f"{date_val}T{time_val}Z"
    return rec


def download_and_parse(s3, bucket: str, key: str) -> list[dict]:
    resp = s3.get_object(Bucket=bucket, Key=key)
    body = resp["Body"].read()
    fields, rows = parse_log_body(body)
    return [row_to_record(fields, r) for r in rows]


def fetch_cloudwatch_metrics(distribution_id: str, start: datetime, end: datetime) -> dict:
    cw = boto3.client("cloudwatch", region_name=CLOUDFRONT_METRIC_REGION)
    dims = [
        {"Name": "DistributionId", "Value": distribution_id},
        {"Name": "Region", "Value": "Global"},
    ]
    metric_specs = [
        ("Requests", "Sum"),
        ("BytesDownloaded", "Sum"),
        ("BytesUploaded", "Sum"),
        ("4xxErrorRate", "Average"),
        ("5xxErrorRate", "Average"),
        ("TotalErrorRate", "Average"),
    ]
    queries = [
        {
            "Id": f"m{i}",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/CloudFront",
                    "MetricName": name,
                    "Dimensions": dims,
                },
                "Period": 3600,
                "Stat": stat,
            },
            "ReturnData": True,
        }
        for i, (name, stat) in enumerate(metric_specs)
    ]

    results: dict = {}
    next_token = None
    while True:
        kwargs = dict(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending",
        )
        if next_token:
            kwargs["NextToken"] = next_token
        resp = cw.get_metric_data(**kwargs)
        for r in resp["MetricDataResults"]:
            idx = int(r["Id"][1:])
            name, stat = metric_specs[idx]
            bucket = results.setdefault(
                name, {"stat": stat, "timestamps": [], "values": []}
            )
            bucket["timestamps"].extend(t.isoformat() for t in r["Timestamps"])
            bucket["values"].extend(r["Values"])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default 7)")
    parser.add_argument("--distribution-id", default=DISTRIBUTION_ID)
    parser.add_argument("--logs-bucket", default=None, help="Override logs bucket (default: zorkgpt-access-logs-<acct>)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--exclude-ip",
        action="append",
        default=[],
        help="Client IP to drop from requests_jsonl (may be repeated)",
    )
    args = parser.parse_args()
    excluded_ips = set(args.exclude_ip)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=args.days)
    window_tag = f"{since.strftime('%Y%m%dT%H%M')}Z-to-{now.strftime('%Y%m%dT%H%M')}Z"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    requests_path = args.out_dir / f"requests-{window_tag}.jsonl"
    metrics_path = args.out_dir / f"metrics-{window_tag}.json"
    manifest_path = args.out_dir / "manifest.json"

    logs_bucket = resolve_logs_bucket(args.logs_bucket)
    print(f"Logs bucket: {logs_bucket}", file=sys.stderr)
    print(f"Window: {since.isoformat()} .. {now.isoformat()}", file=sys.stderr)

    s3 = boto3.client("s3")
    objects = list_log_objects(s3, logs_bucket, since)
    print(f"Log objects in window: {len(objects)}", file=sys.stderr)

    request_count = 0
    excluded_count = 0
    with requests_path.open("w") as fh:
        for i, obj in enumerate(objects, 1):
            key = obj["Key"]
            try:
                records = download_and_parse(s3, logs_bucket, key)
            except Exception as e:
                print(f"  [skip] {key}: {e}", file=sys.stderr)
                continue
            for rec in records:
                if rec.get("c-ip") in excluded_ips:
                    excluded_count += 1
                    continue
                fh.write(json.dumps(rec, separators=(",", ":")))
                fh.write("\n")
                request_count += 1
            if i % 25 == 0 or i == len(objects):
                print(
                    f"  parsed {i}/{len(objects)} objects, {request_count} kept, {excluded_count} excluded",
                    file=sys.stderr,
                )

    print(f"Wrote {request_count} request records -> {requests_path}", file=sys.stderr)

    print("Fetching CloudWatch metrics...", file=sys.stderr)
    metrics = fetch_cloudwatch_metrics(args.distribution_id, since, now)
    metrics_path.write_text(
        json.dumps(
            {
                "distribution_id": args.distribution_id,
                "start": since.isoformat(),
                "end": now.isoformat(),
                "period_seconds": 3600,
                "metrics": metrics,
            },
            indent=2,
        )
    )
    print(f"Wrote metrics -> {metrics_path}", file=sys.stderr)

    manifest = {
        "generated_at": now.isoformat(),
        "window_start": since.isoformat(),
        "window_end": now.isoformat(),
        "distribution_id": args.distribution_id,
        "logs_bucket": logs_bucket,
        "logs_prefix": LOGS_PREFIX,
        "log_objects_fetched": len(objects),
        "request_count": request_count,
        "excluded_ips": sorted(excluded_ips),
        "excluded_request_count": excluded_count,
        "files": {
            "requests_jsonl": str(requests_path.relative_to(args.out_dir.parent.parent) if args.out_dir.is_absolute() else requests_path),
            "metrics_json": str(metrics_path.relative_to(args.out_dir.parent.parent) if args.out_dir.is_absolute() else metrics_path),
        },
        "notes": (
            "requests_jsonl uses CloudFront log field names verbatim (e.g. 'c-ip', "
            "'cs(Referer)', 'x-edge-location', 'sc-status', 'cs-uri-stem'). "
            "'timestamp' is a synthesized ISO-8601 UTC combining 'date'+'time'. "
            "'x-edge-location' is the edge POP (geographic proxy); 'c-ip' is the raw "
            "client IP preserved for optional IP->geo enrichment later."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote manifest -> {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
