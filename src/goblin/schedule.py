"""
EventBridge schedule helpers.

Env vars:
  - GOBLIN_SCHEDULE_RULE (rule name to manage)
"""

import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError


class ScheduleError(Exception):
    pass


def _rule_name(rule: Optional[str]) -> str:
    name = rule or os.environ.get("GOBLIN_SCHEDULE_RULE")
    if not name:
        raise ScheduleError("Missing schedule rule name (GOBLIN_SCHEDULE_RULE).")
    return name


def _normalize_cron(expr: str) -> str:
    expr = expr.strip()
    if expr.startswith("cron("):
        return expr
    fields = expr.split()
    if len(fields) not in (5, 6):
        raise ScheduleError("Cron expression must have 5 or 6 fields or start with cron(...).")
    return f"cron({expr})"


def get_schedule(rule_name: Optional[str] = None) -> str:
    name = _rule_name(rule_name)
    events = boto3.client("events")
    resp = events.describe_rule(Name=name)
    return resp.get("ScheduleExpression", "")


def set_schedule(expr: str, rule_name: Optional[str] = None) -> str:
    name = _rule_name(rule_name)
    norm = _normalize_cron(expr)
    events = boto3.client("events")
    try:
        events.put_rule(Name=name, ScheduleExpression=norm)
    except ClientError as e:
        raise ScheduleError(f"Failed to update schedule: {e}") from e
    return norm

