"""SPA coverage, staged routing and network boundaries; no live provider calls."""

import asyncio
import os
import json
import gzip
import zlib
import time
import unittest
from unittest.mock import AsyncMock, patch

from src.backend.core.config import settings
from src.backend.services.url_renderer_service import BoundedPageRenderer, PublicNetworkBackend, PublicResourceBroker, ResourceResponse
from src.backend.services.url_verification_service import URLVerificationService
from types import SimpleNamespace
from src.backend.services.url_safety_service import URLSafetyError
from tests.test_url_staged_routing import candidate
from tests.test_url_verification_service import BENIGN_PAGE


SHELL = '<!doctype html><html><body><div id="root"></div><script src="/app.js"></script></body></html>'
TEXT = 'A public community library provides books, educational resources, opening hours and local events for visitors.'


def rendered(url='https://spa.test/', html=BENIGN_PAGE, text=TEXT, **changes):
    return {"status": "clean", "complete": True, "html": html, "visible_text": text,
            "final_url": url, "redirect_chain": [url], "http_status": 200, **changes}


class SPARoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_generic_unknown_spa_uses_actual_rendered_evidence_then_ai_no_vt(self):
        for url in ['https://spa.test/', 'https://gungong-vercel-preview.vercel.app/', 'https://unfamiliar.test/catalogue']:
            verifier, gemini, vt, _, _ = candidate(page=SHELL, trusted_origins=[])
            verifier.render_check = AsyncMock(return_value=rendered(url))
            result = await verifier.verify(url)
            self.assertEqual(result['verification_verdict'], 'NO_THREAT_FOUND')
            self.assertEqual(result['checks']['content']['source'], 'bounded_rendered_page_evidence')
            gemini.assert_awaited_once()
            self.assertEqual(gemini.await_args.args[1].visible_text, TEXT)
            vt.assert_not_awaited()
            self.assertNotIn('html', result['checks']['render'])

    async def test_trusted_rendered_benign_is_fast_path(self):
        verifier, gemini, vt, _, _ = candidate(page=SHELL, trusted_origins=['https://spa.test'])
        verifier.render_check = AsyncMock(return_value=rendered())
        result = await verifier.verify('https://spa.test/')
        self.assertEqual(result['verification_route'], 'FAST_SAFE')
        self.assertEqual(result['verification_verdict'], 'NO_THREAT_FOUND')
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_readable_static_page_never_launches_browser(self):
        verifier, _, _, _, _ = candidate()
        result = await verifier.verify('https://static.test/')
        self.assertEqual(result['verification_verdict'], 'NO_THREAT_FOUND')
        verifier.render_check.assert_not_awaited()

    async def test_rendered_fake_bank_stays_suspicious_when_vt_times_out(self):
        verifier, gemini, vt, _, _ = candidate(page=SHELL, vt_status='timeout')
        verifier.render_check = AsyncMock(return_value=rendered(
            html='<form><input type=password></form>',
            text='Bank login password verification. Enter your password to restore your banking account immediately.',
        ))
        result = await verifier.verify('https://spa.test/')
        self.assertEqual(result['verification_verdict'], 'SUSPICIOUS')
        gemini.assert_not_awaited()
        vt.assert_awaited_once()

    async def test_render_timeout_or_missing_resources_is_not_benign(self):
        for response in [dict(status='timeout', complete=False), rendered(status='insufficient', complete=False)]:
            verifier, _, _, _, _ = candidate(page=SHELL)
            verifier.render_check = AsyncMock(return_value=response)
            result = await verifier.verify('https://spa.test/')
            self.assertEqual(result['verification_verdict'], 'INCOMPLETE')
            self.assertIsNone(result['is_safe'])

    async def test_rendered_redirect_rechecks_final_origin_not_initial_trusted(self):
        verifier, gemini, vt, local, _ = candidate(page=SHELL, trusted_origins=['https://spa.test'])
        verifier.render_check = AsyncMock(return_value=rendered(
            'https://unknown.test/', redirect_chain=['https://spa.test/', 'https://unknown.test/'],
        ))
        result = await verifier.verify('https://spa.test/')
        self.assertEqual(result['verification_route'], 'AI_CONFIRMATION')
        self.assertEqual(result['final_url'], 'https://unknown.test/')
        local.assert_awaited_once_with('https://unknown.test/')
        self.assertEqual(verifier.risk_check.await_count, 2)
        gemini.assert_awaited_once()
        vt.assert_not_awaited()

    async def test_render_blocked_never_calls_ai_or_vt(self):
        verifier, gemini, vt, _, _ = candidate(page=SHELL)
        verifier.render_check = AsyncMock(return_value={'status': 'blocked', 'complete': True, 'reason': 'non_public_address'})
        result = await verifier.verify('https://spa.test/')
        self.assertEqual(result['verification_verdict'], 'INVALID')
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_slow_render_is_cancelled_and_bounded(self):
        cancelled = asyncio.Event()
        async def slow(_url):
            try:
                await asyncio.sleep(5)
            finally:
                cancelled.set()
        verifier, _, _, _, _ = candidate(page=SHELL)
        verifier.config.MAX_TOTAL_PROCESSING_TIME = 2.0
        verifier.config.URL_RENDER_TIMEOUT = 0.05
        verifier.render_check = slow
        started = time.monotonic()
        result = await verifier.verify('https://spa.test/')
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(result['verification_verdict'], 'INCOMPLETE')


class PinnedNetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_dns_connection_pins_public_ip_not_hostname(self):
        resolver = AsyncMock(return_value=['93.184.216.34'])
        backend = AsyncMock()
        adapter = PublicNetworkBackend(resolver, backend)
        await adapter.connect_tcp('public.test', 443, timeout=0.1)
        resolver.assert_awaited_once_with('public.test', 443)
        self.assertEqual(backend.connect_tcp.await_args.args, ('93.184.216.34', 443))

    async def test_private_or_mixed_dns_answers_never_connect(self):
        for answers in [['127.0.0.1'], ['169.254.169.254'], ['192.168.1.1'], ['::1'],
                        ['fc00::1'], ['224.0.0.1'], ['ff0e::1'], ['100.64.0.1'],
                        ['::ffff:127.0.0.1'], ['93.184.216.34', '10.0.0.1'], []]:
            backend = AsyncMock()
            adapter = PublicNetworkBackend(AsyncMock(return_value=answers), backend)
            with self.assertRaises(URLSafetyError):
                await adapter.connect_tcp('attacker.test', 443, timeout=0.1)
            backend.connect_tcp.assert_not_awaited()

    async def test_dns_budget_includes_resolution(self):
        backend = AsyncMock()
        async def slow(*_args):
            await asyncio.sleep(1)
        with self.assertRaises(asyncio.TimeoutError):
            await PublicNetworkBackend(slow, backend).connect_tcp('slow.test', 443, timeout=0.01)
        backend.connect_tcp.assert_not_awaited()


class EncodedResourceTests(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, payload, encoding='identity', limit=1024):
        class Response:
            status = 200
            headers = [(b'content-encoding', encoding.encode())]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                self.closed = True

            async def aiter_stream(self):
                for index in range(0, len(payload), 7):
                    yield payload[index:index + 7]

        response = Response()
        with patch('src.backend.services.url_renderer_service.httpcore.AsyncConnectionPool') as pool:
            pool.return_value.stream.return_value = response
            result = await PublicResourceBroker().fetch('https://resource.test/app.js', 0.1, limit)
            self.assertTrue(response.closed)
            self.assertEqual(pool.return_value.stream.call_args.kwargs['headers']['Accept-Encoding'], 'identity')
        return result

    async def test_identity_and_bounded_gzip_deflate_are_readable(self):
        source = b'document.body.textContent = "Public library opening hours";'
        for encoding, payload in [('identity', source), ('gzip', gzip.compress(source)), ('deflate', zlib.compress(source))]:
            with self.subTest(encoding=encoding):
                result = await self.fetch(payload, encoding)
                self.assertEqual(result.body, source)

    async def test_exact_decoded_limit_is_allowed(self):
        result = await self.fetch(gzip.compress(b'A' * 1024), 'gzip')
        self.assertEqual(len(result.body), 1024)

    async def test_compression_bomb_never_exceeds_decoded_budget(self):
        for encoding, payload in [('gzip', gzip.compress(b'A' * 1000000)), ('deflate', zlib.compress(b'A' * 1000000))]:
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                await self.fetch(payload, encoding)

    async def test_wire_budget_is_enforced(self):
        with self.assertRaises(ValueError):
            await self.fetch(b'A' * 1025)

    async def test_truncated_corrupt_trailing_and_concatenated_gzip_are_not_complete(self):
        payload = gzip.compress(b'Public page')
        for bad in [payload[:-1], b'not gzip', payload + b'trailing', payload + payload]:
            with self.subTest(payload_length=len(bad)), self.assertRaises((ValueError, zlib.error)):
                await self.fetch(bad, 'gzip')

    async def test_unsupported_or_stacked_encoding_is_not_complete(self):
        for encoding in ['br', 'gzip, deflate']:
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                await self.fetch(b'encoded', encoding)

    async def test_no_remaining_byte_budget_rejects_before_request(self):
        with patch('src.backend.services.url_renderer_service.httpcore.AsyncConnectionPool') as pool:
            with self.assertRaises(ValueError):
                await PublicResourceBroker().fetch('https://resource.test/', 0.1, 0)
            pool.return_value.stream.assert_not_called()


