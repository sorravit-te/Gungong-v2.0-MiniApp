"""Opt-in, immutable, bounded scan snapshots; never make personal History public."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException
from google.api_core.exceptions import AlreadyExists

from ..core.models import COLLECTION_HISTORY

COLLECTION = "history_shares"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
ENTRY = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
VERDICTS = {"NO_THREAT_FOUND", "SUSPICIOUS", "MALICIOUS", "INCOMPLETE", "INVALID"}


def now():
    return datetime.now(timezone.utc)


def reference(db, token):
    if not TOKEN.fullmatch(token):
        raise HTTPException(404, "Share unavailable")
    # The bearer link is never stored in plaintext or used as the document ID.
    return db.collection(COLLECTION).document(hashlib.sha256(token.encode()).hexdigest())


def verdict(data):
    check = data.get("url_check_result") or {}
    if not isinstance(check, dict):
        check = {}
    value = data.get("verification_verdict") or check.get("verification_verdict")
    if value:
        return value if value in VERDICTS else "INCOMPLETE"
    fallback = {"VERIFICATION_INCOMPLETE": "INCOMPLETE", "INVALID_URL": "INVALID",
                "SUSPICIOUS_URL": "SUSPICIOUS", "SCAM_MALICIOUS": "MALICIOUS"}
    if data.get("type") in {"link", "qr"} and data.get("classification") in fallback:
        return fallback[data["classification"]]
    if data.get("is_fraud") is True or data.get("has_malicious_urls") is True or check.get("is_dangerous") is True:
        return "SUSPICIOUS"
    if data.get("is_safe") is True or (data.get("is_fraud") is False and data.get("is_safe") is not False):
        return "NO_THREAT_FOUND"
    return "INCOMPLETE"


def shared_content(value, kind):
    """Minimize common identifiers, not a guarantee of complete anonymization."""
    value = value if isinstance(value, str) else ""
    value = value[:5000]
    # URLs are non-clickable host names only: omit credentials, paths, queries,
    # fragments and reset/payment tokens. Never fetch the reported destination.
    def host(match):
        try:
            return "[โดเมน: " + (urlsplit(match.group()).hostname or "ไม่ระบุ")[:180] + "]"
        except ValueError:
            return "[ลิงก์]"
    value = re.sub(r"https?://[^\s<>]+", host, value, flags=re.I)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[อีเมล]", value)
    if kind in {"bank", "phone"}:
        digits = re.sub(r"\D", "", value)
        return "••••" + digits[-4:] if digits else "[ข้อมูลที่ตรวจสอบ]"
    value = re.sub(r"(?<!\w)(?:\d[ -]?){7,}\d(?!\w)", "[หมายเลขส่วนบุคคล]", value)
    value = " ".join(value.split())
    return value[:240] + ("…" if len(value) > 240 else "")


def timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def snapshot(data, include_content):
    kind = data.get("type")
    if kind not in {"link", "qr", "text", "sms", "message", "bank", "phone"}:
        kind = "unknown"
    return {"type": kind, "verdict": verdict(data),
            "content": shared_content(data.get("message_text"), kind) if include_content else "",
            "scanned_at": timestamp(data.get("created_at"))}


def active(data):
    expires = data.get("expires_at")
    return (data.get("revoked") is False and isinstance(expires, datetime)
            and expires.tzinfo is not None and expires > now())


def public(data):
    if not active(data):
        raise HTTPException(404, "Share unavailable")
    # Re-project on reads too; no IDs, raw provider evidence, profile or tokens.
    view = data.get("snapshot") or {}
    if not isinstance(view, dict) or view.get("verdict") not in VERDICTS:
        raise HTTPException(404, "Share unavailable")
    return {"snapshot": {key: view.get(key) for key in ("type", "verdict", "content", "scanned_at")},
            "expires_at": timestamp(data["expires_at"])}


def create_share(db, entry_id, token, include_content, user_id):
    if not ENTRY.fullmatch(entry_id):
        raise HTTPException(404, "History unavailable")
    ref = reference(db, token)
    entry = db.collection(COLLECTION_HISTORY).document(entry_id).get(timeout=3, retry=None).to_dict() or {}
    if entry.get("user_id") != user_id:
        raise HTTPException(404, "History unavailable")
    data = {"owner_id": user_id, "entry_id": entry_id, "include_content": include_content,
            "snapshot": snapshot(entry, include_content), "created_at": now(),
            "expires_at": now() + timedelta(days=7), "revoked": False}
    try:
        ref.create(data, timeout=3, retry=None)
    except AlreadyExists:
        previous = ref.get(timeout=3, retry=None).to_dict() or {}
        if any(previous.get(key) != data[key] for key in ("owner_id", "entry_id", "include_content")):
            raise HTTPException(409, "Share token already used") from None
        data = previous  # Retries never overwrite the snapshot or extend expiry.
    return public(data)


def read_share(db, token):
    return public(reference(db, token).get(timeout=3, retry=None).to_dict() or {})


def revoke_share(db, token, user_id):
    ref = reference(db, token)
    data = ref.get(timeout=3, retry=None).to_dict() or {}
    if data.get("owner_id") != user_id:
        raise HTTPException(404, "Share unavailable")
    ref.update({"revoked": True}, timeout=3, retry=None)
    return {"revoked": True}
