"""Deterministic URL normalization, SSRF, and redirect-boundary tests."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock

import httpx

from src.backend.services.url_safety_service import (
    RedirectHTTPResponse,
    RedirectResolutionError,
    SafeRedirectResolver,
    URLSafetyError,
    is_public_address,
    normalize_public_url,
    validate_public_url,
)


async def public_dns(_hostname, _port):
    return ["93.184.216.34"]


class URLSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_normalizes_supported_public_url_shapes(self):
        cases = {
            "http://Example.COM": "http://example.com/",
            "https://example.com/path": "https://example.com/path",
            "https://example.com/a%2Fb?q=x%20y#part": "https://example.com/a%2Fb?q=x%20y#part",
            "https://bücher.example/": "https://xn--bcher-kva.example/",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_public_url(raw), expected)

    def test_rejects_malformed_and_unsupported_urls(self):
        for value in ["", "example.com", "http:///missing", "http://exa mple.com/", "http://-bad.example/", "file:///tmp/a", "javascript:alert(1)", "data:text/plain,x", "ftp://example.com/a"]:
            with self.subTest(value=value):
                with self.assertRaises(URLSafetyError):
                    normalize_public_url(value)

    def test_ipaddress_boundary_rejects_non_public_ranges(self):
        blocked = [
            "127.0.0.1",
            "::1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "100.64.0.1",
            "fc00::1",
            "fe80::1",
            "169.254.169.254",
            "0.0.0.0",
            "224.0.0.1",
            "192.0.2.1",
        ]
        for address in blocked:
            with self.subTest(address=address):
                self.assertFalse(is_public_address(address))
        self.assertTrue(is_public_address("93.184.216.34"))
        self.assertTrue(is_public_address("2606:4700:4700::1111"))

    async def test_rejects_hostname_when_any_dns_answer_is_private(self):
        async def mixed_dns(_hostname, _port):
            return ["93.184.216.34", "10.1.2.3"]

        with self.assertRaisesRegex(URLSafetyError, "non-public"):
            await validate_public_url("https://example.com/", mixed_dns)

    async def test_localhost_private_literals_ipv6_and_metadata_are_blocked(self):
        async def localhost_dns(_hostname, _port):
            return ["127.0.0.1"]

        async def literal_dns(hostname, _port):
            return [hostname]

        cases = [
            ("http://localhost/", localhost_dns),
            ("http://127.0.0.1/", literal_dns),
            ("http://192.168.10.20/", literal_dns),
            ("http://[::1]/", literal_dns),
            ("http://[fc00::1]/", literal_dns),
            ("http://169.254.169.254/latest/meta-data/", literal_dns),
        ]
        for url, resolver in cases:
            with self.subTest(url=url):
                with self.assertRaises(URLSafetyError):
                    await validate_public_url(url, resolver)

    async def test_no_redirect_and_unknown_domain_are_resolved_generically(self):
        calls = []

        async def requester(url, _timeout):
            calls.append(url)
            return RedirectHTTPResponse(200, {"content-type": "text/html"}, b"hello")

        result = await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://redirector.invalid/start")
        self.assertEqual(result.final_url, "https://redirector.invalid/start")
        self.assertEqual(result.redirect_count, 0)
        self.assertEqual(result.content_preview, "hello")
        self.assertTrue(result.client_redirect_checked)
        self.assertEqual(result.client_redirect_status, "none_found")
        self.assertEqual(calls, ["https://redirector.invalid/start"])

    async def test_meta_refresh_absolute_url_is_followed(self):
        responses = {
            "https://example.com/start": RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                b'<meta http-equiv="refresh" content="0; url=https://destination.test/final">',
            ),
            "https://destination.test/final": RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                b"final page",
            ),
        }

        async def requester(url, _timeout):
            return responses[url]

        result = await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://example.com/start")
        self.assertEqual(result.final_url, "https://destination.test/final")
        self.assertEqual(result.redirect_chain, list(responses))
        self.assertEqual(result.redirect_kinds, ("meta_refresh",))
        self.assertEqual(result.client_redirect_status, "followed")
        self.assertEqual(result.content_preview, "final page")

    async def test_meta_refresh_relative_url_is_followed(self):
        responses = {
            "https://example.com/a/start": RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                b"<META HTTP-EQUIV='Refresh' CONTENT='1; URL=../final?x=1&amp;y=2'>",
            ),
            "https://example.com/final?x=1&y=2": RedirectHTTPResponse(200, {"content-type": "text/plain"}, b"done"),
        }

        async def requester(url, _timeout):
            return responses[url]

        result = await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://example.com/a/start")
        self.assertEqual(result.final_url, "https://example.com/final?x=1&y=2")
        self.assertEqual(result.redirect_count, 1)

    async def test_meta_refresh_public_to_private_is_blocked_before_second_request(self):
        requested = []

        async def resolver(hostname, _port):
            return ["127.0.0.1"] if hostname == "private.test" else ["93.184.216.34"]

        async def requester(url, _timeout):
            requested.append(url)
            return RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                b'<meta http-equiv="refresh" content="0;url=http://private.test/admin">',
            )

        with self.assertRaisesRegex(URLSafetyError, "non-public"):
            await SafeRedirectResolver(resolver=resolver, requester=requester).resolve("https://example.com/start")
        self.assertEqual(requested, ["https://example.com/start"])

    async def test_meta_refresh_loop_is_rejected(self):
        async def requester(url, _timeout):
            target = "/b" if url.endswith("/a") else "/a"
            return RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                f'<meta http-equiv="refresh" content="0;url={target}">'.encode(),
            )

        with self.assertRaisesRegex(RedirectResolutionError, "loop"):
            await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://example.com/a")

    async def test_arbitrary_javascript_is_not_executed(self):
        requested = []

        async def requester(url, _timeout):
            requested.append(url)
            return RedirectHTTPResponse(
                200,
                {"content-type": "text/html"},
                b'<script>fetch("https://private.test/"); window.location="https://destination.test/"</script>',
            )

        result = await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://example.com/start")
        self.assertEqual(result.final_url, "https://example.com/start")
        self.assertEqual(result.client_redirect_status, "none_found")
        self.assertEqual(requested, ["https://example.com/start"])

    async def test_relative_and_multiple_redirects_record_chain(self):
        responses = {
            "https://example.com/start": RedirectHTTPResponse(302, {"location": "/middle"}),
            "https://example.com/middle": RedirectHTTPResponse(307, {"location": "https://destination.test/final?q=1"}),
            "https://destination.test/final?q=1": RedirectHTTPResponse(200, {}),
        }

        async def requester(url, _timeout):
            return responses[url]

        result = await SafeRedirectResolver(resolver=public_dns, requester=requester).resolve("https://example.com/start")
        self.assertEqual(result.final_url, "https://destination.test/final?q=1")
        self.assertEqual(result.redirect_count, 2)
        self.assertEqual(result.redirect_chain, list(responses))

    async def test_redirect_loop_and_excessive_redirects_are_rejected(self):
        async def loop_requester(url, _timeout):
            location = "/b" if url.endswith("/a") else "/a"
            return RedirectHTTPResponse(302, {"location": location})

        with self.assertRaisesRegex(RedirectResolutionError, "loop"):
            await SafeRedirectResolver(resolver=public_dns, requester=loop_requester).resolve("https://example.com/a")

        async def endless_requester(url, _timeout):
            number = int(url.rsplit("/", 1)[-1])
            return RedirectHTTPResponse(302, {"location": f"/{number + 1}"})

        with self.assertRaisesRegex(RedirectResolutionError, "limit"):
            await SafeRedirectResolver(resolver=public_dns, requester=endless_requester, max_redirects=2).resolve("https://example.com/0")

    async def test_public_to_private_redirect_is_blocked_before_second_request(self):
        requested = []

        async def resolver(hostname, _port):
            return ["127.0.0.1"] if hostname == "private.test" else ["93.184.216.34"]

        async def requester(url, _timeout):
            requested.append(url)
            return RedirectHTTPResponse(302, {"location": "http://private.test/admin"})

        with self.assertRaisesRegex(URLSafetyError, "non-public"):
            await SafeRedirectResolver(resolver=resolver, requester=requester).resolve("https://example.com/start")
        self.assertEqual(requested, ["https://example.com/start"])

    async def test_total_redirect_deadline_is_enforced(self):
        async def slow_requester(_url, _timeout):
            await asyncio.sleep(0.1)
            return RedirectHTTPResponse(200, {})

        with self.assertRaisesRegex(RedirectResolutionError, "timed out"):
            await SafeRedirectResolver(resolver=public_dns, requester=slow_requester, total_timeout=0.01).resolve("https://example.com/")


class BoundedHTTPFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_client_identifies_bot_without_impersonating_browser(self):
        from src.backend.core.config import settings
        async with SafeRedirectResolver._client() as client:
            self.assertEqual(client.headers['User-Agent'], settings.url_fetch_user_agent)
            self.assertIn('Bot', client.headers['User-Agent'])
            self.assertIn('https://github.com/', client.headers['User-Agent'])
            self.assertNotIn('Mozilla', client.headers['User-Agent'])
            self.assertFalse(client.follow_redirects)

    async def test_meta_body_time_does_not_consume_header_budget_twice(self):
        first = self.Stream([b'<meta http-equiv="refresh" content="0;url=/final">'], delay=0.08)
        final = self.Stream([b'<html><body>Readable destination</body></html>'], delay=0.01)
        resolver, _ = self.resolver(lambda request: httpx.Response(200,
            headers={'content-type': 'text/html'}, stream=first if request.url.path == '/start' else final),
            total_timeout=0.05, content_timeout=0.2)
        result = await resolver.resolve('https://ordinary.test/start')
        self.assertEqual(result.final_url, 'https://ordinary.test/final')
        self.assertEqual(result.redirect_kinds, ('meta_refresh',))
        self.assertIn('Readable destination', result.content_preview)
        self.assertEqual(result.content_fetch_status, 'complete')
        self.assertTrue(first.closed and final.closed)

    async def test_meta_hops_share_one_content_budget_not_one_per_page(self):
        # Each body fits a fresh 0.1-second budget; together they do not.
        # Leave headroom on the first hop so scheduler jitter cannot make this
        # test finish before opening the destination whose cleanup it asserts.
        first = self.Stream([b'<meta http-equiv="refresh" content="0;url=/final">'], delay=0.025)
        final = self.Stream([b'<html><body>Delayed destination</body></html>'], delay=0.09)
        resolver, _ = self.resolver(lambda request: httpx.Response(200,
            headers={'content-type': 'text/html'}, stream=first if request.url.path == '/start' else final),
            total_timeout=0.1, content_timeout=0.1)
        started = time.monotonic()
        result = await resolver.resolve('https://ordinary.test/start')
        self.assertLess(time.monotonic()-started, 0.25)
        self.assertEqual(result.content_fetch_status, 'timeout')
        self.assertNotIn('Delayed destination', result.content_preview)
        self.assertTrue(first.closed and final.closed)

    async def test_header_deadline_does_not_reset_on_http_redirect(self):
        async def handler(request):
            await asyncio.sleep(0.035)
            return httpx.Response(302, headers={'location': '/final'}) if request.url.path == '/start' else httpx.Response(200, text='destination')
        resolver, _ = self.resolver(handler, total_timeout=0.05, content_timeout=0.2)
        with self.assertRaises(RedirectResolutionError) as error:
            await resolver.resolve('https://ordinary.test/start')
        self.assertEqual(error.exception.code, 'timeout')

    async def test_mislabeled_html_redirect_still_blocks_private_destination(self):
        resolver, _ = self.resolver(lambda request: httpx.Response(200,
            headers={'content-type': 'application/octet-stream'},
            content=b'<!doctype html><html><meta http-equiv="refresh" content="0;url=http://127.0.0.1/"></html>'))
        with self.assertRaises(URLSafetyError):
            await resolver.resolve('https://ordinary.test/')

    async def test_declared_thai_charset_is_decoded_without_replacement_noise(self):
        body = '<html><body>ตารางรอบฉายภาพยนตร์และข้อมูลการจองตั๋ว</body></html>'.encode('tis-620')
        resolver, _ = self.resolver(lambda request: httpx.Response(200,
            headers={'content-type': 'text/html; charset=tis-620'}, content=body))
        result = await resolver.resolve('https://ordinary.test/')
        self.assertIn('รอบฉายภาพยนตร์', result.content_preview)
        self.assertNotIn('\ufffd', result.content_preview)

    async def test_binary_content_is_not_benign_page_and_is_bounded(self):
        stream = self.Stream([b'\x00'*4096, b'\x00'*4096])
        resolver, _ = self.resolver(lambda request: httpx.Response(200,
            headers={'content-type': 'application/pdf'}, stream=stream))
        result = await resolver.resolve('https://ordinary.test/')
        self.assertFalse(result.content_readable)
        self.assertEqual(result.content_fetch_status, 'unsupported_content_type')
        self.assertTrue(stream.closed)

    class Stream(httpx.AsyncByteStream):
        def __init__(self, chunks, delay=0):
            self.chunks = chunks
            self.delay = delay
            self.closed = False

        async def __aiter__(self):
            for chunk in self.chunks:
                if self.delay:
                    await asyncio.sleep(self.delay)
                yield chunk

        async def aclose(self):
            self.closed = True

    def resolver(self, handler, **kwargs):
        factory = Mock(side_effect=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False,
        ))
        resolver = SafeRedirectResolver(resolver=public_dns, client_factory=factory, **kwargs)
        return resolver, factory

    async def test_generic_large_head_reaches_visible_body_beyond_old_64k_limit(self):
        body = b'<head><script>' + b'x' * 90000 + b'</script></head><body><p>' + b'Library resources and opening hours. ' * 8 + b'</p></body>'
        stream = self.Stream([body[:65536], body[65536:]])
        resolver, _ = self.resolver(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, stream=stream))
        result = await resolver.resolve("https://ordinary.test/")
        self.assertIn("Library resources", result.content_preview)
        self.assertFalse(result.content_truncated)
        self.assertTrue(stream.closed)

    async def test_native_redirects_share_one_client_and_revalidate_each_hop(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(302, headers={"location": "/final"}) if request.url.path == "/start" else httpx.Response(200, text="ordinary page")

        resolver, factory = self.resolver(handler)
        dns = AsyncMock(side_effect=public_dns)
        resolver.resolver = dns
        result = await resolver.resolve("https://ordinary.test/start")
        self.assertEqual(calls, ["https://ordinary.test/start", "https://ordinary.test/final"])
        factory.assert_called_once()
        self.assertEqual(dns.await_count, 2)
        self.assertEqual(result.redirect_count, 1)

    async def test_body_budget_is_separate_from_header_budget(self):
        stream = self.Stream([b"readable body"], delay=0.08)
        resolver, _ = self.resolver(
            lambda request: httpx.Response(200, headers={"content-type": "text/plain"}, stream=stream),
            total_timeout=0.05, content_timeout=0.2,
        )
        result = await resolver.resolve("https://ordinary.test/")
        self.assertEqual(result.content_preview, "readable body")
        self.assertEqual(result.content_fetch_status, "complete")
        self.assertTrue(stream.closed)

    async def test_stalled_body_returns_partial_incomplete_evidence_and_closes_stream(self):
        class Stalled(self.Stream):
            async def __aiter__(self):
                yield b'<form>Bank login<input type=password></form>'
                await asyncio.sleep(1)

        stream = Stalled([])
        resolver, _ = self.resolver(
            lambda request: httpx.Response(200, headers={"content-type": "text/html"}, stream=stream),
            content_timeout=0.05,
        )
        started = time.monotonic()
        result = await resolver.resolve("https://ordinary.test/")
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(result.content_fetch_status, "timeout")
        self.assertIn("password", result.content_preview)
        self.assertTrue(stream.closed)

    async def test_download_cap_is_enforced(self):
        stream = self.Stream([b'a' * 64, b'b' * 64, b'c' * 64])
        resolver, _ = self.resolver(lambda request: httpx.Response(200, headers={"content-type": "text/plain"}, stream=stream))
        resolver.max_content_bytes = 100
        result = await resolver.resolve("https://ordinary.test/")
        self.assertEqual(len(result.content_preview), 100)
        self.assertTrue(result.content_truncated)
        self.assertEqual(result.content_fetch_status, "byte_limit")
        self.assertTrue(stream.closed)

    async def test_slow_headers_remain_inside_redirect_deadline(self):
        async def handler(request):
            await asyncio.sleep(1)
            return httpx.Response(200, text="body")

        resolver, _ = self.resolver(handler, total_timeout=0.05, content_timeout=0.2)
        started = time.monotonic()
        with self.assertRaises(RedirectResolutionError) as error:
            await resolver.resolve("https://ordinary.test/")
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(error.exception.code, "timeout")
        self.assertEqual(error.exception.chain, ["https://ordinary.test/"])

    async def test_timeout_preserves_completed_redirect_chain(self):
        async def requester(url, timeout):
            if url.endswith("/start"):
                return RedirectHTTPResponse(302, {"location": "/final"})
            await asyncio.sleep(1)

        resolver = SafeRedirectResolver(resolver=public_dns, requester=requester, total_timeout=0.05)
        with self.assertRaises(RedirectResolutionError) as error:
            await resolver.resolve("https://ordinary.test/start")
        self.assertEqual(error.exception.chain, ["https://ordinary.test/start", "https://ordinary.test/final"])


if __name__ == "__main__":
    unittest.main()
