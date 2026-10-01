"""Local worker transport/auth/cancellation without public traffic or credentials."""

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.backend.core.config import settings
from src.backend.services import renderer_worker_app as worker
from src.backend.services.url_renderer_worker_client import render_in_local_worker, worker_endpoint
from src.backend.services.url_renderer_service import browser_environment
from src.backend.services.url_verification_service import URLVerificationService
from tests.test_url_renderer import rendered, SHELL
from tests.test_url_staged_routing import candidate

TOKEN = 'fixture-only-worker-token-not-a-provider-key-123456789'


class WorkerBoundaryTests(unittest.TestCase):
    def test_chromium_environment_excludes_even_the_dedicated_worker_token(self):
        with patch.dict(os.environ, {'PATH': '/usr/bin', 'HOME': '/tmp', 'URL_RENDER_WORKER_TOKEN': TOKEN,
                                    'GOOGLE_API_KEY': 'fixture', 'AWS_SESSION_TOKEN': 'fixture'}, clear=True):
            self.assertEqual(browser_environment(), {'PATH': '/usr/bin', 'HOME': '/tmp'})

    def test_only_explicit_numeric_loopback_worker_endpoints_are_accepted(self):
        self.assertEqual(worker_endpoint('http://127.0.0.1:8071/'), 'http://127.0.0.1:8071/render')
        self.assertEqual(worker_endpoint('http://[::1]:8071'), 'http://[::1]:8071/render')
        for url in ['http://localhost:8071', 'https://example.com', 'http://169.254.169.254:8071',
                    'http://127.0.0.1', 'http://127.0.0.1:80', 'http://user:pass@127.0.0.1:8071',
                    'http://127.0.0.1:8071/path', 'http://127.0.0.1:8071?url=http://private/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                worker_endpoint(url)

    def test_worker_refuses_forwarded_provider_or_firestore_configuration(self):
        for name in worker.FORBIDDEN_ENV:
            with self.subTest(name=name), patch.dict(os.environ, {name: 'fixture', 'URL_RENDER_WORKER_TOKEN': TOKEN}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'refuses backend credentials'):
                    worker.assert_worker_environment()

    def test_worker_refuses_secret_files_and_missing_own_token(self):
        with patch.dict(os.environ, {'URL_RENDER_WORKER_TOKEN': TOKEN}, clear=True), patch.object(worker.Path, 'exists', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'secret files'):
                worker.assert_worker_environment()
        with patch.dict(os.environ, {}, clear=True), patch.object(worker.Path, 'exists', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'dedicated local access token'):
                worker.assert_worker_environment()

    def test_auth_origin_content_type_and_unknown_payload_fields_fail_closed(self):
        engine = SimpleNamespace(render=AsyncMock(return_value=rendered('https://example.com/')))
        client = TestClient(worker.create_app(engine))
        with patch.dict(os.environ, {'URL_RENDER_WORKER_TOKEN': TOKEN}):
            for headers, payload, expected in [
                ({}, {'url': 'https://example.com/'}, 403),
                ({'Authorization': 'Bearer wrong'}, {'url': 'https://example.com/'}, 403),
                ({'Authorization': 'Bearer ' + TOKEN, 'Origin': 'https://evil.test'}, {'url': 'https://example.com/'}, 403),
                ({'Authorization': 'Bearer ' + TOKEN}, {'url': 'https://example.com/', 'GOOGLE_API_KEY': 'fixture'}, 422),
                ({'Authorization': 'Bearer ' + TOKEN}, {'url': 'https://example.com/', 'timeout': 20}, 422),
            ]:
                self.assertEqual(client.post('/render', json=payload, headers=headers).status_code, expected)
            self.assertEqual(client.post('/render', content='url=x', headers={
                'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'text/plain',
            }).status_code, 415)
        engine.render.assert_not_awaited()

    def test_private_target_is_blocked_before_browser_launch(self):
        engine = SimpleNamespace(render=AsyncMock())
        with patch.dict(os.environ, {'URL_RENDER_WORKER_TOKEN': TOKEN}):
            result = TestClient(worker.create_app(engine)).post('/render', json={
                'url': 'http://169.254.169.254/latest/meta-data/',
            }, headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'blocked')
        engine.render.assert_not_awaited()

    def test_request_body_is_bounded(self):
        engine = SimpleNamespace(render=AsyncMock())
        with patch.dict(os.environ, {'URL_RENDER_WORKER_TOKEN': TOKEN}), patch.object(worker, 'MAX_TRANSPORT_BYTES', 16):
            response = TestClient(worker.create_app(engine)).post('/render', content=b'x' * 17, headers={
                'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json',
            })
        self.assertEqual(response.status_code, 413)
        engine.render.assert_not_awaited()


class WorkerTransportTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, handler, **kwargs):
        with patch.object(settings, 'url_render_enabled', True), patch.object(settings, 'url_render_worker_url', 'http://127.0.0.1:8071'), patch.object(settings, 'url_render_worker_token', SecretStr(TOKEN)):
            return await render_in_local_worker('https://spa.test/', client_factory=lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(handler), follow_redirects=False,
            ), **kwargs)

    async def test_transport_sends_only_page_and_dedicated_auth_not_provider_credentials(self):
        def handler(request):
            import json
            payload = json.loads(request.content)
            self.assertEqual(set(payload), {'url', 'initial_html', 'content_security_policy', 'timeout'})
            self.assertEqual(request.headers['authorization'], 'Bearer ' + TOKEN)
            self.assertNotIn('fixture-provider-secret', request.content.decode())
            return httpx.Response(200, json=rendered())
        with patch.object(settings, 'google_api_key', 'fixture-provider-secret'), patch.object(settings, 'virustotal_api_key', 'fixture-provider-secret'):
            result = await self.invoke(handler, initial_html=SHELL)
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['source'], 'isolated_local_worker')

    async def test_redirect_http_error_and_malformed_response_are_not_clean(self):
        for response in [httpx.Response(302, headers={'location': 'http://169.254.169.254/'}),
                         httpx.Response(500), httpx.Response(200, text='not-json'),
                         httpx.Response(200, json={'status': 'clean', 'complete': True})]:
            with self.subTest(status=response.status_code):
                result = await self.invoke(lambda _request: response)
                self.assertEqual(result['status'], 'unavailable')
                self.assertFalse(result['complete'])

    async def test_response_size_is_bounded(self):
        with patch('src.backend.services.url_renderer_worker_client.MAX_TRANSPORT_BYTES', 1024):
            result = await self.invoke(lambda _request: httpx.Response(200, content=b'x' * 1025))
        self.assertEqual(result['status'], 'unavailable')

    async def test_transport_timeout_cancels_request_and_closes_client(self):
        cancelled = asyncio.Event()
        async def handler(_request):
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.set()
        config = SimpleNamespace(URL_RENDER_TIMEOUT=0.03)
        with patch('src.backend.services.url_renderer_worker_client.get_performance_config', return_value=config):
            result = await self.invoke(handler)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(cancelled.is_set())

    async def test_disconnected_caller_cancels_owned_browser_job(self):
        started, cleaned = asyncio.Event(), asyncio.Event()
        async def slow(*_args, **_kwargs):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cleaned.set()
        async def disconnected():
            await started.wait()
            return True
        with patch.object(worker, 'validate_public_url', AsyncMock(return_value='https://spa.test/')):
            result = await worker._run_job(SimpleNamespace(render=slow), worker.RenderJob(url='https://spa.test/'),
                                           SimpleNamespace(is_disconnected=disconnected))
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(cleaned.is_set())

    async def test_api_default_fallback_chooses_worker_without_launching_inline_browser(self):
        with patch.object(settings, 'url_render_worker_url', 'http://127.0.0.1:8071'), patch(
            'src.backend.services.url_renderer_worker_client.render_in_local_worker', AsyncMock(return_value=rendered()),
        ) as remote, patch('src.backend.services.url_renderer_service.get_page_renderer') as inline:
            result = await URLVerificationService._default_render_check('https://spa.test/', initial_html=SHELL)
        remote.assert_awaited_once()
        inline.assert_not_called()
        self.assertEqual(result['status'], 'clean')

    async def test_worker_evidence_runs_same_staged_unknown_benign_and_suspicious_routes(self):
        for risky in [False, True]:
            verifier, gemini, vt, _, _ = candidate(page=SHELL, vt_status='timeout')
            response = rendered(html='<form><input type=password></form>' if risky else rendered()['html'],
                                text='Bank login password verification. Restore your banking account immediately.' if risky else rendered()['visible_text'])
            verifier.render_check = AsyncMock(return_value=response)
            result = await verifier.verify('https://spa.test/')
            self.assertEqual(result['verification_verdict'], 'SUSPICIOUS' if risky else 'NO_THREAT_FOUND')
            if risky:
                vt.assert_awaited_once()
            else:
                gemini.assert_awaited_once()
                vt.assert_not_awaited()
