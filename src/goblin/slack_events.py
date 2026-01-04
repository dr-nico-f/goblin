"""
Slack Events / Slash Command handler (Lambda-friendly).

Expects:
  - Environment variables:
      SLACK_SIGNING_SECRET : Slack app signing secret
      GOBLIN_SLACK_BOT_TOKEN: already used elsewhere for posting (not required for responses here)
  - API Gateway / Lambda proxy integration providing headers + raw body.

Current supported commands (extend in commands.py):
  - help
  - status [--profile nick]
  - filters salary [--profile nick]
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse

from goblin.commands import handle_command


def _verify_signature(headers: dict, body: str, signing_secret: str) -> bool:
    ts = headers.get("X-Slack-Request-Timestamp") or headers.get("x-slack-request-timestamp")
    sig = headers.get("X-Slack-Signature") or headers.get("x-slack-signature")
    if not (ts and sig):
        return False

    # Protect against replay
    if abs(time.time() - int(ts)) > 60 * 5:
        return False

    basestring = f"v0:{ts}:{body}".encode("utf-8")
    my_sig = "v0=" + hmac.new(signing_secret.encode("utf-8"), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(my_sig, sig)


def _parse_slash_command(body: str) -> dict:
    parsed = urllib.parse.parse_qs(body or "")
    # Slack sends values as lists
    return {k: v[0] for k, v in parsed.items()}


def lambda_handler(event, context):
    body = event.get("body", "") or ""
    headers = event.get("headers") or {}
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            return {"statusCode": 400, "body": "Failed to decode body"}

    # Slack URL verification (events API)
    try:
        payload = json.loads(body)
        if payload.get("type") == "url_verification":
            return {"statusCode": 200, "body": payload.get("challenge", "")}
    except Exception:
        # Not JSON; likely a slash command (form-encoded)
        pass

    signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
    if not signing_secret:
        return {"statusCode": 500, "body": "Missing SLACK_SIGNING_SECRET"}

    if not _verify_signature(headers, body, signing_secret):
        return {"statusCode": 401, "body": "Signature verification failed"}

    # Slash command path (form-encoded)
    if headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
        cmd = _parse_slash_command(body)
        text = cmd.get("text", "")
        resp = handle_command(text)
        return {
            "statusCode": resp.status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"response_type": "ephemeral", "text": resp.text}),
        }

    # Fallback for unsupported payloads
    return {"statusCode": 400, "body": "Unsupported Slack payload"}

