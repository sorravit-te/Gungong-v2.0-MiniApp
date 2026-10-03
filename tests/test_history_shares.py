"""API → snapshot storage → recipient reads; synthetic DB/identities only."""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.backend.routers import history_shares as routes
from src.backend.services import history_shares as service
from src.backend.services.user_identity_service import require_user, UserIdentity
from src.backend.core.models import COLLECTION_HISTORY

TOKEN = "A" * 43


class Database:
    def __init__(self):
        self.records = {}
        self.operations = []

    def collection(self, name):
        return SimpleNamespace(document=lambda key: self.document(name, key))

    def document(self, name, key):
        def get(**kwargs):
            self.operations.append(("get", name, key, kwargs))
            return SimpleNamespace(to_dict=lambda: self.records.get((name, key), {}).copy())

        def create(data, **kwargs):
            self.operations.append(("create", name, key, kwargs))
            if (name, key) in self.records:
                raise AlreadyExists("exists")
            self.records[name, key] = data.copy()

        def update(data, **kwargs):
            self.operations.append(("update", name, key, kwargs))
            self.records[name, key].update(data)
        return SimpleNamespace(get=get, create=create, update=update)


class HistoryShareTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.records[COLLECTION_HISTORY, "scan"] = {
            "user_id": "owner", "type": "link", "is_safe": False,
            "message_text": "https://user:password@sample.test/reset?token=private#secret",
            "created_at": datetime.now(timezone.utc),
            "url_check_result": {"verification_verdict": "INCOMPLETE", "checks": {"private": "secret"}},
            "reason": "private phone 0123456789", "display_name": "private-name",
        }
        app = FastAPI()
        app.state.limiter = routes.limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(routes.router)

        async def identity(x_test_user: str = Header(default="")):
            if not x_test_user:
                raise HTTPException(401, "Login required")
            return UserIdentity(x_test_user, "Not public")

        app.dependency_overrides[require_user] = identity
        routes.limiter.enabled = False
        self.addCleanup(setattr, routes.limiter, "enabled", True)
        patcher = patch.object(routes, "get_database_service", return_value=SimpleNamespace(db=self.db))
        patcher.start(); self.addCleanup(patcher.stop)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.payload = {"entry_id": "scan", "token": TOKEN, "include_content": True, "consent": True}

    def create(self, user="owner", **changes):
        return self.client.post("/api/history-shares", json={**self.payload, **changes}, headers={"X-Test-User": user})

    def read(self, token=TOKEN):
        return self.client.get(f"/api/history-shares/{token}")

    def stored(self):
        return self.db.records[service.COLLECTION, hashlib.sha256(TOKEN.encode()).hexdigest()]

    def test_create_requires_verified_owner_and_explicit_consent(self):
        for user, fields, code in [("", {}, 401), ("other", {}, 404),
                                   ("owner", {"consent": False}, 422), ("owner", {"entry_id": "missing"}, 404)]:
            self.assertEqual(self.create(user, **fields).status_code, code)
        self.assertEqual(len(self.db.records), 1)

    def test_server_projection_never_exposes_private_history_or_url_credentials(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["snapshot"]["content"], "[โดเมน: sample.test]")
        self.assertEqual(response.json()["snapshot"]["verdict"], "INCOMPLETE")
        for private in ["owner", "scan\"", "password", "reset", "token=", "secret", "user_id", "checks", "private-name"]:
            self.assertNotIn(private, response.text)
        self.assertEqual(set(response.json()), {"snapshot", "expires_at"})
        self.assertEqual(self.read().json(), response.json())

    def test_recipient_does_not_need_login_or_read_history_and_only_one_bounded_read(self):
        self.create(); self.db.operations.clear()
        self.assertEqual(self.read().status_code, 200)
        self.assertEqual(len(self.db.operations), 1)
        op = self.db.operations[0]
        self.assertEqual(op[:2], ("get", service.COLLECTION))
        self.assertEqual(op[3], {"timeout": 3, "retry": None})

    def test_initial_creation_reads_history_once_and_creates_once_without_rescan(self):
        self.create()
        self.assertEqual([op[:2] for op in self.db.operations], [("get", COLLECTION_HISTORY), ("create", service.COLLECTION)])
        self.assertNotIn(TOKEN, repr(self.db.records))

    def test_no_content_option_omits_message_not_just_from_card(self):
        self.assertEqual(self.create(include_content=False).json()["snapshot"]["content"], "")
        self.assertEqual(self.read().json()["snapshot"]["content"], "")

    def test_idempotent_retry_does_not_extend_expiry_or_change_snapshot(self):
        first = self.create().json()
        self.db.records[COLLECTION_HISTORY, "scan"]["message_text"] = "changed private input"
        self.assertEqual(self.create().json(), first)
        self.assertEqual(self.create(include_content=False).status_code, 409)
        self.db.records[COLLECTION_HISTORY, "other-scan"] = {"user_id": "owner"}
        self.assertEqual(self.create(entry_id="other-scan").status_code, 409)

    def test_bearer_token_collision_cannot_overwrite_another_owners_share(self):
        self.create()
        self.db.records[COLLECTION_HISTORY, "other"] = {"user_id": "other"}
        self.assertEqual(self.create("other", entry_id="other").status_code, 409)
        self.assertEqual(self.stored()["owner_id"], "owner")

    def test_expired_unknown_and_revoked_links_are_indistinguishable(self):
        self.assertEqual(self.read().status_code, 404)
        self.create(); self.stored()["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        expired = self.read()
        self.assertEqual(expired.status_code, 404)
        self.stored()["expires_at"] = datetime.now(timezone.utc) + timedelta(days=1)
        self.stored()["revoked"] = True
        self.assertEqual(self.read().json(), expired.json())
        self.assertEqual(self.read("B" * 43).json(), expired.json())
        self.assertEqual(self.create().status_code, 404)  # No retry resurrection.

    def test_owner_only_revoke_is_idempotent_and_does_not_touch_history(self):
        self.create()
        path = f"/api/history-shares/{TOKEN}/revoke"
        self.assertEqual(self.client.post(path).status_code, 401)
        self.assertEqual(self.client.post(path, headers={"X-Test-User": "other"}).status_code, 404)
        self.assertEqual(self.read().status_code, 200)
        for _ in range(2):
            self.assertEqual(self.client.post(path, headers={"X-Test-User": "owner"}).json(), {"revoked": True})
        self.assertEqual(self.read().status_code, 404)
        self.assertEqual(self.db.records[COLLECTION_HISTORY, "scan"]["user_id"], "owner")

    def test_rejects_arbitrary_snapshot_identity_fields_and_unsafe_inputs(self):
        for key, value in [("owner_id", "other"), ("snapshot", {}), ("expires_at", "2099"),
                           ("token", "short"), ("entry_id", "../private"),
                           ("include_content", "true"), ("consent", 1)]:
            with self.subTest(key=key):
                self.assertEqual(self.create(**{key: value}).status_code, 422)
        self.assertEqual(len(self.db.records), 1)

    def test_body_limit_and_no_public_list_or_write(self):
        response = self.client.post("/api/history-shares", content=b"x" * 32769, headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.client.get("/api/history-shares").status_code, 405)
        self.assertEqual(self.client.put(f"/api/history-shares/{TOKEN}", json={}).status_code, 405)

    def test_headers_prevent_caching_indexing_and_referrer_leaks(self):
        self.create()
        response = self.read()
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["x-robots-tag"], "noindex, nofollow")
        for response in [self.read("short"), self.create(token="invalid-private-token"), self.create(user="")]:
            self.assertEqual(response.headers["cache-control"], "private, no-store")
            self.assertNotIn("invalid-private-token", response.text)

    def test_database_failures_hide_error_details(self):
        with patch.object(self.db, "collection", side_effect=RuntimeError("private credentials")):
            response = self.read()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("credentials", response.text)
        with patch.object(routes, "get_database_service", return_value=None):
            self.assertEqual(self.create().status_code, 503)

    def test_snapshot_limits_and_common_identifiers(self):
        self.assertEqual(service.shared_content("0123456789", "phone"), "••••6789")
        self.assertEqual(service.shared_content("012-345-6789", "bank"), "••••6789")
        result = service.shared_content("mail private@example.test phone 0123456789 https://x.test/private?k=secret", "text")
        self.assertNotIn("private", result); self.assertNotIn("secret", result); self.assertNotIn("0123456789", result)
        self.assertLessEqual(len(service.shared_content("a" * 8000, "text")), 241)
        self.assertIsNone(service.timestamp("bad"))

    def test_all_verdicts_and_legacy_fallbacks_are_conservative(self):
        for value in service.VERDICTS:
            self.assertEqual(service.verdict({"url_check_result": {"verification_verdict": value}}), value)
        self.assertEqual(service.verdict({"verification_verdict": "future-status", "is_safe": True}), "INCOMPLETE")
        self.assertEqual(service.verdict({"type": "link", "classification": "VERIFICATION_INCOMPLETE", "is_safe": True}), "INCOMPLETE")
        self.assertEqual(service.verdict({"is_fraud": True, "is_safe": True}), "SUSPICIOUS")
        self.assertEqual(service.verdict({}), "INCOMPLETE")

    def test_create_rate_limit(self):
        routes.limiter.enabled = True; routes.limiter.reset(); self.addCleanup(routes.limiter.reset)
        for _ in range(10):
            self.assertEqual(self.create().status_code, 200)
        self.assertEqual(self.create().status_code, 429)


if __name__ == "__main__":
    unittest.main()
