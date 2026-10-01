import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { getSessionHeaders } from '../src/utils/session.js';
import { getCommunityImageUrl, loadCommunity, postCommunity } from '../src/utils/community.js';
import { validateImageFile } from '../src/utils/communityImage.js';

test('public feed is real bounded API data, with encoded cursor and no author identity', async () => {
  globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' } };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ posts: [{ id: 'one', content: '<script>literal</script>' }], next_cursor: null }));
  };
  try {
    const feed = await loadCommunity('cursor/value');
    assert.equal(feed.posts[0].content, '<script>literal</script>');
    assert.equal(calls[0].url, 'https://app.test/community/posts?after=cursor%2Fvalue');
    assert.equal(calls[0].options.cache, 'no-store');
    assert.ok(calls[0].options.signal instanceof AbortSignal);
    assert.equal(calls[0].options.headers, undefined);
  } finally { globalThis.fetch = original; }
});

test('posting sends verified session token, same retry ID, and no forged author/user ID', async () => {
  globalThis.window.liff = { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options); return new Response(JSON.stringify({ id: 'saved', content: 'Post' }));
  };
  try {
    await postCommunity('Post', 'stable-id'); await postCommunity('Post', 'stable-id');
    assert.deepEqual(JSON.parse(calls[0].body), { content: 'Post', request_id: 'stable-id' });
    assert.equal(calls[0].body, calls[1].body);
    assert.equal(calls[0].headers.Authorization, 'Bearer test-only-token');
    assert.equal(calls[0].headers['X-Auth-Provider'], 'line');
  } finally { globalThis.fetch = original; delete globalThis.window.liff; }
});

test('anonymous session cannot post and failed reads do not become mock success', async () => {
  await assert.rejects(getSessionHeaders(), /LOGIN_REQUIRED/u);
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('{}', { status: 503 });
  try { await assert.rejects(loadCommunity(), /COMMUNITY_UNAVAILABLE/u); }
  finally { globalThis.fetch = original; }
});

test('community/history refresh on return and only render user text, no mock interactions', () => {
  const social = readFileSync(new URL('../src/components/social.jsx', import.meta.url), 'utf8');
  const history = readFileSync(new URL('../src/components/history.jsx', import.meta.url), 'utf8');
  for (const source of [social, history]) {
    assert.match(source, /visibilitychange/u);
    assert.match(source, /addEventListener\('focus'/u);
    assert.match(source, /removeEventListener\('focus'/u);
    assert.match(source, /30000/u);
  }
  assert.doesNotMatch(social, /dangerouslySetInnerHTML|Somsak|post\.likes|post\.comments/u);
  assert.match(social, /\{post\.content\}/u);
});

test('composer is a dialog with attachment preview; old inline submit and copy are gone', () => {
  const social = readFileSync(new URL('../src/components/social.jsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  assert.match(social, /aria-haspopup="dialog"/u);
  assert.match(social, /element\.showModal\(\)/u);
  assert.match(social, /aria-labelledby="community-composer-title"/u);
  assert.match(social, /type="file" accept="image\/jpeg,image\/png,image\/webp"/u);
  assert.match(social, /ตัวอย่างภาพก่อนโพสต์/u);
  assert.match(social, /เอาภาพออก/u);
  assert.doesNotMatch(social, /โพสต์ในหน้านี้แสดงให้ผู้ใช้อื่นเห็น|ยังไม่มีโพสต์ เป็นคนแรก|add-post-btn/u);
  assert.match(css, /#social-page \.scanner-header h2 \{ margin-left: 0;/u);
});

test('post image URLs are same-origin, ID-bound and never user-controlled external URLs', () => {
  assert.equal(getCommunityImageUrl({ id: 'a'.repeat(64), has_image: true }),
    'https://app.test/community/posts/' + 'a'.repeat(64) + '/image');
  for (const id of ['https://evil.test/', '../escape', 'javascript:alert(1)']) {
    assert.equal(getCommunityImageUrl({ id, has_image: true }), null);
  }
  assert.equal(getCommunityImageUrl({ id: 'a'.repeat(64), has_image: false }), null);
});

test('attachments reject unsupported files and oversized originals before decoding', () => {
  assert.doesNotThrow(() => validateImageFile({ type: 'image/jpeg', size: 100 }));
  for (const file of [{ type: 'image/svg+xml', size: 100 }, { type: 'image/png', size: 11 * 1024 * 1024 },
                      { type: 'image/jpeg', size: 0 }]) assert.throws(() => validateImageFile(file));
});

test('image is carried in the same authenticated idempotent post, not a separate orphan upload', async () => {
  globalThis.window.liff = { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options); return new Response(JSON.stringify({ id: 'saved', has_image: true }));
  };
  try {
    await postCommunity('', 'stable-id', 'base64-fixture');
    assert.deepEqual(JSON.parse(calls[0].body), { content: '', request_id: 'stable-id', image: 'base64-fixture' });
    assert.equal(calls[0].headers['X-Auth-Provider'], 'line');
  } finally { globalThis.fetch = original; delete globalThis.window.liff; }
});
