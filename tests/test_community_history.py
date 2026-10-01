"""Shared posts/private History and identity checks; no live users or keys."""
import copy
import base64
from io import BytesIO
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists
from PIL import Image

from src.backend.routers import community, history, fraud, blacklist
from src.backend.services import user_identity_service as identity


class Document:
    def __init__(self, collection, key):
        self.collection, self.id = collection, key

    @property
    def exists(self):
        return self.id in self.collection.records

    def get(self, **kwargs):
        return self

    def to_dict(self):
        return copy.deepcopy(self.collection.records.get(self.id, {}))

    def create(self, data, **kwargs):
        if self.exists:
            raise AlreadyExists('test duplicate')
        self.collection.records[self.id] = copy.deepcopy(data)


class Collection:
    def __init__(self):
        self.records, self.filters, self.cursor, self.size = {}, [], None, 100

    def document(self, key):
        return Document(self, key)

    def order_by(self, *args, **kwargs):
        return self

    def where(self, *, filter):
        self.filters = [(filter.field_path, filter.value)]
        return self

    def limit(self, size):
        self.size = size
        return self

    def offset(self, value):
        return self

    def select(self, fields):
        return self

    def start_after(self, doc):
        self.cursor = doc.id
        return self

    def stream(self, **kwargs):
        rows = sorted(self.records, key=lambda key: (self.records[key]['created_at'], key), reverse=True)
        if self.cursor:
            rows = rows[rows.index(self.cursor) + 1:]
        return [self.document(key) for key in rows
                if all(self.records[key].get(field) == value for field, value in self.filters)][:self.size]

    def count(self):
        return SimpleNamespace(get=lambda **kw: [[SimpleNamespace(value=len(self.stream()))]])


