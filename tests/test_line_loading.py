"""Native LINE loading with synthetic tokens and mocked transport only."""

import asyncio
import base64
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import BackgroundTasks
from starlette.requests import Request

from src.backend.services import line_service
from src.backend.routers import webhook


USER_ID = 'U' + 'a' * 32


class LoadingServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = line_service.LineService.__new__(line_service.LineService)
        self.service.channel_access_token = 'synthetic-loading-token'
        self.real_client = httpx.AsyncClient

    async def invoke(self, handler, user_id=USER_ID, seconds=30):
        factory = Mock(side_effect=lambda **options: self.real_client(
            transport=httpx.MockTransport(handler), **options,
        ))
        with patch.object(line_service.httpx, 'AsyncClient', factory):
            result = await self.service.show_loading_animation(user_id, seconds)
        return result, factory

    async def test_native_request_uses_server_token_and_30_seconds_without_reply_token(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(202, json={})

        result, factory = await self.invoke(handler)
        self.assertTrue(result)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.method, 'POST')
        self.assertEqual(str(request.url), 'https://api.line.me/v2/bot/chat/loading/start')
        self.assertEqual(request.headers['authorization'], 'Bearer synthetic-loading-token')
        self.assertEqual(request.headers['content-type'], 'application/json')
        self.assertEqual(json.loads(request.content), {'chatId': USER_ID, 'loadingSeconds': 30})
        self.assertFalse(factory.call_args.kwargs['follow_redirects'])
        self.assertFalse(factory.call_args.kwargs['trust_env'])

    async def test_failures_and_redirects_do_not_retry_or_raise_or_log_sensitive_body(self):
        for status in [302, 400, 401, 429, 500]:
            with self.subTest(status=status):
                handler = Mock(return_value=httpx.Response(status, headers={'location': 'https://other.test/'},
                                                          text='synthetic-loading-token'))
                with self.assertLogs(line_service.logger, level='WARNING') as logs:
                    result, _ = await self.invoke(handler)
                self.assertFalse(result)
                handler.assert_called_once()
                self.assertNotIn('synthetic-loading-token', ' '.join(logs.output))

    async def test_network_error_is_optional(self):
        result, _ = await self.invoke(Mock(side_effect=httpx.ReadTimeout('synthetic failure')))
        self.assertFalse(result)

    async def test_whole_request_deadline_cancels_stalled_transport(self):
        cancelled = asyncio.Event()

        async def handler(request):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with patch.object(line_service, 'LINE_LOADING_REQUEST_TIMEOUT_SECONDS', .01):
            result, _ = await asyncio.wait_for(self.invoke(handler), timeout=1)
        self.assertFalse(result)
        self.assertTrue(cancelled.is_set())

    async def test_invalid_targets_and_durations_never_create_a_client(self):
        for user_id, seconds in [(None, 30), ('', 30), ('G' + 'a' * 32, 30),
                                 ('R' + 'a' * 32, 30), (USER_ID, 0), (USER_ID, 7),
                                 (USER_ID, 65), (USER_ID, True)]:
            with self.subTest(user_id=user_id, seconds=seconds):
                result, factory = await self.invoke(Mock(), user_id, seconds)
                self.assertFalse(result)
                factory.assert_not_called()


class LoadingWebhookTests(unittest.IsolatedAsyncioTestCase):
    async def send(self, event, line, check, signature_valid=True):
        secret = 'synthetic-loading-secret'
        body = json.dumps({'events': [event]}).encode()

        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}

        signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
        with patch.object(webhook, 'settings', SimpleNamespace(line_channel_secret=secret)), \
             patch.object(webhook, 'LINE_SERVICE_AVAILABLE', True), \
             patch.object(webhook, 'get_line_service', return_value=line), \
             patch.object(webhook, '_check_link_request', check):
            return await webhook.webhook(Request({'type': 'http'}, receive), BackgroundTasks(),
                                         signature if signature_valid else 'invalid')

    def event(self, source=None):
        return {'type': 'message', 'replyToken': 'synthetic-reply-token',
                'source': source or {'type': 'user', 'userId': USER_ID},
                'message': {'type': 'text', 'text': 'https://example.com/', 'quoteToken': 'synthetic-quote'}}

    async def test_loading_precedes_verification_and_keeps_same_flex_reply(self):
        order = []
        line = Mock()
        line.show_loading_animation = AsyncMock(side_effect=lambda *a, **kw: order.append('loading'))
        flex = {'alt_text': 'synthetic result', 'contents': {'type': 'bubble'}}
        line.create_url_verification_flex_message.return_value = flex

        async def verify(*args, **kwargs):
            order.append('verify')
            return {'verification_verdict': 'INCOMPLETE'}

        line.reply_message.side_effect = lambda *a, **kw: order.append('reply')
        self.assertEqual(await self.send(self.event(), line, AsyncMock(side_effect=verify)), {'status': 'ok'})
        self.assertEqual(order, ['loading', 'verify', 'reply'])
        line.reply_message.assert_called_once_with('synthetic-reply-token', flex_message=flex,
                                                   quote_token='synthetic-quote')

    async def test_loading_failure_does_not_stop_verification_or_flex_reply(self):
        for failure in [False, RuntimeError('synthetic failure')]:
            with self.subTest(failure=failure):
                line = Mock()
                line.show_loading_animation = AsyncMock(
                    return_value=False, side_effect=failure if isinstance(failure, Exception) else None,
                )
                check = AsyncMock(return_value={'verification_verdict': 'INCOMPLETE'})
                await self.send(self.event(), line, check)
                check.assert_awaited_once()
                line.reply_message.assert_called_once()

    async def test_invalid_signature_does_not_start_loading_or_verify(self):
        line = Mock()
        line.show_loading_animation = AsyncMock()
        check = AsyncMock()
        with self.assertRaises(webhook.HTTPException) as failure:
            await self.send(self.event(), line, check, signature_valid=False)
        self.assertEqual(failure.exception.status_code, 403)
        line.show_loading_animation.assert_not_awaited()
        check.assert_not_awaited()

    async def test_groups_rooms_missing_user_and_postbacks_do_not_start_loading(self):
        line = Mock()
        line.show_loading_animation = AsyncMock()
        with patch.object(webhook, 'get_line_service', return_value=line):
            for source in [{'type': 'group', 'groupId': 'group', 'userId': USER_ID},
                           {'type': 'room', 'roomId': 'room', 'userId': USER_ID},
                           {'type': 'user'}, {}]:
                await webhook._show_personal_chat_loading(source)
        event = {'type': 'postback', 'replyToken': 'synthetic-reply-token',
                 'source': {'type': 'user', 'userId': USER_ID}, 'postback': {'data': ''}}
        check = AsyncMock()
        await self.send(event, line, check)
        line.show_loading_animation.assert_not_awaited()
        check.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
