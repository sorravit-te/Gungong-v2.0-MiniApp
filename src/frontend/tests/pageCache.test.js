import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createPageCache, historyCache, invalidateHistoryCache } from '../src/utils/pageCache.js';
import { loadHistory, callFraudCheckApi } from '../src/utils/script.js';
import { loadCommunity } from '../src/utils/community.js';

test('fresh page revisit returns the same real data with zero additional reads', async () => {
  const cache = createPageCache(); let calls = 0;
  const read = async () => { calls++; return [{ id: 'real-api-record' }]; };
  const first = await cache.read('owner-a', read);
  assert.equal(await cache.read('owner-a', read), first);
  assert.equal(calls, 1);
});

test('expiry retains visible data while one background refresh is pending', async () => {
  let time = 0; const cache = createPageCache({ ttl: 30, now: () => time });
  await cache.read('feed', async () => ['old']); time = 31;
  let finish; const refresh = cache.read('feed', () => new Promise(resolve => { finish = resolve; }));
  await Promise.resolve(); assert.deepEqual(cache.peek('feed'), ['old']);
  finish(['new']); await refresh; assert.deepEqual(cache.peek('feed'), ['new']);
});

test('StrictMode and concurrent subscribers share one in-flight load', async () => {
  const cache = createPageCache(); let calls = 0; let finish;
  const read = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  const first = cache.read('feed', read); const second = cache.read('feed', read);
  await Promise.resolve(); assert.equal(calls, 1); finish(['post']);
  assert.deepEqual(await Promise.all([first, second]), [['post'], ['post']]);
});

test('scheduled refresh preserves cached data and deduplicates a revisit during the refresh', async () => {
  const cache = createPageCache();
  cache.write('owner', ['previous']); cache.expire('owner');
  assert.deepEqual(cache.peek('owner'), ['previous']);
  let finish; let calls = 0;
  const loader = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  const first = cache.read('owner', loader);
  await Promise.resolve(); cache.expire('owner');
  const revisit = cache.read('owner', loader);
  assert.deepEqual(cache.peek('owner'), ['previous']);
  finish(['latest']); await Promise.all([first, revisit]);
  assert.equal(calls, 1); assert.deepEqual(cache.peek('owner'), ['latest']);
  cache.invalidate(); assert.equal(cache.peek('owner'), undefined);
});

test('periodic page refresh expires data without clearing the visible cache', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  assert.match(read('../src/hooks/useHistoryEntries.js'), /historyCache\.expire\(userId\)/u);
  assert.match(read('../src/components/social.jsx'), /communityCache\.expire\('feed'\)/u);
});

test('different owners never receive each other\'s History cache', async () => {
  const cache = createPageCache(); await cache.read('owner-a', async () => ['private-a']);
  assert.equal(cache.peek('owner-b'), undefined);
  assert.deepEqual(await cache.read('owner-b', async () => ['private-b']), ['private-b']);
});

test('logout invalidates a pending private read; late data cannot repopulate the cache', async () => {
  const cache = createPageCache(); let finish;
  const pending = cache.read('owner', () => new Promise(resolve => { finish = resolve; }));
  await Promise.resolve(); cache.invalidate(); finish(['private']);
  await assert.rejects(pending, /CACHE_INVALIDATED/u); assert.equal(cache.peek('owner'), undefined);
});

test('failed reads are retriable, not cached as empty success', async () => {
  const cache = createPageCache();
  await assert.rejects(cache.read('feed', async () => { throw new Error('offline'); }), /offline/u);
  assert.equal(cache.peek('feed'), undefined);
  assert.deepEqual(await cache.read('feed', async () => ['recovered']), ['recovered']);
});

test('transient refresh failure preserves stale data; 401 clears it', async () => {
  let time = 0; const cache = createPageCache({ ttl: 30, now: () => time });
  await cache.read('owner', async () => ['private']); time = 31;
  await assert.rejects(cache.read('owner', async () => { throw new Error('offline'); }));
  assert.deepEqual(cache.peek('owner'), ['private']);
  await assert.rejects(cache.read('owner', async () => { throw new Error('LOGIN_REQUIRED'); }));
  assert.equal(cache.peek('owner'), undefined);
});

test('publishing updates the shared feed and suppresses an older refresh response', async () => {
  const cache = createPageCache(); let finish;
  const pending = cache.read('feed', () => new Promise(resolve => { finish = resolve; }));
  await Promise.resolve(); cache.write('feed', { posts: ['new-post'], next_cursor: null });
  finish({ posts: [], next_cursor: null }); await assert.rejects(pending, /CACHE_INVALIDATED/u);
  assert.deepEqual(cache.peek('feed').posts, ['new-post']);
});

test('History and Community revisit caches wrap the actual API without rechecking URLs', async () => {
  globalThis.window = { liff: { isLoggedIn: () => true, getAccessToken: () => 'test-token' },
    location: { hostname: 'app.test', origin: 'https://app.test' } };
  const original = globalThis.fetch; const urls = [];
  globalThis.fetch = async url => { urls.push(url); return new Response(JSON.stringify(
    url.includes('/cache-entries') ? { entries: [{ id: 'stored', type: 'link' }] } : { posts: [{ id: 'post' }] })); };
  try {
    const history = createPageCache(); const feed = createPageCache();
    await history.read('owner', loadHistory); await history.read('owner', loadHistory);
    await feed.read('feed', loadCommunity); await feed.read('feed', loadCommunity);
    assert.equal(urls.length, 2);
    assert.ok(urls.every(url => !/check-fraud|history\//u.test(url)));
  } finally { globalThis.fetch = original; delete globalThis.window; }
});

test('successful scanner verification invalidates History so the next visit sees its new record', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ category: 'SAFE_NORMAL' }));
  globalThis.window = { liff: { isLoggedIn: () => false } };
  try {
    await historyCache.read('owner', async () => ['old']);
    await callFraudCheckApi('https://example.com', 'link', { getUserIdFn: async () => null });
    assert.equal(historyCache.peek('owner'), undefined);
  } finally { invalidateHistoryCache(); globalThis.fetch = original; delete globalThis.window; }
});

test('page cache contains no persistent browser storage; loader presentation is shared', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  assert.doesNotMatch(read('../src/utils/pageCache.js'), /localStorage|sessionStorage/u);
  assert.match(read('../src/components/social.jsx'), /role="status" className="page-loading"/u);
  assert.match(read('../src/hooks/useHistoryEntries.js'), /if \(authLoading\) return/u);
  assert.match(read('../src/components/history.jsx'), /useHistoryEntries\(\)/u);
  assert.match(read('../src/components/social.jsx'), /let refreshing = false/u);
  assert.match(read('../src/components/social.jsx'), /busy\.current = refreshOwner/u);
  assert.match(read('../src/components/social.jsx'), /if \(busy\.current === refreshOwner\) busy\.current = false/u);
});
