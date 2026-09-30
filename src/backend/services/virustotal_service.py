"""Bounded, cached VirusTotal URL evidence for the free public API tier."""

from __future__ import annotations

import asyncio
import base64
import re
from collections import deque
from dataclasses import asdict, dataclass
from datetime import date
from time import monotonic
from typing import Dict, List, Optional

import httpx

from ..core.config import settings
from ..core.performance_config import get_performance_config
from .gambling_detector_service import get_gambling_detector
from .url_safety_service import URLSafetyError, normalize_public_url


COMPLETED_STATUSES = {"clean", "malicious", "suspicious"}


@dataclass(frozen=True)
class VirusTotalResult:
    status: str
    url: str
    malicious_count: int = 0
    suspicious_count: int = 0
    total_scanners: int = 0
    positives_details: tuple[str, ...] = ()
    cached: bool = False
    provider: str = "virustotal"

    @property
    def is_malicious(self) -> bool:
        return self.status == "malicious"

    @property
    def is_suspicious(self) -> bool:
        return self.status == "suspicious"

    @property
    def is_complete(self) -> bool:
        return self.status in COMPLETED_STATUSES

    def to_dict(self) -> dict:
        data = asdict(self)
        data["positives_details"] = list(self.positives_details)
        data["is_malicious"] = self.is_malicious
        data["is_suspicious"] = self.is_suspicious
        data["complete"] = self.is_complete
        return data