class CommunityHistoryTests(unittest.TestCase):
    def setUp(self):
        self.posts, self.history = Collection(), Collection()
        self.service = SimpleNamespace(db=SimpleNamespace(collection=lambda name:
            self.posts if name == community.COLLECTION else self.history))
        self.app = FastAPI()
        self.app.state.limiter = community.limiter
        self.app.include_router(community.router)
        self.app.include_router(history.router)

        async def session(x_test_user: str = Header(default='')):
            if not x_test_user:
                raise HTTPException(401, 'Login required')
            return identity.UserIdentity(x_test_user, 'Verified member ' + x_test_user)
        self.app.dependency_overrides[identity.require_user] = session
        self.client = TestClient(self.app)
        for module in [community, history]:
            patcher = patch.object(module, 'get_database_service', return_value=self.service)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Rate-limit behavior is tested separately; isolate these database cases.
        self.app.state.limiter.enabled = False
        self.addCleanup(setattr, self.app.state.limiter, 'enabled', True)

    def post(self, user='A', **body):
        return self.client.post('/community/posts', headers={'X-Test-User': user},
                                json={'content': 'A real shared post', 'request_id': str(uuid4()), **body})

    def test_post_is_visible_to_other_accounts_and_anonymous_feed_without_owner_id(self):
        posted = self.post().json()
        for headers in [{}, {'X-Test-User': 'B'}]:
            response = self.client.get('/community/posts', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(response.json()['posts'][0], posted)
            self.assertNotIn('author_id', response.text)
        self.assertEqual(posted['author'], 'Verified member A')

    def test_post_requires_login_and_rejects_forged_author_empty_and_oversized_content(self):
        self.assertEqual(self.post(user='').status_code, 401)
        for body in [{'author': 'Someone else'}, {'content': '  '}, {'content': 'x' * 2001}]:
            self.assertEqual(self.post(**body).status_code, 422)
        self.assertEqual(len(self.posts.records), 0)

    def test_lost_response_retry_does_not_duplicate_and_request_id_is_user_scoped(self):
        key = str(uuid4())
        first = self.post(request_id=key)
        second = self.post(request_id=key)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(self.posts.records), 1)
        self.assertEqual(self.post(request_id=key, content='Changed draft').status_code, 409)
        self.assertEqual(self.post(user='B', request_id=key).status_code, 200)
        self.assertEqual(len(self.posts.records), 2)

    def test_pagination_is_bounded_and_uses_cursor(self):
        for number in range(3):
            self.posts.records[str(number) * 64] = {'content': str(number), 'author': 'A',
                'created_at': datetime(2026, 1, number + 1, tzinfo=timezone.utc)}
        response = self.client.get('/community/posts?limit=2').json()
        self.assertEqual([post['content'] for post in response['posts']], ['2', '1'])
        following = self.client.get('/community/posts?limit=2&after=' + response['next_cursor']).json()
        self.assertEqual([post['content'] for post in following['posts']], ['0'])
        self.assertEqual(self.client.get('/community/posts?limit=999').status_code, 422)
        self.assertEqual(self.client.get('/community/posts?after=bad').status_code, 422)

    def test_history_list_and_detail_are_owner_only_without_trusting_user_id(self):
        now = datetime.now(timezone.utc)
        for owner in ['A', 'B']:
            self.history.records[owner] = {'user_id': owner, 'message_text': 'Private ' + owner,
                'created_at': now, 'type': 'text'}
        self.assertEqual(self.client.get('/cache-entries').status_code, 401)
        self.assertEqual(self.client.get('/history/A').status_code, 401)
        self.assertEqual(self.client.get('/history/A', headers={'X-Test-User': 'B'}).status_code, 404)
        self.assertEqual(self.client.get('/cache-entries?user_id=A', headers={'X-Test-User': 'B'}).status_code, 403)
        response = self.client.get('/cache-entries', headers={'X-Test-User': 'A'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertEqual([post['id'] for post in response.json()['entries']], ['A'])
        self.assertEqual(self.client.get('/history/A', headers={'X-Test-User': 'A'}).status_code, 200)

    def test_database_error_is_explicit_not_a_mock_success(self):
        with patch.object(self.posts, 'order_by', side_effect=RuntimeError('private diagnostic')):
            response = self.client.get('/community/posts')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private diagnostic', response.text)

    def test_history_ui_can_skip_unused_count_without_weakening_ownership(self):
        with patch.object(self.history, 'count', side_effect=RuntimeError('Count must not run')):
            result = self.client.get('/cache-entries?include_total=false', headers={'X-Test-User': 'A'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['entries'], [])
        self.assertIsNone(result.json()['total'])
        self.assertFalse(result.json()['total_exact'])

    def image(self, color='green', size=(30, 30), format='PNG'):
        output = BytesIO()
        Image.new('RGB', size, color).save(output, format=format)
        return base64.b64encode(output.getvalue()).decode()

    def test_image_post_is_shared_jpeg_not_inlined_in_feed_and_can_be_image_only(self):
        posted = self.post(content='', image=self.image())
        self.assertEqual(posted.status_code, 200)
        self.assertTrue(posted.json()['has_image'])
        key = posted.json()['id']
        feed = self.client.get('/community/posts').json()['posts'][0]
        self.assertEqual(feed, posted.json())
        self.assertNotIn('image', feed)
        response = self.client.get(f'/community/posts/{key}/image')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'image/jpeg')
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        self.assertLessEqual(len(response.content), 128 * 1024)
        with Image.open(BytesIO(response.content)) as image:
            self.assertEqual(image.format, 'JPEG')

    def test_image_retry_is_idempotent_and_different_image_cannot_overwrite(self):
        key, image = str(uuid4()), self.image()
        first = self.post(request_id=key, image=image)
        self.assertEqual(first.json(), self.post(request_id=key, image=image).json())
        self.assertEqual(self.post(request_id=key, image=self.image('red')).status_code, 409)
        self.assertEqual(len(self.posts.records), 1)

    def test_invalid_oversized_svg_animation_and_excessive_pixels_never_persist(self):
        for image in ['broken base64', base64.b64encode(b'<svg onload="alert(1)"></svg>').decode(),
                      self.image(size=(2000, 1600)), self.image(format='GIF'), 'a' * 180000]:
            with self.subTest(image_kind=len(image)):
                self.assertEqual(self.post(image=image).status_code, 422)
        self.assertEqual(len(self.posts.records), 0)

    def test_post_body_limit_enforced_even_without_truthful_content_length(self):
        response = self.client.post('/community/posts', headers={'X-Test-User': 'A', 'Content-Length': '1'},
                                    content=b'x' * (256 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(len(self.posts.records), 0)

    def test_images_require_a_valid_post_id_and_exist(self):
        self.assertEqual(self.client.get('/community/posts/not-an-id/image').status_code, 422)
        self.assertEqual(self.client.get('/community/posts/' + 'a' * 64 + '/image').status_code, 404)

    def test_image_exif_metadata_is_stripped(self):
        output = BytesIO()
        exif = Image.Exif()
        exif[270] = 'test metadata not for publishing'
        Image.new('RGB', (30, 30), 'green').save(output, 'JPEG', exif=exif)
        posted = self.post(image=base64.b64encode(output.getvalue()).decode()).json()
        response = self.client.get(f'/community/posts/{posted["id"]}/image')
        with Image.open(BytesIO(response.content)) as image:
            self.assertFalse(image.getexif())


class IdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_unsupported_expired_and_wrong_channel_sessions_fail_closed(self):
        for headers in [('', ''), ('Bearer token', 'other')]:
            with self.assertRaises(HTTPException) as error:
                await identity.require_user(*headers)
            self.assertEqual(error.exception.status_code, 401)
        for value in [{'client_id': 'wrong', 'expires_in': 30},
                      {'client_id': identity.settings.line_login_channel_id, 'expires_in': 0}]:
            client = AsyncMock()
            client.get.return_value = httpx.Response(200, json=value)
            with patch.object(identity.httpx, 'AsyncClient') as factory:
                factory.return_value.__aenter__.return_value = client
                with self.assertRaises(HTTPException) as error:
                    await identity.verify_line_identity('test-token')
            self.assertEqual(error.exception.status_code, 401)
            self.assertEqual(client.get.await_count, 1)

    async def test_line_identity_comes_from_verified_profile(self):
        client = AsyncMock()
        client.get.side_effect = [httpx.Response(200, json={
            'client_id': identity.settings.line_login_channel_id, 'expires_in': 30}),
            httpx.Response(200, json={'userId': 'A', 'displayName': 'Verified A'})]
        with patch.object(identity.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            user = await identity.require_user('Bearer test-token', 'line')
        self.assertEqual(user, identity.UserIdentity('A', 'Verified A'))

    async def test_provider_unavailable_does_not_accept_identity(self):
        with patch.object(identity, 'verify_line_identity', side_effect=httpx.ReadTimeout('test')):
            with self.assertRaises(HTTPException) as error:
                await identity.require_user('Bearer test-token', 'line')
        self.assertEqual(error.exception.status_code, 503)

    async def test_firebase_signature_verification_is_required_and_audience_is_our_project(self):
        with patch.object(identity.settings, 'firestore_project_id', 'test-project'), patch.object(
            identity.id_token, 'verify_firebase_token', return_value={'sub': 'firebase-user', 'name': 'Name'}) as verify:
            user = await identity.require_user('Bearer test-token', 'firebase')
        self.assertEqual(user.user_id, 'firebase-user')
        self.assertEqual(verify.call_args.kwargs['audience'], 'test-project')
        with patch.object(identity.id_token, 'verify_firebase_token', side_effect=ValueError('bad signature')):
            with self.assertRaises(HTTPException) as error:
                await identity.require_user('Bearer test-token', 'firebase')
        self.assertEqual(error.exception.status_code, 401)

    async def test_scan_cannot_write_history_using_an_unverified_user_id(self):
        app = FastAPI()
        app.state.limiter = fraud.limiter
        app.include_router(fraud.router)
        response = TestClient(app).post('/check-fraud', json={
            'message': 'example.com', 'message_type': 'link', 'user_id': 'victim'})
        self.assertEqual(response.status_code, 401)

    async def test_personal_checks_cannot_spoof_history_owner(self):
        app = FastAPI()
        app.state.limiter = blacklist.limiter
        app.include_router(blacklist.router)
        for path, body in [('/check-phone', {'phone_number': '0812345678'}),
                           ('/check-bank', {'bank_code': 'KBANK', 'account_number': '1234567890'})]:
            response = TestClient(app).post(path, json={**body, 'user_id': 'victim'})
            self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
