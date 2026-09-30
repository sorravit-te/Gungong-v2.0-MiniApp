"""Deterministic URL normalization, SSRF, and redirect-boundary tests."""

import asyncio
import unittest

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


if __name__ == "__main__":
    unittest.main()
