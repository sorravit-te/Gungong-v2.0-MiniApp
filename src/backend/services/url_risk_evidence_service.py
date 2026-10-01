"""Bounded, positive-only risk memory shared by fresh and cached URL checks."""

import asyncio
import hashlib
import logging
from time import monotonic
from weakref import WeakKeyDictionary
from datetime import datetime, timedelta, timezone

from ..core.performance_config import get_performance_config


_memory = WeakKeyDictionary()
logger = logging.getLogger(__name__)


def _key(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


async def lookup_recent_risk(db, urls: list[str]) -> dict:
    if db is None:
        return {"status": "unavailable", "complete": False, "required": True}
    observations = _memory.get(db, {})
    for url in urls:
        item = observations.get(_key(url))
        if item and item[0] > monotonic():
            return {**item[1], "required": False, "source": "recent_risk_evidence", "storage": "process_memory"}
    config = get_performance_config()
    results = []
    # Start concurrently only within this core stage, not speculative AI/VT.
    # Each synchronous RPC has its own timeout with retries disabled.
    try:
        results = await asyncio.wait_for(asyncio.gather(*(
            asyncio.to_thread(db.get_url_risk_evidence, url) for url in dict.fromkeys(urls)
        )), timeout=config.URL_RISK_LOOKUP_TIMEOUT)
    except asyncio.TimeoutError:
        return {"status": "timeout", "complete": False, "required": True}
    except Exception:
        return {"status": "error", "complete": False, "required": True}
    positive = next((item for item in results if item.get("status") == "suspicious"), None)
    if positive:
        return {**positive, "required": False, "source": "recent_risk_evidence"}
    failures = [item for item in results if item.get("complete") is not True]
    if failures:
        # Preserve sanitized diagnostic fields; never return exception text/URLs.
        diagnostic = {key: failures[0][key] for key in (
            "reason", "error_type", "timeout_seconds", "elapsed_ms",
        ) if key in failures[0]}
        return {**diagnostic, "status": "timeout" if all(item.get("status") == "timeout" for item in failures) else "error",
                "complete": False, "required": True}
    return {"status": "not_listed", "complete": True, "required": True, "source": "recent_risk_evidence"}


async def save_recent_risk(db, response: dict, *, persist: bool = True) -> bool:
    if db is None:
        return False
    evidence = {}
    targets = {}
    keys = ("status", "provider_status", "reason", "source", "malicious_count", "suspicious_count", "total_scanners", "analysis_timestamp")
    for name, details in response.get("checks", {}).items():
        # Never re-save inherited observations: repeated scans must not extend
        # their expiry. Only newly obtained, completed source evidence counts.
        if name in {"risk_history", "route"} or details.get("cached") is True:
            continue
        if details.get("status") in {"malicious", "suspicious"} and details.get("complete") is True:
            evidence[name] = {key: details[key] for key in keys if key in details}
            targets[name] = details.get("checked_url") or details.get("url") or response.get("final_url")
    if not evidence:
        return False
    config = get_performance_config()
    weak = set(evidence) == {"virustotal"} and evidence["virustotal"].get("malicious_count", 0) <= 1
    ttl = config.URL_WEAK_RISK_TTL_SECONDS if weak else config.URL_RISK_TTL_SECONDS
    for name in evidence:
        expires = response["checks"][name].get("evidence_expires_at")
        if expires:
            try:
                ttl = min(ttl, (datetime.fromisoformat(expires) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                return False
    if ttl <= 0:
        return False
    urls = list(dict.fromkeys(url for url in (response.get("original_url"), response.get("final_url")) if url))
    writes = [(url, {name: item for name, item in evidence.items()
                     if url == response.get("original_url") or targets[name] == url})
              for url in urls if url == response.get("original_url") or url in targets.values()]
    observations = _memory.setdefault(db, {})
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
    for url, relevant in writes:
        existing = observations.get(_key(url))
        if existing and existing[0] >= monotonic()+ttl:
            continue
        if len(observations) >= 1024:
            observations.pop(next(iter(observations)))
        observations[_key(url)] = (monotonic()+ttl, {
            "status": "suspicious", "complete": True, "reason": "recent_detection_requires_confirmation",
            "evidence": relevant, "expires_at": expires_at,
        })
    if not persist:
        return False
    try:
        saved = await asyncio.wait_for(asyncio.gather(*(
            asyncio.to_thread(db.save_url_risk_evidence, url, relevant, ttl) for url, relevant in writes
        )), timeout=config.URL_RISK_LOOKUP_TIMEOUT)
        persisted = bool(saved) and all(saved)
        if not persisted:
            logger.warning("url_risk_save outcome=process_memory_only")
        return persisted
    except Exception:
        logger.warning("url_risk_save outcome=process_memory_only")
        return False
