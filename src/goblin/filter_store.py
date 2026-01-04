"""
Filter storage backed by S3, with local fallback.

Env vars:
  - GOBLIN_FILTERS_BUCKET (required for S3 usage)
  - GOBLIN_FILTERS_PREFIX (optional, default: "filters")
"""

import os
from typing import Optional

import boto3
import yaml
from botocore.exceptions import ClientError


def _s3_key(profile: str, prefix: str) -> str:
    prefix = prefix.strip("/ ")
    return f"{prefix}/{profile}.yaml" if prefix else f"{profile}.yaml"


def _load_local(path: Optional[str]) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_local(path: Optional[str], data: dict) -> None:
    if not path:
        raise RuntimeError("No local path provided for saving filters.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def load_profile_filters(profile: str, fallback_path: Optional[str] = None) -> dict:
    bucket = os.environ.get("GOBLIN_FILTERS_BUCKET")
    prefix = os.environ.get("GOBLIN_FILTERS_PREFIX", "filters")
    if not bucket:
        return _load_local(fallback_path)

    key = _s3_key(profile, prefix)
    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj.get("Body").read().decode("utf-8")
        return yaml.safe_load(body) or {}
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return _load_local(fallback_path)
        raise


def save_profile_filters(profile: str, data: dict, fallback_path: Optional[str] = None) -> None:
    bucket = os.environ.get("GOBLIN_FILTERS_BUCKET")
    prefix = os.environ.get("GOBLIN_FILTERS_PREFIX", "filters")
    if not bucket:
        _save_local(fallback_path, data)
        return

    key = _s3_key(profile, prefix)
    s3 = boto3.client("s3")
    body = yaml.safe_dump(data, sort_keys=False)
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType="text/yaml")

