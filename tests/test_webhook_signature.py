"""Webhook authentication without real LINE messages, providers or database I/O."""

import base64
import hashlib
import hmac
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.backend.routers import webhook


class WebhookSignatureTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(webhook.router)
        self.client = TestClient(app)
        self.body = b'{"events":[]}'
        self.secret = "fixture-secret-not-a-real-key"
        self.settings_patch = patch.object(
            webhook, "settings", SimpleNamespace(line_channel_secret=self.secret)
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.available_patch = patch.object(webhook, "LINE_SERVICE_AVAILABLE", True)
        self.available_patch.start()
        self.addCleanup(self.available_patch.stop)

    def signature(self, body):
        return base64.b64encode(hmac.new(
            self.secret.encode(), body, hashlib.sha256
        ).digest()).decode()

    def post(self, body=None, signature=None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Line-Signature"] = signature
        return self.client.post("/webhook", content=body or self.body, headers=headers)

    def test_valid_signed_empty_event_batch(self):
        self.assertEqual(self.post(signature=self.signature(self.body)).status_code, 200)

    def test_missing_signature(self):
        self.assertEqual(self.post().status_code, 403)

    def test_invalid_signature(self):
        self.assertEqual(self.post(signature="invalid").status_code, 403)

    def test_changed_body_invalidates_signature(self):
        self.assertEqual(self.post(b'{"events": []}', self.signature(self.body)).status_code, 403)

    def test_no_secret_fails_closed(self):
        with patch.object(webhook.settings, "line_channel_secret", None):
            self.assertEqual(self.post(signature="invalid").status_code, 503)

    def test_signature_checked_before_parsing_or_processing(self):
        with patch.object(webhook.json, "loads") as parser, patch.object(webhook, "get_line_service") as line:
            self.assertEqual(self.post(b"not-json", "invalid").status_code, 403)
            parser.assert_not_called()
            line.assert_not_called()

    def test_signed_invalid_json_is_rejected(self):
        body = b"not-json"
        self.assertEqual(self.post(body, self.signature(body)).status_code, 400)


if __name__ == "__main__":
    unittest.main()
