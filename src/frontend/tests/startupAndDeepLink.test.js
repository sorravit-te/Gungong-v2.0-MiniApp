import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import { getAppEntry, initializeLineSession } from '../src/features/auth/lineAuth.js';
import { createPageCache } from '../src/shared/cache/pageCache.js';
import { createHistoryStartup } from '../src/features/history/utils/historyStartup.js';
import { createHistoryDetailController } from '../src/features/history/utils/historyDetail.js';

test('old Flex URLs select History; malformed IDs never become a detail request', () => {
  assert.deepEqual(getAppEntry('?historyId=stored_123'), { section: 'history', historyId: 'stored_123' });
  assert.deepEqual(getAppEntry('?section=home&historyId=stored_123'), { section: 'history', historyId: 'stored_123' });
  assert.deepEqual(getAppEntry('?section=history'), { section: 'history', historyId: null });
  assert.deepEqual(getAppEntry('?section=https://evil.test&historyId=../private'), { section: 'home', historyId: null });
  assert.equal(getAppEntry('?historyId=' + 'a'.repeat(129)).historyId, null);
});

test('session-ready reads start after init but before a slow display profile finishes', async () => {
  let resolveProfile; let started = 0;
  const profile = { userId: 'owner' };
  globalThis.window = { location: { search: '?liff.state=callback' }, liff: {
    init: async () => { window.location.search = '?historyId=restored'; },
    isLoggedIn: () => true, getAccessToken: () => 'test-only-token',
    getProfile: () => new Promise(resolve => { resolveProfile = resolve; }),
  } };
  try {
    const session = initializeLineSession({ onSessionReady: () => { started++; } });
    await setImmediate();
    assert.equal(started, 1);
    assert.equal(getAppEntry(window.location.search).historyId, 'restored');
    resolveProfile(profile);
    assert.deepEqual(await session, profile);
  } finally { delete globalThis.window; }
});

test('anonymous initialization never prefetches private history', async () => {
  let started = 0;
  globalThis.window = { location: { search: '' }, liff: { init: async () => {}, isLoggedIn: () => false } };
  try {
    assert.equal(await initializeLineSession({ onSessionReady: () => { started++; } }), null);
    assert.equal(started, 0);
  } finally { delete globalThis.window; }
});

test('startup and page consumers share one real read; no owner cache before binding', async () => {
  const cache = createPageCache(); let reads = 0; let resolve;
  const startup = createHistoryStartup({ cache, load: () => { reads++; return new Promise(done => { resolve = done; }); } });
  startup.start(); startup.start(); await setImmediate();
  assert.equal(cache.peek('owner'), undefined);
  const bound = startup.bind('owner');
  const consumer = cache.read('owner', () => { throw new Error('duplicate read'); });
  resolve([{ id: 'stored' }]);
  assert.deepEqual(await bound, [{ id: 'stored' }]);
  assert.deepEqual(await consumer, [{ id: 'stored' }]);
  assert.equal(reads, 1); assert.equal(cache.peek('other'), undefined);
});

test('startup disposal/logout prevents late data from repopulating history', async () => {
  const cache = createPageCache(); let resolve;
  const startup = createHistoryStartup({ cache, load: () => new Promise(done => { resolve = done; }) });
  startup.start(); await setImmediate();
  const bound = startup.bind('owner'); await setImmediate();
  startup.dispose(); cache.invalidate(); resolve(['private']);
  await assert.rejects(bound, /CACHE_INVALIDATED/u);
  assert.equal(cache.peek('owner'), undefined);
});

test('prefetch failure is not cached as empty history and can be retried', async () => {
  const cache = createPageCache();
  const startup = createHistoryStartup({ cache, load: async () => { throw new Error('offline'); } });
  startup.start(); await setImmediate();
  await assert.rejects(startup.bind('owner'), /offline/u);
  assert.equal(cache.peek('owner'), undefined);
  assert.deepEqual(await cache.read('owner', async () => ['real']), ['real']);
});

test('a rotated/switched LINE session cannot adopt an earlier private response', async () => {
  const cache = createPageCache(); let resolve; let current = true;
  const startup = createHistoryStartup({ cache, isCurrent: () => current,
    load: () => new Promise(done => { resolve = done; }) });
  startup.start(); await setImmediate();
  const bound = startup.bind('owner'); await setImmediate();
  current = false; resolve(['old-session-private']);
  await assert.rejects(bound, /CACHE_INVALIDATED/u);
  assert.equal(cache.peek('owner'), undefined);
});

test('deep-link details read one owned record even outside the first 50 and never rescan', async () => {
  const calls = []; const popups = [];
  const flow = createHistoryDetailController({
    getDetail: async id => { calls.push(id); return { id, type: 'text', message_text: 'stored full message', is_safe: true, confidence_score: 99 }; },
    swal: { fire: popup => { popups.push(popup); }, showLoading() {}, close() {} }, typeName: type => type,
  });
  await flow.open({ id: 'older-record' }, { fetchDetail: true });
  assert.deepEqual(calls, ['older-record']);
  assert.match(popups[1].html, /stored full message/u);
  assert.doesNotMatch(popups[1].html, /ความมั่นใจ|99%/u);
  flow.dispose();
});

test('entrypoint keeps main visible; mobile chart and inconclusive cards use requested styles', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  assert.doesNotMatch(read('../index.html'), /deep-link-mode/u);
  assert.match(read('../src/App.jsx'), /getAppEntry\(window\.location\.search\)/u);
  assert.match(read('../src/App.jsx'), /communityCache\.read\('feed', loadCommunity\)/u);
  assert.match(read('../src/features/history/history.jsx'), /fetchDetail: true/u);
  const css = read('../src/features/history/history.css');
  assert.match(css, /\.h-icon\.icon-unknown\s*\{\s*background-color: #FBBF24;/u);
  assert.match(css, /\.history-card\.unknown \.card-date-block\s*\{\s*background: linear-gradient\(135deg, #fffbeb/u);
  const chart = read('../src/features/home/dataVisualization.css');
  assert.match(chart, /\.summary-viz-card \.summary-segment-count/u);
  assert.match(chart, /fill: var\(--summary-caption-color\) !important/u);
  assert.match(read('../src/features/home/components/DataVisualization.jsx'), /loading && summary\.total === 0/u);
  for (const path of ['../src/features/scanner/scanner.jsx', '../src/features/scanner/ScanImage.jsx', '../src/features/history/utils/historyDetail.js']) {
    assert.doesNotMatch(read(path), /ความมั่นใจ/u);
  }
});
