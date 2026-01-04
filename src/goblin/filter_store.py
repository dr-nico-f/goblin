"""
Filter storage backed by DynamoDB (field-level friendly), with optional local fallback.

Env vars:
  - GOBLIN_FILTERS_TABLE (required for Dynamo usage)
  - GOBLIN_FILTERS_PK    (optional, default: "profile")
"""

import os
from typing import Optional

import boto3
import yaml
from botocore.exceptions import ClientError


class FilterStoreError(Exception):
    pass


def _table():
    name = os.environ.get("GOBLIN_FILTERS_TABLE")
    if not name:
        raise FilterStoreError("Missing env GOBLIN_FILTERS_TABLE.")
    return boto3.resource("dynamodb").Table(name)


def _pk_name() -> str:
    return os.environ.get("GOBLIN_FILTERS_PK", "profile")


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
    table = None
    try:
        table = _table()
        resp = table.get_item(Key={_pk_name(): profile})
        item = resp.get("Item") or {}
        data = item.get("filters") or {}
        return data if isinstance(data, dict) else {}
    except FilterStoreError:
        return _load_local(fallback_path)
    except ClientError:
        return _load_local(fallback_path)


def save_profile_filters(profile: str, data: dict, fallback_path: Optional[str] = None) -> None:
    try:
        table = _table()
    except FilterStoreError:
        _save_local(fallback_path, data)
        return

    try:
        table.put_item(Item={_pk_name(): profile, "filters": data})
    except ClientError as e:
        raise FilterStoreError(f"Failed to save filters: {e}") from e