class GroundedAIContractTests(unittest.IsolatedAsyncioTestCase):
    async def classify(self, risks):
        from src.backend.services.url_verification_service import extract_page_evidence
        llm = AsyncMock()
        llm.ainvoke.return_value = SimpleNamespace(content=json.dumps({
            'assessment': 'suspicious', 'category': 'SCAM_MALICIOUS', 'risk_level': 'Medium',
            'confidence_score': 85, 'reason_th': 'คำอธิบายความเสี่ยง', 'keywords_found': [],
            'evidence_sufficient': True, 'risk_evidence': risks,
        }))
        with patch('src.backend.services.url_verification_service.get_fraud_detector', return_value=SimpleNamespace(llm=llm, model='mock')):
            result = await URLVerificationService._default_gemini_check(
                'https://unfamiliar.test/', extract_page_evidence('https://unfamiliar.test/', '<p>Enter your bank password immediately</p><input type=password>'),
            )
        return result, llm.ainvoke.await_args.args[0][0].content

    async def test_ungrounded_or_invented_ai_suspicion_is_not_confirmed_danger(self):
        for risks in [[], [{'kind': 'impersonation', 'quote': 'This quote is not in the page'}],
                      [{'kind': 'free_hosting', 'quote': 'Enter your bank password'}], None]:
            result, prompt = await self.classify(risks)
            self.assertEqual(result['assessment'], 'uncertain')
            self.assertFalse(result['is_fraud'])
            self.assertFalse(result['evidence_sufficient'])
            self.assertIn('Free/shared hosting', prompt)

    async def test_grounded_credential_risk_is_not_suppressed(self):
        result, _ = await self.classify([{'kind': 'credential_theft', 'quote': 'Enter your bank password'}])
        self.assertEqual(result['assessment'], 'suspicious')
        self.assertTrue(result['is_fraud'])

    async def test_model_cannot_invent_credential_forms_from_privacy_policy(self):
        from src.backend.services.url_verification_service import extract_page_evidence
        llm = AsyncMock()
        llm.ainvoke.return_value = SimpleNamespace(content=json.dumps({
            'assessment': 'suspicious', 'category': 'SCAM_MALICIOUS', 'risk_level': 'Medium',
            'confidence_score': 85, 'reason_th': 'พบฟอร์มปลอม', 'keywords_found': [],
            'evidence_sufficient': True,
            'risk_evidence': [{'kind': 'impersonation', 'quote': 'Privacy policy and personal data consent'}],
        }))
        with patch('src.backend.services.url_verification_service.get_fraud_detector', return_value=SimpleNamespace(llm=llm, model='mock')):
            result = await URLVerificationService._default_gemini_check(
                'https://unknown.test/', extract_page_evidence('https://unknown.test/', '<p>Privacy policy and personal data consent</p>'),
            )
        self.assertEqual(result['assessment'], 'uncertain')
        self.assertFalse(result['is_fraud'])


class RendererAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_renderer_never_starts_browser(self):
        renderer = BoundedPageRenderer()
        renderer._render = AsyncMock()
        with patch.object(settings, 'url_render_enabled', False):
            result = await renderer.render('https://example.com/')
        renderer._render.assert_not_awaited()
        self.assertEqual(result['reason'], 'renderer_disabled')

    async def test_busy_renderer_never_queues_unbounded_work(self):
        renderer = BoundedPageRenderer()
        renderer._render = AsyncMock()
        await renderer._slots.acquire()
        await renderer._slots.acquire()
        with patch.object(settings, 'url_render_enabled', True):
            result = await renderer.render('https://example.com/')
        self.assertEqual(result['reason'], 'renderer_busy')
        renderer._render.assert_not_awaited()

    async def test_browser_sandbox_failure_is_explicit_not_clean(self):
        renderer = BoundedPageRenderer()
        renderer._render = AsyncMock(side_effect=RuntimeError('No usable sandbox'))
        with patch.object(settings, 'url_render_enabled', True):
            result = await renderer.render('https://example.com/')
        self.assertEqual(result['reason'], 'renderer_sandbox_unavailable')
        self.assertFalse(result['complete'])


