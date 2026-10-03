"""No live LINE requests or Firestore writes. Atomic in-memory transaction model."""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1.types import BatchGetDocumentsResponse, Document, Value
from pydantic import SecretStr

from src.backend.services import report_service_messages as messages
from scripts.reports.complete_review import parser, run


class MemoryDB:
    def __init__(self):
        self.records = {}
        self.lock = threading.RLock()
        self.batch_reads = []

    def collection(self, name):
        db = self
        class Ref:
            def __init__(self, key):
                self.path = (name, key)

            def get(self, transaction=None, **kwargs):
                if transaction is not None and transaction.wrote:
                    raise AssertionError("Firestore reads must precede writes")
                return SimpleNamespace(to_dict=lambda: deepcopy(db.records.get(self.path, {})))

            def update(self, data, **kwargs):
                with db.lock:
                    db.records[self.path].update(deepcopy(data))
        return SimpleNamespace(document=Ref)

    def get_all(self, references, transaction=None, **kwargs):
        self.batch_reads.append((references, transaction, kwargs))
        # Deliberately reverse Firestore's unspecified response order.
        for reference in reversed(references):
            snapshot = reference.get(transaction=transaction, **kwargs)
            yield SimpleNamespace(reference=reference, to_dict=snapshot.to_dict)

    def atomic(self, operation):
        db = self
        class Tx:
            wrote = False
            def update(self, reference, data):
                self.wrote = True
                reference.update(data)
            def set(self, reference, data):
                self.wrote = True
                db.records[reference.path] = deepcopy(data)
        with self.lock:
            before = deepcopy(self.records)
            try:
                return operation(Tx())
            except Exception:
                self.records = before
                raise


def config(**updates):
    return SimpleNamespace(line_service_messages_enabled=True,
        line_service_messages_environment="developing", line_service_messages_published_approved=False,
        line_miniapp_channel_id="123", line_login_channel_id="123",
        line_miniapp_channel_secret=SecretStr("test-secret-not-real"),
        line_miniapp_liff_id="123-Test", line_service_messages_test_user_ids="test-user",
        firestore_project_id="test-project", **updates)


