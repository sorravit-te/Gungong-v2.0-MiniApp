"""VirusTotal evidence semantics, caching, and free-tier guard tests."""

import asyncio
import unittest

import httpx

from src.backend.services.virustotal_service import VirusTotalService


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeClient:
    def __init__(self, get_results, post_results=None):
        self.get_results = list(get_results)
        self.post_results = list(post_results or [])
        self.get_calls = 0
        self.post_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, _url):
        self.get_calls += 1
        result = self.get_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    async def post(self, _url, **_kwargs):
        self.post_calls += 1
        result = self.post_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def completed(stats):
    return FakeResponse(200, {
        "data": {"attributes": {"last_analysis_stats": stats, "last_analysis_results": {}}},
    })


class VirusTotalTests(unittest.IsolatedAsyncioTestCase):
    async def check(self, response, **kwargs):
        client = FakeClient([response], kwargs.pop("post_results", None))
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client, **kwargs)
        return await service.check_url_evidence_async("https://example.com/path"), client

    async def test_completed_clean_malicious_and_suspicious_semantics(self):
        cases = [
            ({"harmless": 70, "malicious": 0, "suspicious": 0}, "clean"),
            ({"harmless": 69, "malicious": 1, "suspicious": 0}, "malicious"),
            ({"harmless": 69, "malicious": 0, "suspicious": 1}, "suspicious"),
        ]
        for stats, expected in cases:
            with self.subTest(expected=expected):
                result, _ = await self.check(completed(stats))
                self.assertEqual(result.status, expected)
                self.assertTrue(result.is_complete)

    async def test_not_found_is_not_submitted_by_default(self):
        result, client = await self.check(FakeResponse(404))
        self.assertEqual(result.status, "not_found")
        self.assertFalse(result.is_complete)
        self.assertEqual(client.post_calls, 0)

    async def test_empty_or_failed_scanner_set_is_not_clean(self):
        for stats in [{'harmless': 0, 'undetected': 0}, {'timeout': 92}, {'harmless': -1}, {'harmless': True}]:
            result, _ = await self.check(completed(stats))
            self.assertNotEqual(result.status, 'clean')
            self.assertFalse(result.is_complete)

    async def test_completed_report_preserves_analysis_timestamp(self):
        response = completed({'harmless': 70})
        response.payload['data']['attributes']['last_analysis_date'] = 1700000000
        result, _ = await self.check(response)
        self.assertEqual(result.analysis_timestamp, 1700000000)

    async def test_not_found_is_short_cached_without_becoming_complete(self):
        client = FakeClient([FakeResponse(404)])
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client)
        first = await service.check_url_evidence_async("HTTPS://Example.COM:443")
        second = await service.check_url_evidence_async("https://example.com/")
        self.assertEqual(first.status, "not_found")
        self.assertFalse(first.is_complete)
        self.assertEqual(second.status, "not_found")
        self.assertFalse(second.is_complete)
        self.assertTrue(second.cached)
        self.assertFalse(second.to_dict()["complete"])
        self.assertEqual(client.get_calls, 1)

    async def test_opt_in_submission_returns_pending_not_clean(self):
        result, client = await self.check(FakeResponse(404), submit_unknown=True, post_results=[FakeResponse(200, {})])
        self.assertEqual(result.status, "pending")
        self.assertFalse(result.is_complete)
        self.assertEqual(client.post_calls, 1)

    async def test_timeout_rate_limit_5xx_malformed_and_missing_key_are_not_clean(self):
        cases = [
            (httpx.ReadTimeout("slow"), {}, "timeout"),
            (FakeResponse(429), {}, "rate_limited"),
            (FakeResponse(503), {}, "unavailable"),
            (FakeResponse(200, {"unexpected": True}), {}, "error"),
            (FakeResponse(200, {"data": {"attributes": {"last_analysis_stats": {}}}}), {}, "error"),
        ]
        for response, kwargs, expected in cases:
            with self.subTest(expected=expected):
                result, _ = await self.check(response, **kwargs)
                self.assertEqual(result.status, expected)
                self.assertNotEqual(result.status, "clean")
                self.assertFalse(result.is_complete)

        missing = VirusTotalService(api_key="")
        result = await missing.check_url_evidence_async("https://example.com/")
        self.assertEqual(result.status, "unavailable")
        self.assertFalse(result.is_complete)

    async def test_local_free_tier_budget_and_429_cooldown_avoid_extra_requests(self):
        minute_client = FakeClient([FakeResponse(404)])
        minute_service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: minute_client)
        minute_service.requests_per_minute = 1
        first = await minute_service.check_url_evidence_async("https://one.example/")
        second = await minute_service.check_url_evidence_async("https://two.example/")
        self.assertEqual(first.status, "not_found")
        self.assertEqual(second.status, "rate_limited")
        self.assertEqual(minute_client.get_calls, 1)

        day_client = FakeClient([FakeResponse(404)])
        day_service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: day_client)
        day_service.requests_per_minute = 10
        day_service.requests_per_day = 1
        await day_service.check_url_evidence_async("https://one.example/")
        daily_deferred = await day_service.check_url_evidence_async("https://two.example/")
        self.assertEqual(daily_deferred.status, "rate_limited")
        self.assertEqual(day_client.get_calls, 1)

        cooldown_client = FakeClient([FakeResponse(429)])
        cooldown_service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: cooldown_client)
        limited = await cooldown_service.check_url_evidence_async("https://one.example/")
        deferred = await cooldown_service.check_url_evidence_async("https://two.example/")
        self.assertEqual(limited.status, "rate_limited")
        self.assertEqual(deferred.status, "rate_limited")
        self.assertEqual(cooldown_client.get_calls, 1, "429 must not trigger an immediate retry")

    async def test_completed_result_is_cached_by_normalized_url(self):
        client = FakeClient([completed({"harmless": 1, "malicious": 0, "suspicious": 0})])
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client)
        first = await service.check_url_evidence_async("HTTPS://Example.COM:443")
        second = await service.check_url_evidence_async("https://example.com/")
        self.assertEqual(first.status, "clean")
        self.assertTrue(second.cached)
        self.assertEqual(client.get_calls, 1)

    async def test_inflight_duplicate_uses_one_lookup(self):
        client = FakeClient([completed({"harmless": 1, "malicious": 0, "suspicious": 0})])
        original_get = client.get

        async def delayed_get(url):
            await asyncio.sleep(0.01)
            return await original_get(url)

        client.get = delayed_get
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client)
        one, two = await asyncio.gather(
            service.check_url_evidence_async("https://example.com/"),
            service.check_url_evidence_async("https://example.com/"),
        )
        self.assertEqual(one.status, "clean")
        self.assertEqual(two.status, "clean")
        self.assertEqual(client.get_calls, 1)

    async def test_cancelling_one_waiter_does_not_cancel_shared_lookup(self):
        client = FakeClient([completed({"harmless": 1, "malicious": 0, "suspicious": 0})])
        original_get = client.get

        async def delayed_get(url):
            await asyncio.sleep(0.03)
            return await original_get(url)

        client.get = delayed_get
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client)
        first = asyncio.create_task(service.check_url_evidence_async("https://example.com/"))
        second = asyncio.create_task(service.check_url_evidence_async("https://example.com/"))
        await asyncio.sleep(0.005)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        result = await second
        self.assertEqual(result.status, "clean")
        self.assertEqual(client.get_calls, 1)

    async def test_text_pipeline_keeps_legacy_shape_without_network_scraping(self):
        client = FakeClient([completed({"harmless": 1, "malicious": 0, "suspicious": 0})])
        service = VirusTotalService(api_key="synthetic-key", client_factory=lambda: client)
        result = await service.check_text_for_malicious_urls_async("ดู https://example.com/path")
        self.assertTrue(result["has_urls"])
        self.assertTrue(result["verification_complete"])
        self.assertFalse(result["is_dangerous"])
        self.assertEqual(result["details"][0]["status"], "clean")
        self.assertIn("detections", result["details"][0])


if __name__ == "__main__":
    unittest.main()
