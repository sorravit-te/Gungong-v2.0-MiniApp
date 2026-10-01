import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers';
import { loadHistory } from '../src/utils/script.js';

globalThis.window = { liff: { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' } };

test('history skips unused count, enforces verified auth and retries a transient read once', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return calls.length === 1 ? new Response('{}', { status: 503 })
      : new Response(JSON.stringify({ entries: [{ id: 'owner-record' }] }));
  };
  try {
    assert.deepEqual(await loadHistory(), [{ id: 'owner-record' }]);
    assert.equal(calls.length, 2);
    assert.match(calls[0].url, /include_total=false/u);
    assert.doesNotMatch(calls[0].url, /user_id/u);
    assert.equal(calls[0].options.headers.Authorization, 'Bearer test-only-token');
    assert.equal(calls[0].options.cache, 'no-store');
  } finally { globalThis.fetch = original; }
});

test('401 and malformed history are not retried or represented as an empty success', async () => {
  const original = globalThis.fetch;
  try {
    for (const [status, body, expected] of [[401, '{}', /LOGIN_REQUIRED/u], [200, '{}', /HISTORY_UNAVAILABLE/u]]) {
      let count = 0;
      globalThis.fetch = async () => { count += 1; return new Response(body, { status }); };
      await assert.rejects(loadHistory(), expected);
      assert.equal(count, 1);
    }
  } finally { globalThis.fetch = original; }
});

test('history deadline covers a stalled body and aborts without further requests; timer cleaned up', async () => {
  const originals = { fetch, setTimeout, clearTimeout };
  const timers = [];
  const cleared = [];
  let signal;
  globalThis.setTimeout = (callback, delay) => { const timer = { callback, delay }; timers.push(timer); return timer; };
  globalThis.clearTimeout = timer => cleared.push(timer);
  globalThis.fetch = async (_url, options) => {
    signal = options.signal;
    return { ok: true, status: 200, json: () => new Promise(() => {}) };
  };
  try {
    const pending = loadHistory();
    const rejected = assert.rejects(pending, /REQUEST_TIMEOUT/u);
    await new Promise(resolve => setImmediate(resolve));
    const deadline = timers.find(timer => timer.delay === 15000);
    deadline.callback();
    await rejected;
    assert.equal(signal.aborted, true);
    assert.ok(cleared.includes(deadline));
  } finally { Object.assign(globalThis, originals); }
});