class ServiceMessagesTests(unittest.TestCase):
    def setUp(self):
        self.db, self.cfg = MemoryDB(), config()
        self.id = "a" * 64
        self.db.records[(messages.REPORTS, self.id)] = {
            "reporter_id": "test-user", "status": "pending", "kind": "text",
            "content": "<script>literal tip</script>"}
        self.patch = patch.object(messages, "transaction", side_effect=lambda db, op: db.atomic(op))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.calls = []
        self.fail_issue = False
        self.fail_send = False
        self.final_send = False

    @contextmanager
    def client(self):
        def respond(request):
            self.calls.append(request)
            if request.url.path == "/oauth2/v3/token":
                return httpx.Response(200, json={"access_token": "test-channel-token"})
            if request.url.path.endswith("/token"):
                if self.fail_issue:
                    raise httpx.ReadTimeout("secret exception must not escape")
                return httpx.Response(200, json={"notificationToken": "initial-token",
                    "sessionId": "line-session", "expiresIn": 31536000, "remainingCount": 5})
            if self.fail_send:
                raise httpx.ReadTimeout("secret exception must not escape")
            return httpx.Response(200, json={"notificationToken": "rotated-token",
                "sessionId": "line-session", "expiresIn": 0 if self.final_send else 31536000,
                "remainingCount": 0 if self.final_send else 5 - len(self.sends())})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            yield client

    def register(self, report_id=None, token="raw-test-liff-token"):
        return messages.register_notification(self.db, self.cfg, report_id or self.id,
                                               "test-user", token, self.client)

    def complete(self, report_id=None):
        messages.complete_review(self.db, report_id or self.id, "operator", "risk", "Review completed")

    def send(self, report_id=None):
        return messages.send_receipt_notification(self.db, self.cfg, report_id or self.id,
                                                   "test-user", "raw-test-liff-token", self.client)

    def report(self, report_id=None):
        return self.db.records[(messages.REPORTS, report_id or self.id)]

    def session(self):
        return self.db.records[(messages.SESSIONS, self.report()["notification_session"])]

    def sends(self):
        return [request for request in self.calls if request.url.path.endswith("/send")]

    def test_registration_prepares_once_never_sends_and_never_stores_liff_token(self):
        self.assertEqual(self.register(), "ready")
        self.assertEqual(self.register(), "ready")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.sends(), [])
        self.assertEqual(self.report()["status"], "pending")
        self.assertNotIn("raw-test-liff-token", repr(self.db.records))
        self.assertNotIn("test-secret-not-real", repr(self.db.records))

    def test_same_session_shared_by_two_reports_issued_only_once(self):
        self.register()
        second = "b" * 64
        self.db.records[(messages.REPORTS, second)] = {**self.report(), "notification_session": None}
        self.register(second)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.report(second)["notification_session"], self.report()["notification_session"])

    def test_concurrent_registration_issues_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.register(), range(2)))
        self.assertEqual(sum(request.url.path.endswith("notifier/token") for request in self.calls), 1)

    def test_issuance_uncertainty_blocks_reissue(self):
        self.fail_issue = True
        self.assertEqual(self.register(), "unavailable")
        self.fail_issue = False
        self.assertEqual(self.register(), "unavailable")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.session()["state"], "unknown")

    def test_pending_receipt_is_notified_immediately_with_three_line_calls(self):
        self.assertEqual(self.send(), "sent")
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.report()["status"], "pending")
        self.assertNotIn("reviewed_at", self.report())
        self.assertNotIn("raw-test-liff-token", repr(self.db.records))
        self.assertNotIn("test-secret-not-real", repr(self.db.records))

    def test_notification_batches_independent_reads_without_weakening_transactions(self):
        self.assertEqual(self.send(), "sent")
        self.assertEqual(len(self.db.batch_reads), 2)
        for references, tx, kwargs in self.db.batch_reads:
            self.assertEqual(len(references), 2)
            self.assertIsNotNone(tx)
            self.assertEqual(kwargs, {"timeout": 4, "retry": None})
        self.assertEqual(self.report()["receipt_notification_state"], "sent")
        self.assertEqual(self.session()["state"], "ready")
        self.assertEqual(len(self.sends()), 1)

    def test_incomplete_batch_read_does_not_issue_or_send(self):
        def incomplete(references, **kwargs):
            reference = references[0]
            return [SimpleNamespace(reference=reference, to_dict=lambda: self.report())]
        with patch.object(self.db, "get_all", side_effect=incomplete):
            with self.assertRaisesRegex(messages.ServiceMessageError, "database_read_incomplete"):
                self.send()
        self.assertEqual(self.calls, [])
        self.assertNotIn("notification_session", self.report())

    def test_review_replay_does_not_overwrite_or_change_timestamp(self):
        self.complete()
        previous = deepcopy(self.report())
        self.complete()
        self.assertEqual(previous, self.report())
        with self.assertRaisesRegex(messages.ServiceMessageError, "review_already_completed"):
            messages.complete_review(self.db, self.id, "operator", "risk", "Changed")
        self.assertEqual(previous, self.report())

    def test_exact_template_minimal_params_safe_permanent_link_and_rotation(self):
        self.register()
        self.assertEqual(self.send(), "sent")
        calls = len(self.calls)
        self.assertEqual(self.send(), "already_sent")
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(len(self.sends()), 1)
        request = self.sends()[0]
        self.assertEqual(request.url.query, b"target=service")
        self.assertEqual(json.loads(request.content), {
            "templateName": "answer_completed_s_th", "notificationToken": "initial-token",
            "params": {"btn1_url": f"https://miniapp.line.me/123-Test?section=report&reportId={self.id}"}})
        self.assertNotIn("<script>", request.content.decode())
        self.assertEqual(self.session()["notification_token"], "rotated-token")
        self.assertEqual(self.session()["remaining_count"], 4)

    def test_concurrent_send_one_external_attempt(self):
        def attempt(_):
            try:
                return self.send()
            except messages.ServiceMessageError:
                return "blocked"
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(attempt, range(2)))
        self.assertEqual(len(self.sends()), 1)

    def test_two_reports_use_rotated_token_and_shared_quota(self):
        self.register()
        second = "b" * 64
        self.db.records[(messages.REPORTS, second)] = {**self.report(), "notification_session": None}
        self.register(second)
        self.send()
        self.send(second)
        bodies = [json.loads(request.content) for request in self.sends()]
        self.assertEqual([body["notificationToken"] for body in bodies], ["initial-token", "rotated-token"])
        self.assertEqual(self.session()["remaining_count"], 3)
        self.assertEqual(sum(request.url.path.endswith("notifier/token") for request in self.calls), 1)

    def test_post_send_database_failure_never_replays_external_send(self):
        self.register()
        def fail_persist(db, operation):
            if operation.__name__ == "persist":
                raise RuntimeError("lost DB acknowledgment")
            return db.atomic(operation)
        with patch.object(messages, "transaction", side_effect=fail_persist):
            with self.assertRaisesRegex(messages.ServiceMessageError, "delivery_unknown_no_retry"):
                self.send()
        self.assertEqual(self.report()["receipt_notification_state"], "sending")
        with self.assertRaisesRegex(messages.ServiceMessageError, "delivery_unknown_no_retry"):
            self.send()
        self.assertEqual(len(self.sends()), 1)

    def test_shared_session_uncertainty_blocks_other_report(self):
        self.register()
        second = "b" * 64
        self.db.records[(messages.REPORTS, second)] = {**self.report(), "notification_session": None}
        self.register(second)
        self.fail_send = True
        with self.assertRaises(messages.ServiceMessageError):
            self.send()
        with self.assertRaisesRegex(messages.ServiceMessageError, "notification_session_unavailable"):
            self.send(second)
        self.assertEqual(len(self.sends()), 1)

    def test_pre_send_channel_failure_does_not_reserve_an_external_attempt(self):
        self.register()
        @contextmanager
        def broken_client():
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={}))) as client:
                yield client
        with self.assertRaisesRegex(messages.ServiceMessageError, "line_request_rejected"):
            messages.send_receipt_notification(self.db, self.cfg, self.id,
                                               "test-user", "raw-test-liff-token", broken_client)
        self.assertNotIn("receipt_notification_state", self.report())
        self.assertEqual(self.session()["state"], "ready")

    def test_malformed_quota_and_secret_errors_are_sanitized(self):
        for payload in [{}, {"notificationToken": "t", "sessionId": "s", "expiresIn": True, "remainingCount": 5},
            {"notificationToken": "t", "sessionId": "s", "expiresIn": 31536001, "remainingCount": 5},
            {"notificationToken": "t", "sessionId": "s", "expiresIn": 1, "remainingCount": 6}]:
            with self.assertRaisesRegex(messages.ServiceMessageError, "invalid_line_response"):
                messages.token_data(payload)

    def test_review_without_receipt_does_not_trigger_delayed_acknowledgement(self):
        self.complete()
        with self.assertRaisesRegex(messages.ServiceMessageError, "report_not_pending"):
            self.send()
        self.assertEqual(self.report()["status"], "reviewed")
        self.assertEqual(self.sends(), [])

    def test_timeout_keeps_receipt_pending_and_blocks_resending_and_stale_session(self):
        self.register()
        self.fail_send = True
        with self.assertRaisesRegex(messages.ServiceMessageError, "delivery_unknown_no_retry"):
            self.send()
        self.fail_send = False
        with self.assertRaisesRegex(messages.ServiceMessageError, "delivery_unknown_no_retry"):
            self.send()
        self.assertEqual(len(self.sends()), 1)
        self.assertEqual(self.report()["status"], "pending")
        self.assertEqual(self.session()["state"], "sending")

    def test_final_quota_response_is_success_not_retry(self):
        self.register()
        self.final_send = True
        self.assertEqual(self.send(), "sent")
        self.assertEqual(self.session()["state"], "exhausted")
        self.assertEqual(self.send(), "already_sent")

    def test_expired_or_exhausted_session_cannot_send(self):
        self.register()
        for values in [{"expires_at": messages.now() - timedelta(seconds=1)}, {"remaining_count": 0}]:
            with self.subTest(values=values):
                self.session().update(values)
                with self.assertRaisesRegex(messages.ServiceMessageError, "notification_session_unavailable"):
                    self.send()
        self.assertEqual(self.sends(), [])

    def test_foreign_owner_and_session_rebinding_rejected(self):
        self.register()
        with self.assertRaisesRegex(messages.ServiceMessageError, "session_already_bound"):
            self.register(token="new-session")
        self.session()["reporter_id"] = "another-user"
        with self.assertRaisesRegex(messages.ServiceMessageError, "session_owner_mismatch"):
            self.send()
        self.assertEqual(self.sends(), [])

    def test_disabled_wrong_channel_unapproved_published_and_testers_fail_closed(self):
        for field, value, code in [
            ("line_service_messages_enabled", False, "disabled"),
            ("line_login_channel_id", "999", "configuration"),
            ("line_miniapp_liff_id", "999-Wrong", "configuration"),
            ("line_miniapp_channel_secret", None, "configuration"),
            ("line_service_messages_environment", "published", "approval"),
            ("line_service_messages_test_user_ids", "other", "tester")]:
            with self.subTest(field=field):
                cfg = config()
                setattr(cfg, field, value)
                with self.assertRaisesRegex(messages.ServiceMessageError, code):
                    messages.send_receipt_notification(self.db, cfg, self.id, "test-user", "token", self.client)
        self.assertEqual(self.calls, [])

    def test_foreign_or_missing_receipt_never_calls_line_or_creates_session(self):
        self.cfg.line_service_messages_test_user_ids = "test-user,other"
        for report_id, user in [(self.id, "other"), ("b" * 64, "test-user")]:
            with self.assertRaises(Exception) as caught:
                messages.send_receipt_notification(self.db, self.cfg, report_id, user, "token", self.client)
            self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.db.records), 1)

    def test_issuance_failure_preserves_receipt_and_cannot_reissue_on_retry(self):
        self.fail_issue = True
        for _ in range(2):
            with self.assertRaisesRegex(messages.ServiceMessageError, "notification_session_unavailable"):
                self.send()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.report()["status"], "pending")
        self.assertEqual(self.sends(), [])

    def test_acknowledgement_replay_after_manual_review_never_sends_again(self):
        self.send()
        self.complete()
        calls = len(self.calls)
        self.assertEqual(self.send(), "already_sent")
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(self.report()["status"], "reviewed")

    def test_legacy_review_notification_fields_do_not_impersonate_a_receipt_ack(self):
        self.report()["notification_state"] = "sent"
        self.assertEqual(self.send(), "sent")
        self.assertEqual(len(self.sends()), 1)
        self.assertEqual(self.report()["receipt_notification_state"], "sent")
        self.assertEqual(self.report()["status"], "pending")

    def test_manual_review_after_acknowledgement_has_no_line_transport(self):
        self.send()
        calls = len(self.calls)
        args = parser().parse_args([self.id, "--project", "test-project", "--reviewer", "operator",
            "--result", "risk", "--note", "Reviewed", "--apply", "--confirm-reviewed"])
        result = run(args, self.cfg, SimpleNamespace(db=self.db))
        self.assertEqual(result["notification"], "not_requested")
        self.assertEqual(self.report()["status"], "reviewed")
        self.assertEqual(len(self.calls), calls)

    def test_owner_projection_excludes_operator_and_all_notification_credentials(self):
        self.register()
        self.complete()
        data = messages.public_report(self.id, self.report())
        self.assertEqual(set(data), {"id", "kind", "content", "status", "review_result", "review_note", "reviewed_at"})
        with self.assertRaises(Exception) as caught:
            messages.owned_report(self.db, self.id, "other")
        self.assertEqual(caught.exception.status_code, 404)

    def test_operator_preview_no_writes_confirmation_and_project_guards(self):
        args = parser().parse_args([self.id, "--project", "test-project", "--reviewer", "operator",
                                     "--result", "risk", "--note", "Reviewed"])
        previous = deepcopy(self.db.records)
        self.assertEqual(run(args, self.cfg, SimpleNamespace(db=self.db))["mode"], "preview")
        self.assertEqual(previous, self.db.records)
        args.apply = True
        with self.assertRaisesRegex(messages.ServiceMessageError, "confirmation_required"):
            run(args, self.cfg, SimpleNamespace(db=self.db))
        args.confirm_reviewed = True
        args.project = "wrong-project"
        with self.assertRaisesRegex(messages.ServiceMessageError, "project_confirmation_mismatch"):
            run(args, self.cfg, SimpleNamespace(db=self.db))
        self.assertEqual(previous, self.db.records)
        args.project = "test-project"
        self.assertEqual(run(args, self.cfg, SimpleNamespace(db=self.db))["notification"], "not_requested")
        self.assertEqual(self.report()["status"], "reviewed")
        self.assertEqual(self.calls, [])