@unittest.skipUnless(os.path.exists('C:/Program Files/Google/Chrome/Application/chrome.exe'), 'Local Chrome not installed')
class ControlledChromiumTests(unittest.IsolatedAsyncioTestCase):
    """Real sandboxed Chrome, intercepted synthetic responses, no public network."""

    async def execute(self, script, *, missing_script=False):
        async def fetch(url, _timeout, _limit):
            if url == 'https://spa.test/':
                return ResourceResponse(200, {'content-type': 'text/html'}, SHELL.encode())
            if url == 'https://spa.test/app.js':
                return ResourceResponse(404 if missing_script else 200, {'content-type': 'text/javascript'}, script.encode())
            if url == 'https://destination.test/':
                return ResourceResponse(200, {'content-type': 'text/html'}, ('<body>' + TEXT + '</body>').encode())
            if url == 'https://telemetry.test/':
                return ResourceResponse(403, {'content-type': 'text/plain'}, b'denied')
            raise ValueError('Unexpected synthetic resource')
        fetcher = AsyncMock(side_effect=fetch)
        with patch.object(settings, 'url_render_browser_channel', 'chrome'), patch.object(settings, 'url_render_enabled', True):
            result = await BoundedPageRenderer(fetcher=fetcher).render('https://spa.test/')
        return result, fetcher

    async def test_javascript_renders_real_dom(self):
        result, _ = await self.execute(f"document.getElementById('root').textContent = {TEXT!r};")
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['visible_text'], TEXT)

    async def test_private_fetch_is_blocked_before_broker(self):
        result, fetcher = await self.execute(f"document.body.textContent={TEXT!r}; fetch('http://169.254.169.254/latest/meta-data/');")
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(fetcher.await_count, 2)

    async def test_private_javascript_redirect_is_blocked(self):
        result, fetcher = await self.execute("location.href='http://127.0.0.1/';")
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(fetcher.await_count, 2)

    async def test_missing_script_is_not_clean(self):
        result, _ = await self.execute('', missing_script=True)
        self.assertNotEqual(result['status'], 'clean')

    async def test_public_js_redirect_is_recorded_and_read(self):
        result, _ = await self.execute("location.href='https://destination.test/';")
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['final_url'], 'https://destination.test/')
        self.assertEqual(result['redirect_chain'], ['https://spa.test/', 'https://destination.test/'])

    async def test_hash_router_keeps_public_origin_and_rendered_location(self):
        result, _ = await self.execute(f"document.body.textContent={TEXT!r}; location.hash='catalogue';")
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['final_url'], 'https://spa.test/#catalogue')

    async def test_completed_html_is_reused_without_duplicate_fetch(self):
        fetcher = AsyncMock(return_value=ResourceResponse(200, {'content-type':'text/javascript'},
                                                        f"document.body.textContent={TEXT!r};".encode()))
        with patch.object(settings, 'url_render_browser_channel', 'chrome'), patch.object(settings, 'url_render_enabled', True), patch(
            'src.backend.services.url_renderer_service.validate_public_url', AsyncMock(return_value='https://spa.test/'),
        ):
            result = await BoundedPageRenderer(fetcher=fetcher).render('https://spa.test/', initial_html=SHELL)
        self.assertEqual(result['status'], 'clean')
        fetcher.assert_awaited_once()
        self.assertEqual(fetcher.await_args.args[0], 'https://spa.test/app.js')

    async def test_reused_html_preserves_content_security_policy(self):
        fetcher = AsyncMock()
        with patch.object(settings, 'url_render_browser_channel', 'chrome'), patch.object(settings, 'url_render_enabled', True), patch(
            'src.backend.services.url_renderer_service.validate_public_url', AsyncMock(return_value='https://spa.test/'),
        ):
            result = await BoundedPageRenderer(fetcher=fetcher).render(
                'https://spa.test/', initial_html=f'<body>{TEXT}<script src="/app.js"></script></body>',
                content_security_policy="script-src 'none'",
            )
        self.assertEqual(result['status'], 'clean')
        fetcher.assert_not_awaited()

    async def test_optional_third_party_telemetry_is_not_core_failure(self):
        result, fetcher = await self.execute(f"document.body.textContent={TEXT!r}; fetch('https://telemetry.test/'); fetch('https://telemetry.test/', {{method:'POST'}});")
        self.assertEqual(result['status'], 'clean')
        self.assertGreaterEqual(result['optional_resource_failures'], 2)
        self.assertEqual(fetcher.await_count, 3)  # No POST was sent.

    async def test_websocket_never_reaches_broker(self):
        result, fetcher = await self.execute(f"document.body.textContent={TEXT!r}; new WebSocket('ws://127.0.0.1:12345');")
        self.assertNotEqual(result['status'], 'clean')
        self.assertEqual(fetcher.await_count, 2)


if __name__ == '__main__':
    unittest.main()
