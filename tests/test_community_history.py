"""Shared posts/private History and identity checks; no live users or keys."""
import copy
import asyncio
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
from google.api_core.exceptions import AlreadyExists, FailedPrecondition
from google.cloud import firestore
from PIL import Image

from src.backend.routers import community, history, fraud, blacklist
from src.backend.services import user_identity_service as identity


class Snapshot:
    def __init__(self, reference):
        self.reference, self.id = reference, reference.id
        self.exists = reference.exists
        self.update_time = reference._collection.versions.get(reference.id, 0)
        self.data = reference.to_dict()

    def to_dict(self):
        return copy.deepcopy(self.data)


class Document:
    def __init__(self, collection, key):
        self._collection, self.id = collection, key
        self.path = collection.path + '/' + key

    @property
    def exists(self):
        return self.id in self._collection.records

    def get(self, **kwargs):
        return Snapshot(self)

    def to_dict(self):
        return copy.deepcopy(self._collection.records.get(self.id, {}))

    def collection(self, name):
        return self._collection.children.setdefault((self.id, name), Collection(self.path + '/' + name))

    def create(self, data, **kwargs):
        if self.exists:
            raise AlreadyExists('test duplicate')
        self._collection.records[self.id] = copy.deepcopy(data)
        self._collection.versions[self.id] = self._collection.versions.get(self.id, 0) + 1


class Collection:
    def __init__(self, path='test'):
        self.records, self.filters, self.cursor, self.size = {}, [], None, 100
        self.path, self.versions, self.children = path, {}, {}
        self.reverse = True

    def document(self, key):
        return Document(self, key)

    def order_by(self, *args, **kwargs):
        self.reverse = kwargs.get('direction') == firestore.Query.DESCENDING
        self.cursor, self.size = None, 100
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
        rows = sorted((key for key in self.records if 'created_at' in self.records[key]),
                      key=lambda key: (self.records[key]['created_at'], key), reverse=self.reverse)
        if self.cursor:
            rows = rows[rows.index(self.cursor) + 1:]
        return [self.document(key).get() for key in rows
                if all(self.records[key].get(field) == value for field, value in self.filters)][:self.size]

    def count(self):
        return SimpleNamespace(get=lambda **kw: [[SimpleNamespace(value=len(self.stream()))]])


class FakeBatch:
    def __init__(self, db):
        self.db, self.writes = db, []

    def set(self, ref, data):
        self.writes.append(('set', ref, data, None))

    def create(self, ref, data):
        self.writes.append(('create', ref, data, None))

    def delete(self, ref):
        self.writes.append(('delete', ref, None, None))

    def update(self, ref, data, option=None):
        self.writes.append(('update', ref, data, option))

    def commit(self, **kwargs):
        self.db.commits += 1
        if self.db.conflict:
            callback, self.db.conflict = self.db.conflict, None
            callback()
            raise FailedPrecondition('simulated concurrent write')
        # Validate every precondition BEFORE changing any document.
        for kind, ref, data, option in self.writes:
            if option and ref._collection.versions.get(ref.id, 0) != option.last_update_time:
                raise FailedPrecondition('stale snapshot')
            if kind == 'create' and ref.exists:
                raise AlreadyExists('existing child')
        for kind, ref, data, option in self.writes:
            if kind == 'delete':
                ref._collection.records.pop(ref.id, None)
            elif kind == 'update':
                target = ref._collection.records[ref.id]
                for key, value in data.items():
                    if value is firestore.DELETE_FIELD:
                        target.pop(key, None)
                    else:
                        target[key] = copy.deepcopy(value)
            else:
                ref._collection.records[ref.id] = copy.deepcopy(data)
            ref._collection.versions[ref.id] = ref._collection.versions.get(ref.id, 0) + 1


class FakeDb:
    def __init__(self, posts, history):
        self.posts, self.history = posts, history
        self.commits, self.conflict = 0, None

    def collection(self, name):
        return self.posts if name == community.COLLECTION else self.history

    def batch(self):
        return FakeBatch(self)

    def write_option(self, **kwargs):
        return SimpleNamespace(**kwargs)

    def get_all(self, refs, **kwargs):
        return [ref.get() for ref in refs]


