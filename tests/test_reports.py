"""Report receipts and validation with an in-memory database, no live writes."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.backend.routers import reports
from src.backend.services.user_identity_service import UserIdentity, require_user


class FakeDatabase:
    def __init__(self):
        self.records = {}
        self.collections = []

    def collection(self, name):
        self.collections.append(name)
        return self

    def document(self, key):
        records = self.records

        def create(data, **kwargs):
            if key in records:
                raise AlreadyExists("duplicate")
            records[key] = data.copy()

        return SimpleNamespace(create=create, get=lambda **kwargs:
                               SimpleNamespace(to_dict=lambda: records.get(key, {}).copy()))


class ReportsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.state.limiter = reports.limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(reports.router)

        async def identity(x_test_user: str = Header(default="")):
            if not x_test_user:
                raise HTTPException(401, "Login required")
            return UserIdentity(x_test_user, "Verified user")

        app.dependency_overrides[require_user] = identity
        reports.limiter.enabled = False
        self.addCleanup(setattr, reports.limiter, "enabled", True)
        self.db = FakeDatabase()
        self.patch = patch.object(reports, "get_database_service",
                                  return_value=SimpleNamespace(db=self.db))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.payload = {"kind": "link", "content": "https://example.com/suspicious",
                        "reason": "phishing", "details": "Found in a message",
                        "request_id": str(uuid4())}

    def submit(self, payload=None, user="line-user"):
        return self.client.post("/api/reports", json=self.payload if payload is None else payload,
                                headers={"X-Test-User": user})

    def test_requires_verified_identity_and_has_no_public_read_endpoint(self):
        self.assertEqual(self.submit(user="").status_code, 401)
        self.assertEqual(self.client.get("/api/reports").status_code, 405)
        self.assertEqual(self.db.records, {})

    def test_real_receipt_pending_and_server_owned_identity(self):
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertRegex(response.json()["id"], r"^[a-f0-9]{64}$")
        stored = self.db.records[response.json()["id"]]
        self.assertEqual(stored["reporter_id"], "line-user")
        self.assertEqual(stored["status"], "pending")
        self.assertIsNotNone(stored["created_at"].tzinfo)
        self.assertEqual(set(self.db.collections), {"content_reports"})

    def test_retry_is_idempotent_and_does_not_overwrite(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(self.db.records), 1)
        changed = {**self.payload, "content": "https://different.example"}
        self.assertEqual(self.submit(changed).status_code, 409)
        self.assertEqual(next(iter(self.db.records.values()))["content"], self.payload["content"])

    def test_different_reporters_do_not_share_a_retry_key(self):
        first = self.submit().json()
        second = self.submit(user="another-line-user").json()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.db.records), 2)

    def test_text_is_literal_and_trimmed(self):
        payload = {**self.payload, "kind": "text", "content": "  <script>not HTML</script>  "}
        self.assertEqual(self.submit(payload).status_code, 200)
        self.assertEqual(next(iter(self.db.records.values()))["content"], "<script>not HTML</script>")

    def test_rejects_forged_identity_and_unknown_types_reasons(self):
        for field, value in [("reporter_id", "forged"), ("kind", "bank"), ("reason", "safe"),
                             ("status", "approved"), ("request_id", "not-a-uuid")]:
            with self.subTest(field=field):
                self.assertEqual(self.submit({**self.payload, field: value}).status_code, 422)
        self.assertEqual(self.db.records, {})

    def test_rejects_invalid_urls_and_bounds_without_fetching_them(self):
        for value in ["javascript:alert(1)", "example.com", "https://user:secret@example.com",
                      "https://example.com:invalid", "https://example.com/has space",
                      "https://example.com/" + "a" * 2048]:
            with self.subTest(value=value[:45]):
                self.assertEqual(self.submit({**self.payload, "content": value}).status_code, 422)
        for fields in [{"kind": "text", "content": " "}, {"kind": "text", "content": "a" * 5001},
                       {"details": "a" * 1001}]:
            self.assertEqual(self.submit({**self.payload, **fields}).status_code, 422)
        self.assertEqual(self.db.records, {})

    def test_request_body_is_bounded(self):
        response = self.client.post("/api/reports", content=b"x" * (32 * 1024 + 1),
                                    headers={"Content-Type": "application/json", "X-Test-User": "line-user"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.db.records, {})

    def test_unavailable_database_never_returns_success(self):
        with patch.object(reports, "get_database_service", return_value=None):
            self.assertEqual(self.submit().status_code, 503)
        with patch.object(self.db, "document", side_effect=RuntimeError("offline")):
            self.assertEqual(self.submit().status_code, 503)
        self.assertEqual(self.db.records, {})

    def test_detail_is_owner_only_and_has_no_notification_secrets(self):
        report_id = self.submit().json()["id"]
        self.db.records[report_id].update({"status": "reviewed", "review_result": "risk",
            "review_note": "<script>literal explanation</script>", "reviewer": "private-operator",
            "notification_session": "private-session", "notification_token": "private-token"})
        response = self.client.get(f"/api/reports/{report_id}", headers={"X-Test-User": "line-user"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.json()["status"], "reviewed")
        self.assertEqual(response.json()["review_note"], "<script>literal explanation</script>")
        self.assertNotIn("private-", response.text)
        self.assertEqual(self.client.get(f"/api/reports/{report_id}").status_code, 401)
        self.assertEqual(self.client.get(f"/api/reports/{report_id}",
            headers={"X-Test-User": "other"}).status_code, 404)
        self.assertEqual(self.client.get("/api/reports/not-valid", headers={"X-Test-User": "line-user"}).status_code, 404)

    def test_notification_disabled_by_default_and_no_public_review_mutation(self):
        report_id = self.submit().json()["id"]
        with patch.object(reports.settings, "line_service_messages_enabled", False), \
                patch.object(reports, "send_receipt_notification") as prepare:
            response = self.client.post(f"/api/reports/{report_id}/notification",
                                         headers={"X-Test-User": "line-user"})
            self.assertEqual(response.json(), {"notification": "disabled"})
            prepare.assert_not_called()
        self.assertEqual(self.client.post(f"/api/reports/{report_id}/notification").status_code, 401)
        self.assertEqual(self.client.patch(f"/api/reports/{report_id}", json={"status": "reviewed"},
            headers={"X-Test-User": "line-user"}).status_code, 405)

    def test_immediate_acknowledgement_is_separate_from_receipt_and_line_only(self):
        report_id = self.submit().json()["id"]
        with patch.object(reports.settings, "line_service_messages_enabled", True), \
                patch.object(reports, "send_receipt_notification", return_value="sent") as prepare:
            self.assertEqual(self.client.post(f"/api/reports/{report_id}/notification",
                headers={"X-Test-User": "line-user", "X-Auth-Provider": "firebase"}).status_code, 403)
            prepare.assert_not_called()
            response = self.client.post(f"/api/reports/{report_id}/notification",
                headers={"X-Test-User": "line-user", "X-Auth-Provider": "line",
                         "Authorization": "Bearer test-token"})
            self.assertEqual(response.json(), {"notification": "sent"})
            prepare.assert_called_once_with(self.db, reports.settings, report_id, "line-user", "test-token")
        with patch.object(reports.settings, "line_service_messages_enabled", True), \
                patch.object(reports, "send_receipt_notification", side_effect=RuntimeError("private")):
            response = self.client.post(f"/api/reports/{report_id}/notification",
                headers={"X-Test-User": "line-user", "X-Auth-Provider": "line"})
            self.assertEqual(response.json(), {"notification": "unavailable"})
            self.assertEqual(self.db.records[report_id]["status"], "pending")

    def test_acknowledgement_retry_does_not_claim_a_second_message(self):
        report_id = self.submit().json()["id"]
        with patch.object(reports.settings, "line_service_messages_enabled", True), \
                patch.object(reports, "send_receipt_notification", return_value="already_sent"):
            response = self.client.post(f"/api/reports/{report_id}/notification",
                headers={"X-Test-User": "line-user", "X-Auth-Provider": "line",
                         "Authorization": "Bearer test-token"})
        self.assertEqual(response.json(), {"notification": "sent"})
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(self.db.records[report_id]["status"], "pending")

    def test_rate_limit_rejects_excess_requests(self):
        reports.limiter.enabled = True
        reports.limiter.reset()
        self.addCleanup(reports.limiter.reset)
        for _ in range(5):
            self.assertEqual(self.submit({**self.payload, "request_id": str(uuid4())}).status_code, 200)
        self.assertEqual(self.submit().status_code, 429)


if __name__ == "__main__":
    unittest.main()
