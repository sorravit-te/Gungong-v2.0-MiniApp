"""Opt-in Google URL threat-list evidence, not proof of benign page content."""

import asyncio
import math
from datetime import datetime, timezone
from datetime import timedelta
from time import monotonic

import httpx

from ..core.config import settings
from ..core.performance_config import get_performance_config


class URLReputationService:
    def __init__(self, *, provider=None, api_key=None, client_factory=None):
        self.provider = provider if provider is not None else settings.url_reputation_provider
        self.api_key = api_key if api_key is not None else settings.url_reputation_api_key
        self.timeout = get_performance_config().URL_REPUTATION_TIMEOUT
        self.client_factory = client_factory or (lambda: httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=False, trust_env=False,
            headers={"X-Goog-Api-Key": self.api_key or ""},
        ))
        self._cache = {}

    async def check_urls(self, urls):
        if self.provider == "disabled":
            return {"status": "skipped_not_needed", "complete": None, "reason": "provider_not_enabled"}
        if self.provider not in {"safe_browsing", "web_risk"} or not self.api_key:
            return {"status": "unavailable", "complete": False, "source": self.provider}
        try:
            results = await asyncio.wait_for(self._check_urls(list(dict.fromkeys(urls))), timeout=self.timeout)
            # A partial lookup cannot erase a completed positive result.
            positive = next((item for item in results if item["status"] == "malicious"), None)
            if positive:
                return positive
            failure = next((item for item in results if item.get("complete") is not True), None)
            return failure or {"status": "not_listed", "complete": True, "source": self.provider,
                               "evidence_expires_at": min(item["evidence_expires_at"] for item in results)}
        except (asyncio.TimeoutError, httpx.TimeoutException):
            return {"status": "timeout", "complete": False, "source": self.provider}
        except Exception:
            return {"status": "error", "complete": False, "source": self.provider}

    async def _check_urls(self, urls):
        # Sequential bounded lookups avoid launching work after a known threat.
        results = []
        async with self.client_factory() as client:
            for url in urls:
                result = await self._lookup(client, url)
                results.append(result)
                if result["status"] == "malicious":
                    break
        return results

    async def _lookup(self, client, url):
        cached = self._cache.get(url)
        if cached and cached[0] > monotonic():
            return {**cached[1], "cached": True}
        if self.provider == "safe_browsing":
            endpoint = "https://safebrowsing.googleapis.com/v5/urls:search"
            params = [("urls", url)]
        else:
            endpoint = "https://webrisk.googleapis.com/v1/uris:search"
            params = [("uri", url)] + [("threatTypes", value) for value in ("MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE")]
        response = await client.get(endpoint, params=params)
        if response.status_code != 200:
            status = "rate_limited" if response.status_code == 429 else "unavailable" if response.status_code >= 500 else "error"
            return {"status": status, "complete": False, "source": self.provider}
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid reputation schema")
        if self.provider == "safe_browsing":
            threats = data.get("threats", [])
            if not isinstance(threats, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("url"), str) or not item["url"]
                or not isinstance(item.get("threatTypes"), list) or not item["threatTypes"]
                for item in threats
            ):
                raise ValueError("Invalid reputation threats")
            types = [value for item in threats for value in item["threatTypes"]]
            duration = data.get("cacheDuration")
            if not isinstance(duration, str) or not duration.endswith("s"):
                raise ValueError("Missing provider cache duration")
            ttl = float(duration[:-1])
        else:
            threat = data.get("threat", {})
            if not isinstance(threat, dict):
                raise ValueError("Invalid reputation threat")
            types = threat.get("threatTypes", [])
            ttl = 60.0  # short miss cache, never a clean evidence cache
            if types:
                expires = datetime.fromisoformat(threat["expireTime"].replace("Z", "+00:00"))
                ttl = (expires - datetime.now(timezone.utc)).total_seconds()
        if not isinstance(types, list) or any(not isinstance(value, str) or not value for value in types):
            raise ValueError("Invalid reputation threat types")
        if not math.isfinite(ttl) or ttl < 0:
            raise ValueError("Invalid reputation expiry")
        result = {"status": "malicious" if types else "not_listed", "complete": True,
                  "source": self.provider, "threat_types": sorted(set(types)), "checked_url": url,
                  "evidence_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=min(ttl, 86400))).isoformat()}
        # Bounded memory; honor the provider expiry, never extend a match.
        if len(self._cache) >= 1024:
            self._cache.pop(next(iter(self._cache)))
        self._cache[url] = (monotonic() + min(ttl, 86400), result)
        return result


_service = None


def get_url_reputation_service():
    global _service
    if _service is None:
        _service = URLReputationService()
    return _service
