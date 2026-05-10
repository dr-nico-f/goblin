import hashlib
import hmac
import json
import time
from unittest.mock import patch

import pytest
from goblin.slack_events import _verify_signature, _parse_slash_command, lambda_handler


SIGNING_SECRET = "test_signing_secret_123"


def _make_signature(body: str, ts: str, secret: str = SIGNING_SECRET) -> str:
    basestring = f"v0:{ts}:{body}".encode("utf-8")
    return "v0=" + hmac.new(
        secret.encode("utf-8"), basestring, hashlib.sha256,
    ).hexdigest()


def _signed_event(body: str, headers: dict | None = None, base64: bool = False):
    ts = str(int(time.time()))
    sig = _make_signature(body, ts)
    h = {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        **(headers or {}),
    }
    event = {"body": body, "headers": h}
    if base64:
        import base64 as b64
        event["body"] = b64.b64encode(body.encode()).decode()
        event["isBase64Encoded"] = True
    return event


class TestVerifySignature:
    def test_valid_signature(self):
        body = "test_body"
        ts = str(int(time.time()))
        sig = _make_signature(body, ts)
        headers = {
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        }
        assert _verify_signature(headers, body, SIGNING_SECRET) is True

    def test_invalid_signature(self):
        headers = {
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=bad",
        }
        assert _verify_signature(headers, "body", SIGNING_SECRET) is False

    def test_missing_timestamp(self):
        headers = {"X-Slack-Signature": "v0=anything"}
        assert _verify_signature(headers, "body", SIGNING_SECRET) is False

    def test_missing_signature(self):
        headers = {"X-Slack-Request-Timestamp": str(int(time.time()))}
        assert _verify_signature(headers, "body", SIGNING_SECRET) is False

    def test_replay_attack_rejected(self):
        old_ts = str(int(time.time()) - 600)
        sig = _make_signature("body", old_ts)
        headers = {
            "X-Slack-Request-Timestamp": old_ts,
            "X-Slack-Signature": sig,
        }
        assert _verify_signature(headers, "body", SIGNING_SECRET) is False

    def test_lowercase_headers(self):
        body = "test"
        ts = str(int(time.time()))
        sig = _make_signature(body, ts)
        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        }
        assert _verify_signature(headers, body, SIGNING_SECRET) is True


class TestParseSlashCommand:
    def test_parses_form_data(self):
        body = "text=help&user_id=U123&channel_id=C456"
        result = _parse_slash_command(body)
        assert result["text"] == "help"
        assert result["user_id"] == "U123"
        assert result["channel_id"] == "C456"

    def test_empty_body(self):
        assert _parse_slash_command("") == {}

    def test_none_body(self):
        assert _parse_slash_command(None) == {}


class TestLambdaHandler:
    def test_missing_signing_secret(self, monkeypatch):
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
        resp = lambda_handler({"body": "", "headers": {}}, None)
        assert resp["statusCode"] == 500

    def test_invalid_signature_rejected(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        resp = lambda_handler({
            "body": "data",
            "headers": {
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=invalid",
            },
        }, None)
        assert resp["statusCode"] == 401

    def test_url_verification_after_sig_check(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        payload = json.dumps({"type": "url_verification", "challenge": "abc"})
        event = _signed_event(payload)
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        assert resp["body"] == "abc"

    def test_url_verification_blocked_without_valid_sig(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        payload = json.dumps({"type": "url_verification", "challenge": "abc"})
        event = {
            "body": payload,
            "headers": {
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=forged",
            },
        }
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 401

    @patch("goblin.slack_events.handle_command")
    def test_slash_command_routing(self, mock_cmd, monkeypatch):
        from goblin.commands import CommandResult
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        mock_cmd.return_value = CommandResult(text="ok", blocks=None)

        body = "text=help&user_id=U1&channel_id=C1"
        event = _signed_event(body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
        })
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        mock_cmd.assert_called_once_with("help", user_id="U1", channel_id="C1")

    def test_unsupported_payload(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        event = _signed_event("not-json-not-form", headers={
            "Content-Type": "text/plain",
        })
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 400

    def test_base64_decoding(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        payload = json.dumps({"type": "url_verification", "challenge": "xyz"})
        event = _signed_event(payload, base64=True)
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        assert resp["body"] == "xyz"