class CommunityHistoryTests(unittest.TestCase):
    def setUp(self):
        self.posts, self.history = Collection(community.COLLECTION), Collection('fraud_check_history')
        self.service = SimpleNamespace(db=FakeDb(self.posts, self.history))
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
        for body in [{'author': 'Someone else'}, {'author_picture_url': 'https://profile.line-scdn.net/forged'},
                     {'content': '  '}, {'content': 'x' * 2001}]:
            self.assertEqual(self.post(**body).status_code, 422)
        self.assertEqual(len(self.posts.records), 0)

    def test_verified_profile_picture_is_stored_and_returned_for_posts_and_comments(self):
        async def session(x_test_user: str = Header(default='')):
            return identity.UserIdentity(x_test_user, 'Member ' + x_test_user,
                                         'https://profile.line-scdn.net/test-' + x_test_user)
        self.app.dependency_overrides[identity.require_user] = session
        posted = self.post().json()
        self.assertEqual(posted['author_picture_url'], 'https://profile.line-scdn.net/test-A')
        feed = self.client.get('/community/posts').json()['posts'][0]
        self.assertEqual(feed['author_picture_url'], posted['author_picture_url'])
        self.assertIn('author_picture_url', community.PUBLIC_FIELDS)
        comment = self.action('POST', posted['id'], '/comments', 'B',
                              {'content': 'Comment', 'request_id': str(uuid4())}).json()['comment']
        self.assertEqual(comment['author_picture_url'], 'https://profile.line-scdn.net/test-B')
        self.assertIsNotNone(comment['created_at'])
        listed = self.action('GET', posted['id'], '/comments').json()['comments'][0]
        self.assertEqual(listed, comment)
        self.assertNotIn('author_id', listed)
        forged = self.action('POST', posted['id'], '/comments', 'B',
                             {'content': 'Comment', 'request_id': str(uuid4()), 'author_picture_url': 'forged'})
        self.assertEqual(forged.status_code, 422)

    def test_legacy_posts_and_comments_have_no_invented_profile_picture(self):
        posted = self.post().json()
        self.assertIsNone(posted['author_picture_url'])
        self.assertIsNone(community.public_comment(SimpleNamespace(id='old', to_dict=lambda: {
            'author': 'Legacy', 'content': 'Before avatars', 'created_at': datetime.now(timezone.utc)}))['author_picture_url'])

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

    def test_browser_image_cache_is_short_private_versioned_and_revalidated_after_deletion(self):
        posted = self.post(image=self.image()).json()
        key, version = posted['id'], posted['image_version']
        url = f'/community/posts/{key}/image?v={version}'
        response = self.client.get(url)
        self.assertEqual(response.headers['cache-control'], 'private, max-age=30, must-revalidate')
        etag = response.headers['etag']
        self.assertEqual(self.client.get(url, headers={'If-None-Match': etag}).status_code, 304)
        self.assertEqual(self.client.get(f'/community/posts/{key}/image?v=' + '0' * 64).status_code, 404)
        self.assertEqual(self.client.get(f'/community/posts/{key}/image?v=bad').status_code, 422)
        self.assertEqual(self.action('PATCH', key, body={'content': 'replacement', 'image': self.image('red'),
            'expected_revision': 0}).status_code, 200)
        self.assertEqual(self.client.get(url, headers={'If-None-Match': etag}).status_code, 404)
        self.assertEqual(self.action('DELETE', key).status_code, 200)
        self.assertEqual(self.client.get(f'/community/posts/{key}/image', headers={'If-None-Match': etag}).status_code, 404)
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

    def action(self, method, key, suffix='', user='A', body=None):
        return self.client.request(method, '/community/posts/' + key + suffix,
            headers={'X-Test-User': user}, **({'json': body} if body is not None else {}))

    def test_likes_are_member_scoped_idempotent_and_real_counts(self):
        key = self.post().json()['id']
        for member, expected in [('A', 1), ('A', 1), ('B', 2)]:
            result = self.action('PUT', key, '/like', member, {'liked': True})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['like_count'], expected)
        for _ in range(2):
            result = self.action('PUT', key, '/like', 'A', {'liked': False})
            self.assertEqual(result.json()['like_count'], 1)
        self.assertEqual(self.action('PUT', key, '/like', '', {'liked': True}).status_code, 401)
        self.assertEqual(self.action('PUT', key, '/like', 'A', {'liked': 'true'}).status_code, 422)

    def test_viewer_state_private_permissions_without_exposing_ids(self):
        key = self.post().json()['id']
        self.action('PUT', key, '/like', 'B', {'liked': True})
        for member, edit, liked in [('A', True, False), ('B', False, True)]:
            result = self.client.post('/community/posts/viewer-state',
                headers={'X-Test-User': member}, json={'post_ids': [key]})
            self.assertEqual(result.json(), {'states': {key: {'can_edit': edit, 'liked': liked}}})
            self.assertNotIn('author_id', result.text)
        self.assertEqual(self.client.post('/community/posts/viewer-state', json={'post_ids': [key]}).status_code, 401)

    def test_comment_retry_only_increments_once_and_no_author_spoofing(self):
        key, request_id = self.post().json()['id'], str(uuid4())
        body = {'content': 'A comment', 'request_id': request_id}
        first = self.action('POST', key, '/comments', 'B', body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), self.action('POST', key, '/comments', 'B', body).json())
        self.assertEqual(first.json()['comment_count'], 1)
        self.assertEqual(self.action('POST', key, '/comments', 'B', {**body, 'content': 'changed'}).status_code, 409)
        self.assertEqual(self.action('POST', key, '/comments', 'B', {**body, 'author_id': 'A'}).status_code, 422)
        listed = self.action('GET', key, '/comments').json()['comments']
        self.assertEqual(len(listed), 1)
        self.assertNotIn('author_id', listed[0])

    def test_only_owner_edits_image_text_and_deletes_no_resurrection(self):
        draft_id = str(uuid4())
        key = self.post(request_id=draft_id, image=self.image()).json()['id']
        body = {'content': 'Edited', 'expected_revision': 0, 'image': self.image('red')}
        self.assertEqual(self.action('PATCH', key, user='B', body=body).status_code, 403)
        edited = self.action('PATCH', key, body=body)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['revision'], 1)
        self.assertEqual(self.action('PATCH', key, body=body).status_code, 409)
        removed = self.action('PATCH', key, body={'content': 'Text only', 'expected_revision': 1, 'remove_image': True})
        self.assertFalse(removed.json()['has_image'])
        self.assertEqual(self.action('GET', key, '/image').status_code, 404)
        self.assertEqual(self.action('DELETE', key, user='B').status_code, 403)
        self.assertEqual(self.action('DELETE', key).status_code, 200)
        self.assertEqual(self.client.get('/community/posts').json()['posts'], [])
        for suffix in ['', '/image', '/comments']:
            self.assertEqual(self.action('GET', key, suffix).status_code, 404)
        self.assertEqual(self.action('PUT', key, '/like', body={'liked': True}).status_code, 404)
        self.assertEqual(self.post(request_id=draft_id, image=self.image()).status_code, 409)

    def test_reports_private_pending_not_auto_hiding_post(self):
        key = self.post().json()['id']
        for _ in range(2):
            result = self.action('PUT', key, '/report', 'B', {'reason': 'scam', 'details': 'Check please'})
            self.assertEqual(result.json(), {'reported': True, 'status': 'pending'})
        self.assertEqual(len(self.posts.document(key).collection('reports').records), 1)
        feed = self.client.get('/community/posts').json()['posts']
        self.assertEqual(len(feed), 1)
        self.assertNotIn('reporter_id', str(feed))
        self.assertNotIn('Check please', str(feed))

    def test_atomic_conflict_retries_without_losing_completed_counter(self):
        key = self.post().json()['id']
        def concurrent():
            self.posts.records[key]['like_count'] = 2
            self.posts.versions[key] += 1
        self.service.db.conflict = concurrent
        result = self.action('PUT', key, '/like', body={'liked': True})
        self.assertEqual(result.json()['like_count'], 3)
        self.assertEqual(self.service.db.commits, 2)
        self.assertEqual(len(self.posts.document(key).collection('likes').records), 1)

    def test_concurrent_deletion_rejects_child_write_after_retry(self):
        key = self.post().json()['id']
        def concurrent():
            self.posts.records[key]['deleted_at'] = datetime.now(timezone.utc)
            self.posts.versions[key] += 1
        self.service.db.conflict = concurrent
        result = self.action('POST', key, '/comments', body={'content': 'No resurrection', 'request_id': str(uuid4())})
        self.assertEqual(result.status_code, 404)
        self.assertEqual(self.posts.document(key).collection('comments').records, {})


class IdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_reads_overlap_but_identity_waits_for_both(self):
        started = set()
        both_started = asyncio.Event()
        async def read(url, **kwargs):
            started.add(url)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=1)
            data = {'client_id': identity.settings.line_login_channel_id, 'expires_in': 30} if '/verify' in url else {
                'userId': 'verified-owner', 'displayName': 'Member'}
            return httpx.Response(200, json=data)
        client = AsyncMock(); client.get.side_effect = read
        with patch.object(identity.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            result = await identity.require_user('Bearer test-token', 'line')
        self.assertEqual(result.user_id, 'verified-owner')
        self.assertEqual(len(started), 2)

    async def test_provider_failure_or_invalid_profile_never_authenticates(self):
        valid = httpx.Response(200, json={'client_id': identity.settings.line_login_channel_id, 'expires_in': 30})
        for verify_result, profile_result, expected in [
            (valid, httpx.Response(500), 503),
            (valid, httpx.ReadTimeout('synthetic timeout'), 503),
            (httpx.Response(400), httpx.Response(200, json={'userId': 'valid-profile'}), 401),
            (valid, httpx.Response(200, json={}), 401),
        ]:
            async def read(url, **kwargs):
                result = verify_result if '/verify' in url else profile_result
                if isinstance(result, Exception):
                    raise result
                return result
            client = AsyncMock(); client.get.side_effect = read
            with patch.object(identity.httpx, 'AsyncClient') as factory:
                factory.return_value.__aenter__.return_value = client
                with self.assertRaises(HTTPException) as failure:
                    await identity.require_user('Bearer test-token', 'line')
            self.assertEqual(failure.exception.status_code, expected)

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
            self.assertEqual(client.get.await_count, 2)

    async def test_line_identity_comes_from_verified_profile(self):
        client = AsyncMock()
        client.get.side_effect = [httpx.Response(200, json={
            'client_id': identity.settings.line_login_channel_id, 'expires_in': 30}),
            httpx.Response(200, json={'userId': 'A', 'displayName': 'Verified A'})]
        with patch.object(identity.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            user = await identity.require_user('Bearer test-token', 'line')
        self.assertEqual(user, identity.UserIdentity('A', 'Verified A'))

    async def test_line_picture_comes_from_the_verified_provider_not_request_fields(self):
        client = AsyncMock()
        client.get.side_effect = [httpx.Response(200, json={
            'client_id': identity.settings.line_login_channel_id, 'expires_in': 30}),
            httpx.Response(200, json={'userId': 'A', 'displayName': 'A',
                                     'pictureUrl': 'https://profile.line-scdn.net/avatar'})]
        with patch.object(identity.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            user = await identity.require_user('Bearer test-token', 'line')
        self.assertEqual(user.picture_url, 'https://profile.line-scdn.net/avatar')
        self.assertEqual(client.get.await_count, 2)
        for value in [None, 'javascript:alert(1)', 'http://profile.line-scdn.net/image',
                      'https://profile.line-scdn.net.evil.test/a', 'https://user:pass@profile.line-scdn.net/a']:
            self.assertIsNone(identity.safe_line_picture(value))

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
        with patch.object(identity.settings, 'firestore_project_id', 'test-project'), patch.object(
            identity.id_token, 'verify_firebase_token', side_effect=ValueError('bad signature')):
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
