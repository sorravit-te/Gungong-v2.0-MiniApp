"""Real local QR pixels; signed events and provider transports are synthetic."""
import asyncio
import base64
import hashlib
import hmac
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import numpy as np
import zxingcpp
from PIL import Image, ImageOps
from fastapi import BackgroundTasks
from starlette.requests import Request

from src.backend.routers import webhook
from src.backend.services.line_service import LineService
from src.backend.services.qr_image_service import decode_qr_image, QRImageError


URL = 'https://example.com/qr-check'
USER = 'U' + 'a' * 32


def qr_image(value=URL):
    barcode = zxingcpp.create_barcode(value, zxingcpp.BarcodeFormat.QRCode)
    return Image.fromarray(np.asarray(zxingcpp.write_barcode_to_image(barcode, scale=8))).resize((240, 240), Image.Resampling.NEAREST)


def encode_image(image, format='PNG'):
    output = io.BytesIO()
    image.save(output, format=format)
    return output.getvalue()


class QRImageDecoderTests(unittest.TestCase):
    def test_pixel_decoder_handles_rotated_inverted_and_small_qr_inside_poster(self):
        qr = qr_image()
        poster = Image.new('RGB', (1000, 1600), 'lightblue')
        poster.paste(qr.resize((180, 180)), (720, 1300))
        for image in [qr, qr.rotate(90), ImageOps.invert(qr), poster]:
            with self.subTest(size=image.size):
                self.assertEqual(decode_qr_image(encode_image(image)), URL)

    def test_supported_formats_and_transparent_background(self):
        qr = qr_image().convert('RGBA')
        qr.putalpha(255)
        for format in ['PNG', 'JPEG', 'WEBP']:
            image = qr if format == 'PNG' else qr.convert('RGB')
            self.assertEqual(decode_qr_image(encode_image(image, format)), URL)

    def test_no_qr_returns_none_not_an_ai_guessed_url(self):
        self.assertIsNone(decode_qr_image(encode_image(Image.new('RGB', (300, 300), 'white'))))

    def test_multiple_distinct_qr_codes_are_not_silently_reduced_to_one(self):
        image = Image.new('RGB', (600, 300), 'white')
        image.paste(qr_image(URL), (10, 20))
        image.paste(qr_image('https://other.example/'), (330, 20))
        with self.assertRaisesRegex(QRImageError, 'QR_IMAGE_MULTIPLE'):
            decode_qr_image(encode_image(image))

    def test_invalid_oversized_unsupported_and_large_pixel_images_are_bounded(self):
        with self.assertRaises(QRImageError):
            decode_qr_image(b'not an image')
        with patch('src.backend.services.qr_image_service.MAX_QR_IMAGE_BYTES', 2):
            with self.assertRaisesRegex(QRImageError, 'QR_IMAGE_SIZE'):
                decode_qr_image(b'123')
        with self.assertRaisesRegex(QRImageError, 'QR_IMAGE_TYPE'):
            decode_qr_image(encode_image(qr_image(), 'GIF'))
        with patch('src.backend.services.qr_image_service.MAX_QR_IMAGE_PIXELS', 100):
            with self.assertRaisesRegex(QRImageError, 'QR_IMAGE_SIZE'):
                decode_qr_image(encode_image(qr_image()))