class FirestoreBatchReadTests(unittest.TestCase):
    def test_installed_sdk_uses_one_rpc_with_reversed_and_missing_snapshots(self):
        # Use the real installed SDK, but replace its RPC so no cloud is contacted.
        db = messages.firestore.Client(project="synthetic-test-project", credentials=AnonymousCredentials())
        self.addCleanup(db.close)
        report_ref = db.collection(messages.REPORTS).document("a" * 64)
        session_ref = db.collection(messages.SESSIONS).document("b" * 64)
        tx = db.transaction()
        tx._id = b"synthetic-transaction"
        responses = [
            BatchGetDocumentsResponse(missing=session_ref._document_path),
            BatchGetDocumentsResponse(found=Document(name=report_ref._document_path,
                fields={"reporter_id": Value(string_value="synthetic-user")})),
        ]
        with patch.object(db._firestore_api, "batch_get_documents", return_value=iter(responses)) as rpc:
            report, session = messages.read_many(db, [report_ref, session_ref], tx)
        self.assertEqual(report, {"reporter_id": "synthetic-user"})
        self.assertEqual(session, {})
        rpc.assert_called_once()
        request = rpc.call_args.kwargs["request"]
        self.assertEqual(request["transaction"], b"synthetic-transaction")
        self.assertEqual(request["documents"], [report_ref._document_path, session_ref._document_path])
        self.assertEqual(rpc.call_args.kwargs["timeout"], 4)
        self.assertIsNone(rpc.call_args.kwargs["retry"])


if __name__ == "__main__":
    unittest.main()
