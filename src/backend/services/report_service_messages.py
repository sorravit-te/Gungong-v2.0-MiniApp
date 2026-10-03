"""Private MINI App receipt notifications and operator-only review completion.

LINE doesn't document an idempotency key for notifier/send. Reserve each external
attempt durably BEFORE calling it; an uncertain response stays blocked, never
blindly replayed. No network call runs inside a retryable Firestore transaction.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from google.cloud import firestore

REPORTS = "content_reports"
SESSIONS = "report_service_sessions"
TEMPLATE = "answer_completed_s_th"
RESULTS = {"no_risk_found", "risk", "inconclusive"}
ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class ServiceMessageError(Exception):
    """Only fixed, non-sensitive codes may cross the CLI/API boundary."""


def now():
    return datetime.now(timezone.utc)


def validate_id(report_id):
    if not isinstance(report_id, str) or not ID_PATTERN.fullmatch(report_id):
        raise HTTPException(404, "Report not found")


def configuration(cfg, user_id=None):
    if not cfg.line_service_messages_enabled:
        raise ServiceMessageError("notifications_disabled")
    channel = cfg.line_miniapp_channel_id
    if (not re.fullmatch(r"[0-9]+", channel)
            or channel != cfg.line_login_channel_id
            or not re.fullmatch(re.escape(channel) + r"-[A-Za-z0-9]+", cfg.line_miniapp_liff_id)
            or not cfg.line_miniapp_channel_secret
            or not cfg.line_miniapp_channel_secret.get_secret_value()):
        raise ServiceMessageError("miniapp_configuration_required")
    if cfg.line_service_messages_environment == "published":
        if not cfg.line_service_messages_published_approved:
            raise ServiceMessageError("published_approval_required")
    else:
        testers = {value.strip() for value in cfg.line_service_messages_test_user_ids.split(",") if value.strip()}
        if not testers or (user_id is not None and user_id not in testers):
            raise ServiceMessageError("developing_tester_required")


def transaction(db, operation):
    @firestore.transactional
    def run(tx):
        return operation(tx)
    return run(db.transaction(max_attempts=3))


def read(reference, tx=None):
    return reference.get(transaction=tx, timeout=4, retry=None).to_dict() or {}


def read_many(db, references, tx):
    # BatchGet returns snapshots in arbitrary order, including missing documents.
    # Keep the same transaction/timeout and fail closed on an incomplete response.
    snapshots = {snapshot.reference.path: snapshot.to_dict() or {}
                 for snapshot in db.get_all(references, transaction=tx, timeout=4, retry=None)}
    if set(snapshots) != {reference.path for reference in references}:
        raise ServiceMessageError("database_read_incomplete")
    return tuple(snapshots[reference.path] for reference in references)


def owned_report(db, report_id, user_id):
    validate_id(report_id)
    data = read(db.collection(REPORTS).document(report_id))
    if not data or data.get("reporter_id") != user_id:
        raise HTTPException(404, "Report not found")
    return data


def public_report(report_id, data):
    # Never serialize session keys, tokens, operator identifiers or delivery state.
    return {"id": report_id, "kind": data.get("kind"), "content": data.get("content"),
            "status": data.get("status"), "review_result": data.get("review_result"),
            "review_note": data.get("review_note", ""), "reviewed_at": data.get("reviewed_at")}


def token_data(value, *, exhausted_allowed=False):
    if not isinstance(value, dict):
        raise ServiceMessageError("invalid_line_response")
    token, session = value.get("notificationToken"), value.get("sessionId")
    seconds, count = value.get("expiresIn"), value.get("remainingCount")
    if (type(seconds) is not int or not 0 <= seconds <= 31536000
            or type(count) is not int or not 0 <= count <= 5
            or not isinstance(session, str) or not 1 <= len(session) <= 512
            or not isinstance(token, str) or len(token) > 8192
            or (not exhausted_allowed and (not token or not seconds or not count))
            or (exhausted_allowed and count > 0 and (not token or not seconds))):
        raise ServiceMessageError("invalid_line_response")
    return {"notification_token": token, "line_session_id": session,
            "expires_at": now() + timedelta(seconds=seconds), "remaining_count": count}


class LineServiceClient:
    def __init__(self, cfg, client):
        self.cfg, self.client = cfg, client

    def request(self, path, **kwargs):
        try:
            response = self.client.post("https://api.line.me" + path, **kwargs)
            if response.status_code != 200:
                raise ServiceMessageError("line_request_rejected")
            return response.json()
        except ServiceMessageError:
            raise
        except Exception:
            # Don't expose provider bodies, secret-bearing requests or exceptions.
            raise ServiceMessageError("line_response_unknown") from None

    def channel_token(self):
        value = self.request("/oauth2/v3/token", data={"grant_type": "client_credentials",
            "client_id": self.cfg.line_miniapp_channel_id,
            "client_secret": self.cfg.line_miniapp_channel_secret.get_secret_value()})
        token = value.get("access_token") if isinstance(value, dict) else None
        if not isinstance(token, str) or not 1 <= len(token) <= 8192:
            raise ServiceMessageError("invalid_line_response")
        return token

    def issue(self, channel_token, liff_token):
        return token_data(self.request("/message/v3/notifier/token",
            headers={"Authorization": f"Bearer {channel_token}"},
            json={"liffAccessToken": liff_token}))

    def send(self, channel_token, notification_token, report_id):
        # Only the required button. Do not advertise unsupported edit/cancel actions.
        link = (f"https://miniapp.line.me/{self.cfg.line_miniapp_liff_id}"
                f"?section=report&reportId={report_id}")
        return token_data(self.request("/message/v3/notifier/send?target=service",
            headers={"Authorization": f"Bearer {channel_token}"},
            json={"templateName": TEMPLATE, "notificationToken": notification_token,
                  "params": {"btn1_url": link}}),
            exhausted_allowed=True)


def http_client():
    # Synchronous, bounded calls run in an API worker thread or the local CLI.
    return httpx.Client(timeout=4, follow_redirects=False, trust_env=False)


def register_notification(db, cfg, report_id, user_id, liff_token, client_factory=http_client,
                          *, issue_token=None):
    configuration(cfg, user_id)
    validate_id(report_id)
    if not isinstance(liff_token, str) or not 1 <= len(liff_token) <= 8192:
        raise ServiceMessageError("invalid_session")
    # Raw LIFF tokens never go to Firestore. One reservation per verified session.
    key = hashlib.sha256(f"{cfg.line_miniapp_channel_id}:{user_id}:{liff_token}".encode()).hexdigest()
    report_ref = db.collection(REPORTS).document(report_id)
    session_ref = db.collection(SESSIONS).document(key)

    def reserve(tx):
        report, session = read_many(db, [report_ref, session_ref], tx)
        if not report or report.get("reporter_id") != user_id:
            raise HTTPException(404, "Report not found")
        if report.get("status") != "pending":
            raise ServiceMessageError("report_not_pending")
        previous = report.get("notification_session")
        if previous and previous != key:
            # Never silently replace a report's original notification session.
            raise ServiceMessageError("session_already_bound")
        if session and (session.get("reporter_id") != user_id
                        or session.get("channel_id") != cfg.line_miniapp_channel_id):
            raise ServiceMessageError("session_owner_mismatch")
        if not session:
            tx.set(session_ref, {"reporter_id": user_id, "channel_id": cfg.line_miniapp_channel_id,
                                 "state": "issuing", "created_at": now()})
        tx.update(report_ref, {"notification_session": key})
        if not session:
            return "issue"
        expires = session.get("expires_at")
        if (session.get("state") == "ready" and isinstance(expires, datetime)
                and expires.tzinfo is not None and expires > now()
                and type(session.get("remaining_count")) is int and session["remaining_count"] > 0):
            return "ready"
        return "unavailable"

    action = transaction(db, reserve)
    if action != "issue":
        return "ready" if action == "ready" else "unavailable"
    # A failed issuance or lost DB response must never trigger a second issuance.
    try:
        if issue_token is None:
            with client_factory() as client:
                line = LineServiceClient(cfg, client)
                value = line.issue(line.channel_token(), liff_token)
        else:
            # Submission acknowledgement reuses the same HTTP client/channel
            # token for issuance and sending, just three LINE calls in total.
            value = issue_token(liff_token)
        session_ref.update({**value, "state": "ready"}, timeout=4, retry=None)
        return "ready"
    except Exception:
        # The issuing reservation itself safely blocks retries, even if this fails.
        try:
            session_ref.update({"state": "unknown"}, timeout=4, retry=None)
        except Exception:
            pass
        return "unavailable"


def complete_review(db, report_id, reviewer, result, note):
    validate_id(report_id)
    if (not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80
            or result not in RESULTS or not isinstance(note, str)
            or not 1 <= len(note.strip()) <= 1000):
        raise ServiceMessageError("invalid_review")
    reference = db.collection(REPORTS).document(report_id)
    fields = {"reviewer": reviewer.strip(), "review_result": result, "review_note": note.strip()}

    def complete(tx):
        report = read(reference, tx)
        if not report:
            raise ServiceMessageError("report_not_found")
        if report.get("status") == "reviewed":
            if any(report.get(key) != value for key, value in fields.items()):
                raise ServiceMessageError("review_already_completed")
            return
        if report.get("status") != "pending":
            raise ServiceMessageError("invalid_report_state")
        tx.update(reference, {**fields, "status": "reviewed", "reviewed_at": now()})
    transaction(db, complete)


def send_receipt_notification(db, cfg, report_id, user_id, liff_token, client_factory=http_client):
    configuration(cfg, user_id)
    validate_id(report_id)
    report = owned_report(db, report_id, user_id)
    if report.get("receipt_notification_state") == "sent":
        return "already_sent"
    if report.get("receipt_notification_state") in {"sending", "unknown"}:
        raise ServiceMessageError("delivery_unknown_no_retry")
    report_ref = db.collection(REPORTS).document(report_id)
    claim = uuid4().hex

    def reserve(tx):
        report = read(report_ref, tx)
        if not report or report.get("reporter_id") != user_id:
            raise HTTPException(404, "Report not found")
        if report.get("receipt_notification_state") == "sent":
            return None
        if report.get("receipt_notification_state") in {"sending", "unknown"}:
            raise ServiceMessageError("delivery_unknown_no_retry")
        if report.get("status") != "pending":
            raise ServiceMessageError("report_not_pending")
        configuration(cfg, report.get("reporter_id"))
        key = report.get("notification_session")
        if not isinstance(key, str) or not ID_PATTERN.fullmatch(key):
            raise ServiceMessageError("notification_session_missing")
        session_ref = db.collection(SESSIONS).document(key)
        session = read(session_ref, tx)
        if (session.get("reporter_id") != report.get("reporter_id")
                or session.get("channel_id") != cfg.line_miniapp_channel_id):
            raise ServiceMessageError("session_owner_mismatch")
        expires = session.get("expires_at")
        if (session.get("state") != "ready" or not isinstance(expires, datetime)
                or expires.tzinfo is None or expires <= now()
                or type(session.get("remaining_count")) is not int
                or session["remaining_count"] <= 0 or not session.get("notification_token")):
            raise ServiceMessageError("notification_session_unavailable")
        # Locks the whole rotating token, not just this report. Concurrent receipts
        # from the same LIFF session cannot send with a stale token.
        tx.update(session_ref, {"state": "sending", "claim": claim})
        tx.update(report_ref, {"receipt_notification_state": "sending", "receipt_notification_claim": claim})
        return session_ref, session

    # Get credentials BEFORE reserving a send. Safe failures here don't consume it.
    with client_factory() as client:
        line = LineServiceClient(cfg, client)
        token = None

        def channel_token():
            nonlocal token
            if token is None:
                token = line.channel_token()
            return token

        registered = register_notification(db, cfg, report_id, user_id, liff_token,
            issue_token=lambda raw: line.issue(channel_token(), raw))
        if registered != "ready":
            raise ServiceMessageError("notification_session_unavailable")
        bearer = channel_token()
        reserved = transaction(db, reserve)
        if reserved is None:
            return "already_sent"
        session_ref, session = reserved
        try:
            value = line.send(bearer, session["notification_token"], report_id)
            if (value["line_session_id"] != session.get("line_session_id")
                    or value["remaining_count"] >= session["remaining_count"]):
                raise ServiceMessageError("invalid_line_response")

            def persist(tx):
                current_report, current_session = read_many(db, [report_ref, session_ref], tx)
                if (current_report.get("receipt_notification_claim") != claim
                        or current_session.get("claim") != claim):
                    raise ServiceMessageError("delivery_claim_lost")
                tx.update(session_ref, {**value, "state": "ready" if value["remaining_count"] else "exhausted"})
                tx.update(report_ref, {"receipt_notification_state": "sent", "receipt_notified_at": now()})
            transaction(db, persist)
            return "sent"
        except Exception:
            # Retain the durable sending locks. A timeout/crash may have delivered
            # the message or rotated its token. There is no automatic retry/reset.
            raise ServiceMessageError("delivery_unknown_no_retry") from None