class QRImageWebhookTests(unittest.IsolatedAsyncioTestCase):
    async def send(self, image=None, *, decoded=URL, valid_signature=True, loading_error=None, classifier=None,
                   verdict='SUSPICIOUS', source=None):
        event = {'type': 'message', 'replyToken': 'test-reply',
                 'source': source or {'type': 'user', 'userId': USER},
                 'message': {'type': 'image', 'id': '123456789', 'quoteToken': 'test-quote'}}
        body = json.dumps({'events': [event]}).encode()
        secret = 'test-only-secret'

        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}

        signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
        line = Mock(spec=LineService)
        line.channel_access_token = 'test-only-token'
        line.show_loading_animation = AsyncMock(side_effect=loading_error)
        line.create_url_verification_flex_message.side_effect = lambda result: LineService.create_url_verification_flex_message(None, result)
        order = []
        line.show_loading_animation.side_effect = loading_error or (lambda *a, **kw: order.append('loading'))

        async def download(*args):
            order.append('download')
            return image if image is not None else encode_image(qr_image(decoded))

        async def check(*args, **kwargs):
            order.append('check')
            return {'verification_verdict': verdict, 'history_id': 'stored-qr'}

        line.reply_message.side_effect = lambda *a, **kw: order.append('reply')
        reader = AsyncMock(side_effect=download)
        verifier = AsyncMock(side_effect=check)
        classifier = classifier or Mock()
        with patch.object(webhook, 'settings', SimpleNamespace(line_channel_secret=secret)), \
             patch.object(webhook, 'LINE_SERVICE_AVAILABLE', True), \
             patch.object(webhook, 'get_line_service', return_value=line), \
             patch.object(webhook, '_download_line_image', reader), \
             patch.object(webhook, '_check_link_request', verifier), \
             patch.object(webhook, 'get_image_classifier_service', return_value=classifier) as classifier_factory, \
             patch.object(webhook, 'get_fraud_detector') as old_detector, \
             patch.object(webhook, 'get_id_card_service') as id_cards:
            id_cards.return_value.verify_id_card.return_value = {'success': False}
            if not valid_signature:
                with self.assertRaises(webhook.HTTPException):
                    await webhook.webhook(Request({'type': 'http'}, receive), BackgroundTasks(), 'invalid')
            else:
                await webhook.webhook(Request({'type': 'http'}, receive), BackgroundTasks(), signature)
        old_detector.assert_not_called()
        return line, verifier, reader, classifier_factory, id_cards, order

    async def test_loading_then_real_qr_then_same_miniapp_pipeline_and_flex_for_every_verdict(self):
        for verdict, color in [('SUSPICIOUS', '#FF3B30'), ('MALICIOUS', '#FF3B30'),
                               ('NO_THREAT_FOUND', '#4AB918'), ('INCOMPLETE', '#FF9500'), ('INVALID', '#FF9500')]:
            with self.subTest(verdict=verdict):
                line, verify, download, classifier, ids, order = await self.send(verdict=verdict)
                self.assertEqual(order, ['loading', 'download', 'check', 'reply'])
                line.show_loading_animation.assert_awaited_once_with(USER, loading_seconds=30)
                download.assert_awaited_once_with('123456789', 'test-only-token')
                request = verify.call_args.args[0]
                self.assertEqual((request.message, request.message_type, request.user_id), (URL, 'qr', USER))
                self.assertTrue(verify.call_args.kwargs['persist_history_before_return'])
                reply = line.reply_message.call_args.kwargs
                self.assertEqual(reply['quote_token'], 'test-quote')
                self.assertIn('historyId=stored-qr', reply['flex_message']['contents']['body']['action']['uri'])
                self.assertEqual(reply['flex_message']['contents']['styles']['body']['backgroundColor'], color)
                classifier.assert_not_called()
                ids.assert_not_called()

    async def test_loading_failure_does_not_block_qr_verification(self):
        line, verifier, *_ = await self.send(loading_error=RuntimeError('test error'))
        verifier.assert_awaited_once()
        line.reply_message.assert_called_once()

    async def test_bad_signature_never_downloads_decodes_or_verifies(self):
        line, verifier, download, *_ = await self.send(valid_signature=False)
        line.show_loading_animation.assert_not_awaited()
        verifier.assert_not_awaited()
        download.assert_not_awaited()

    async def test_non_url_qr_is_not_sent_to_the_url_verifier(self):
        line, verifier, *_ = await self.send(decoded='plain text not a URL')
        verifier.assert_not_awaited()
        self.assertIn('ไม่ได้เป็นลิงก์', line.reply_message.call_args.kwargs['text'])

    async def test_unsupported_url_reaches_same_safety_checks_not_an_ai_rewrite(self):
        line, verifier, *_ = await self.send(decoded='file:///etc/passwd', verdict='INVALID')
        self.assertEqual(verifier.call_args.args[0].message, 'file:///etc/passwd')
        self.assertEqual(line.reply_message.call_args.kwargs['flex_message']['contents']['styles']['body']['backgroundColor'], '#FF9500')

    async def test_undecodable_qr_never_uses_classifier_guessed_url(self):
        classifier = Mock()
        classifier.classify_image.return_value = {'image_type': 'qr_code', 'qr_url': 'https://guessed.example/'}
        blank = encode_image(Image.new('RGB', (300, 300), 'white'))
        line, verifier, *_ = await self.send(image=blank, classifier=classifier)
        verifier.assert_not_awaited()
        self.assertIn('ไม่สามารถอ่าน QR Code', line.reply_message.call_args.kwargs['text'])

    async def test_invalid_image_is_not_a_success_or_a_database_write(self):
        line, verifier, *_ = await self.send(image=b'invalid')
        verifier.assert_not_awaited()
        self.assertIn('ไม่สามารถอ่านภาพ', line.reply_message.call_args.kwargs['text'])

    async def test_general_and_id_card_images_preserve_existing_non_qr_behavior(self):
        for image_type in ['general', 'id_card']:
            classifier = Mock()
            classifier.classify_image.return_value = {'image_type': image_type}
            line, verifier, _, _, ids, _ = await self.send(
                image=encode_image(Image.new('RGB', (300, 300), 'white')), classifier=classifier)
            verifier.assert_not_awaited()
            if image_type == 'general':
                ids.assert_not_called()
                line.reply_message.assert_not_called()
            else:
                ids.return_value.verify_id_card.assert_called_once()
                self.assertIn('ไม่สามารถอ่านบัตรประชาชน', line.reply_message.call_args.kwargs['text'])


class QRImageDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, handler, message_id='123'):
        real_client = httpx.AsyncClient
        factory = Mock(side_effect=lambda **options: real_client(transport=httpx.MockTransport(handler), **options))
        with patch.object(webhook.httpx, 'AsyncClient', factory):
            result = await webhook._download_line_image(message_id, 'test-only-token')
        return result, factory

    async def test_fixed_line_host_token_and_no_redirects(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, content=b'image')
        result, factory = await self.invoke(handle)
        self.assertEqual(result, b'image')
        self.assertEqual(str(requests[0].url), 'https://api-data.line.me/v2/bot/message/123/content')
        self.assertEqual(requests[0].headers['authorization'], 'Bearer test-only-token')
        self.assertFalse(factory.call_args.kwargs['follow_redirects'])
        self.assertFalse(factory.call_args.kwargs['trust_env'])

    async def test_http_failures_oversized_content_and_untrusted_ids_fail(self):
        for status in [302, 401, 404, 500]:
            with self.assertRaises(httpx.HTTPStatusError):
                await self.invoke(lambda request: httpx.Response(status, headers={'location': 'https://other.example/'}))
        with patch.object(webhook, 'MAX_QR_IMAGE_BYTES', 2):
            with self.assertRaisesRegex(QRImageError, 'QR_IMAGE_SIZE'):
                await self.invoke(lambda request: httpx.Response(200, content=b'123'))
        for value in ['../../private', 'x?token=other', 'a' * 129]:
            with self.assertRaises(QRImageError):
                await self.invoke(lambda request: httpx.Response(200, content=b'123'), value)