class VirusTotalService:
    """Best-effort evidence provider with normalized caching and quota guards."""

    BASE_URL = "https://www.virustotal.com/api/v3"
    URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

    def __init__(self, api_key: Optional[str] = None, *, submit_unknown: Optional[bool] = None, client_factory=None):
        config = get_performance_config()
        self.api_key = api_key if api_key is not None else settings.virustotal_api_key
        self.submit_unknown = settings.virustotal_submit_unknown_urls if submit_unknown is None else submit_unknown
        self.timeout = config.VIRUSTOTAL_TIMEOUT
        self.cache_ttl = config.URL_CACHE_TTL_DAYS * 86400
        self.not_found_cache_ttl = config.VIRUSTOTAL_NOT_FOUND_CACHE_TTL_SECONDS
        self.requests_per_minute = config.VIRUSTOTAL_REQUESTS_PER_MINUTE
        self.requests_per_day = config.VIRUSTOTAL_REQUESTS_PER_DAY
        self.cooldown_seconds = config.VIRUSTOTAL_RATE_LIMIT_COOLDOWN
        self.client_factory = client_factory or self._default_client
        self._cache: dict[str, tuple[float, VirusTotalResult]] = {}
        self._inflight: dict[str, asyncio.Task] = {}
        self._inflight_waiters: dict[str, int] = {}
        self._request_times: deque[float] = deque()
        self._daily_date = date.today()
        self._daily_count = 0
        self._cooldown_until = 0.0
        self._inflight_lock = asyncio.Lock()
        self._rate_lock = asyncio.Lock()

    def _default_client(self):
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=False,
            trust_env=False,
            headers={"accept": "application/json", "x-apikey": self.api_key or ""},
        )

    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        return list(dict.fromkeys(cls.URL_PATTERN.findall(text or "")))

    def _cached_result(self, key: str) -> Optional[VirusTotalResult]:
        cached = self._cache.get(key)
        if not cached:
            return None
        created_at, result = cached
        ttl = self.cache_ttl if result.status in COMPLETED_STATUSES else self.not_found_cache_ttl
        if monotonic() - created_at >= ttl:
            self._cache.pop(key, None)
            return None
        return VirusTotalResult(**{**asdict(result), "cached": True})

    async def _reserve_request(self) -> bool:
        async with self._rate_lock:
            now = monotonic()
            if now < self._cooldown_until:
                return False
            today = date.today()
            if today != self._daily_date:
                self._daily_date = today
                self._daily_count = 0
            while self._request_times and now - self._request_times[0] >= 60:
                self._request_times.popleft()
            if len(self._request_times) >= self.requests_per_minute or self._daily_count >= self.requests_per_day:
                return False
            self._request_times.append(now)
            self._daily_count += 1
            return True

    async def _start_cooldown(self) -> None:
        async with self._rate_lock:
            self._cooldown_until = max(self._cooldown_until, monotonic() + self.cooldown_seconds)

    async def check_url_evidence_async(self, url: str) -> VirusTotalResult:
        try:
            normalized = normalize_public_url(url)
        except URLSafetyError:
            return VirusTotalResult(status="error", url=str(url))
        cached = self._cached_result(normalized)
        if cached:
            return cached
        if not self.api_key or self.api_key == "your_virustotal_api_key_here":
            return VirusTotalResult(status="unavailable", url=normalized)

        async with self._inflight_lock:
            cached = self._cached_result(normalized)
            if cached:
                return cached
            task = self._inflight.get(normalized)
            if task is None:
                task = asyncio.create_task(self._lookup(normalized))
                self._inflight[normalized] = task
            self._inflight_waiters[normalized] = self._inflight_waiters.get(normalized, 0) + 1
        cancel_orphan = False
        try:
            # A timeout in one HTTP request must not cancel evidence that another
            # concurrent request is still awaiting.
            result = await asyncio.shield(task)
        finally:
            async with self._inflight_lock:
                remaining = self._inflight_waiters.get(normalized, 1) - 1
                if remaining > 0:
                    self._inflight_waiters[normalized] = remaining
                else:
                    self._inflight_waiters.pop(normalized, None)
                    if self._inflight.get(normalized) is task:
                        self._inflight.pop(normalized, None)
                        if not task.done():
                            task.cancel()
                            cancel_orphan = True
            if cancel_orphan:
                await asyncio.gather(task, return_exceptions=True)
        if result.status in COMPLETED_STATUSES or result.status == "not_found":
            self._cache[normalized] = (monotonic(), result)
        return result

    async def _lookup(self, normalized: str) -> VirusTotalResult:
        if not await self._reserve_request():
            return VirusTotalResult(status="rate_limited", url=normalized)
        url_id = base64.urlsafe_b64encode(normalized.encode("utf-8")).decode("ascii").rstrip("=")
        try:
            async with self.client_factory() as client:
                response = await client.get(f"{self.BASE_URL}/urls/{url_id}")
                if response.status_code == 429:
                    await self._start_cooldown()
                    return VirusTotalResult(status="rate_limited", url=normalized)
                if response.status_code == 404:
                    if not self.submit_unknown:
                        return VirusTotalResult(status="not_found", url=normalized)
                    return await self._submit(client, normalized)
                if response.status_code >= 500:
                    return VirusTotalResult(status="unavailable", url=normalized)
                if response.status_code >= 400:
                    return VirusTotalResult(status="error", url=normalized)
                try:
                    attributes = response.json()["data"]["attributes"]
                    stats = attributes["last_analysis_stats"]
                    if not isinstance(stats, dict) or not stats:
                        return VirusTotalResult(status="error", url=normalized)
                    malicious = int(stats.get("malicious", 0))
                    suspicious = int(stats.get("suspicious", 0))
                    total = sum(int(value) for value in stats.values())
                    positives = tuple(
                        name for name, details in attributes.get("last_analysis_results", {}).items()
                        if details.get("category") in {"malicious", "suspicious"}
                    )[:5]
                except (KeyError, TypeError, ValueError):
                    return VirusTotalResult(status="error", url=normalized)
                status = "malicious" if malicious > 0 else "suspicious" if suspicious > 0 else "clean"
                return VirusTotalResult(status, normalized, malicious, suspicious, total, positives)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return VirusTotalResult(status="timeout", url=normalized)
        except httpx.HTTPError:
            return VirusTotalResult(status="unavailable", url=normalized)
        except Exception:
            return VirusTotalResult(status="error", url=normalized)

    async def _submit(self, client, normalized: str) -> VirusTotalResult:
        if not await self._reserve_request():
            return VirusTotalResult(status="rate_limited", url=normalized)
        try:
            response = await client.post(
                f"{self.BASE_URL}/urls",
                data={"url": normalized},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 429:
                await self._start_cooldown()
                return VirusTotalResult(status="rate_limited", url=normalized)
            if response.status_code >= 500:
                return VirusTotalResult(status="unavailable", url=normalized)
            if response.status_code >= 400:
                return VirusTotalResult(status="error", url=normalized)
            return VirusTotalResult(status="pending", url=normalized)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return VirusTotalResult(status="timeout", url=normalized)
        except httpx.HTTPError:
            return VirusTotalResult(status="unavailable", url=normalized)

    async def check_text_for_malicious_urls_async(self, text: str) -> Dict:
        urls = self.extract_urls(text)
        if not urls:
            return {"has_urls": False, "urls_found": [], "malicious_urls": [], "gambling_urls": [], "is_dangerous": False, "details": []}
        results = await asyncio.gather(*(self._check_text_url(url) for url in urls))
        malicious = [result["url"] for result in results if result["status"] == "malicious"]
        suspicious = [result["url"] for result in results if result["status"] == "suspicious"]
        gambling = [result["url"] for result in results if result["is_gambling"]]
        return {
            "has_urls": True,
            "urls_found": urls,
            "malicious_urls": malicious,
            "suspicious_urls": suspicious,
            "gambling_urls": gambling,
            "is_dangerous": bool(malicious or suspicious or gambling),
            "verification_complete": all(result.get("complete") is True for result in results),
            "details": results,
        }

    async def _check_text_url(self, url: str) -> Dict:
        """Preserve text-message gambling heuristics without outbound scraping."""
        vt_result = await self.check_url_evidence_async(url)
        try:
            gambling_result = await get_gambling_detector().check_url_async(
                url,
                scrape_content=False,
                use_headless_if_needed=False,
            )
        except Exception:
            gambling_result = {"is_gambling": False, "confidence": 0, "keywords_found": []}
        details = vt_result.to_dict()
        details.update({
            "is_gambling": gambling_result.get("is_gambling", False),
            "gambling_confidence": gambling_result.get("confidence", 0),
            "gambling_keywords": gambling_result.get("keywords_found", []),
            "detections": f"{vt_result.malicious_count}/{vt_result.total_scanners}",
            "scanners": list(vt_result.positives_details),
        })
        return details

    def check_url(self, url: str) -> VirusTotalResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.check_url_evidence_async(url))
        normalized = normalize_public_url(url)
        return self._cached_result(normalized) or VirusTotalResult("unavailable", normalized)

    def check_text_for_malicious_urls(self, text: str) -> Dict:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.check_text_for_malicious_urls_async(text))
        urls = self.extract_urls(text)
        results = [self.check_url(url) for url in urls]
        return {
            "has_urls": bool(urls),
            "urls_found": urls,
            "malicious_urls": [result.url for result in results if result.status == "malicious"],
            "gambling_urls": [],
            "is_dangerous": any(result.status in {"malicious", "suspicious"} for result in results),
            "verification_complete": all(result.is_complete for result in results),
            "details": [result.to_dict() for result in results],
        }


_virustotal_service: Optional[VirusTotalService] = None


def get_virustotal_service() -> VirusTotalService:
    global _virustotal_service
    if _virustotal_service is None:
        _virustotal_service = VirusTotalService()
    return _virustotal_service
