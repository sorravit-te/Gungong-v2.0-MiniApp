import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createLineFriendshipAction, LINE_OA_URL } from '../src/features/auth/lineFriendship.js';

function fixture({ sdkChanges = {}, friendFlag = true, timeoutMs = 20 } = {}) {
  const calls = [];
  const sdk = {
    id: 'test-liff-id',
    isInClient: () => true,
    isLoggedIn: () => true,
    getContext: () => ({ viewType: 'full' }),
    requestFriendship: async (...args) => { calls.push(['request', ...args]); },
    getFriendship: async (...args) => { calls.push(['status', ...args]); return { friendFlag }; },
    ...sdkChanges,
  };
  const action = createLineFriendshipAction({
    getSdk: () => sdk,
    fallback: async reason => calls.push(['fallback', reason]),
    onResult: async result => calls.push(['result', result]),
    onBusy: value => calls.push(['busy', value]),
    statusTimeoutMs: timeoutMs,
  });
  return { calls, sdk, action };
}

test('creating the action does no startup SDK/network work', () => {
  const { calls } = fixture();
  assert.deepEqual(calls, []);
});

test('native request starts on the tap, before any awaited profile/status calls', async () => {
  const { calls, action } = fixture();
  const pending = action();
  assert.deepEqual(calls, [['busy', true], ['request']]);
  assert.deepEqual(await pending, { mode: 'native', friendFlag: true });
  assert.deepEqual(calls, [
    ['busy', true], ['request'], ['status'],
    ['result', { mode: 'native', friendFlag: true }], ['busy', false],
  ]);
  // No officialAccount arguments: use the Thailand channel's linked OA.
});

test('cancel/not-added/blocked status is not converted into a success or fallback navigation', async () => {
  const { calls, action } = fixture({ friendFlag: false });
  assert.deepEqual(await action(), { mode: 'native', friendFlag: false });
  assert.equal(calls.some(([name]) => name === 'fallback'), false);
});

test('an existing friend is confirmed from getFriendship, not the void request result', async () => {
  const { action } = fixture({ sdkChanges: { requestFriendship: async () => undefined } });
  assert.deepEqual(await action(), { mode: 'native', friendFlag: true });
});

test('unsupported clients use the fallback without calling native/status APIs', async () => {
  for (const sdkChanges of [
    { id: null }, { isInClient: () => false }, { isLoggedIn: () => false },
    { getContext: () => ({ viewType: 'tall' }) },
    { getContext: () => ({ viewType: 'compact' }) },
    { getContext: () => null }, { getContext: undefined },
    { getContext: () => { throw new Error('INIT_FAILED'); } },
    { requestFriendship: undefined },
  ]) {
    const { calls, action } = fixture({ sdkChanges });
    assert.deepEqual(await action(), { mode: 'fallback' });
    assert.deepEqual(calls, [['busy', true], ['fallback', { reason: 'unsupported' }], ['busy', false]]);
  }
});

test('missing SDK does not initialize/login and still offers fallback', async () => {
  let reason;
  const action = createLineFriendshipAction({ getSdk: () => undefined,
    fallback: async value => { reason = value; } });
  assert.deepEqual(await action(), { mode: 'fallback' });
  assert.deepEqual(reason, { reason: 'unsupported' });
});

test('missing OA/unsupported native API/network failure offers fallback once, without retrying', async () => {
  for (const code of ['FORBIDDEN', 'INVALID_CONFIG', 'UNKNOWN', 500]) {
    let requests = 0;
    const { calls, action } = fixture({ sdkChanges: {
      requestFriendship: async () => { requests++; throw Object.assign(new Error('test'), { code }); },
    } });
    assert.deepEqual(await action(), { mode: 'fallback' });
    assert.equal(requests, 1);
    assert.ok(calls.some(([name, value]) => name === 'fallback' && value.reason === 'failed'));
    assert.equal(calls.some(([name]) => name === 'status' || name === 'result'), false);
    assert.deepEqual(calls.at(-1), ['busy', false]);
  }
});

test('failed/missing/invalid friendship check remains unknown, never a success/fallback', async () => {
  for (const getFriendship of [undefined,
    async () => { throw Object.assign(new Error('no profile consent'), { code: 403 }); },
    async () => undefined, async () => ({ friendFlag: 'true' }),
    async () => ({ friendFlag: 1 }),
  ]) {
    const { action, calls } = fixture({ sdkChanges: { getFriendship } });
    assert.deepEqual(await action(), { mode: 'native', friendFlag: null });
    assert.equal(calls.some(([name]) => name === 'fallback'), false);
  }
});

test('hung status check is bounded and releases the button without inventing success', async () => {
  const { action, calls } = fixture({ sdkChanges: { getFriendship: () => new Promise(() => {}) }, timeoutMs: 5 });
  assert.deepEqual(await action(), { mode: 'native', friendFlag: null });
  assert.deepEqual(calls.at(-1), ['busy', false]);
});

test('rapid taps cannot open duplicate native windows; another tap works after closure', async () => {
  let close;
  const { action, calls, sdk } = fixture({ sdkChanges: {
    requestFriendship: () => { calls.push(['request']); return new Promise(resolve => { close = resolve; }); },
  } });
  const first = action();
  assert.deepEqual(await action(), { mode: 'busy' });
  assert.equal(calls.filter(([name]) => name === 'request').length, 1);
  close(); await first;
  sdk.requestFriendship = async () => calls.push(['request']);
  await action();
  assert.equal(calls.filter(([name]) => name === 'request').length, 2);
});

test('the lock also covers an open fallback confirmation and verified-friend feedback', async () => {
  for (const inClient of [true, false]) {
    let finish;
    const action = createLineFriendshipAction({
      getSdk: () => ({ id: 'test', isInClient: () => inClient, isLoggedIn: () => true,
        getContext: () => ({ viewType: 'full' }), requestFriendship: async () => {},
        getFriendship: async () => ({ friendFlag: true }) }),
      fallback: () => new Promise(resolve => { finish = resolve; }),
      onResult: () => new Promise(resolve => { finish = resolve; }),
    });
    const pending = action();
    assert.deepEqual(await action(), { mode: 'busy' });
    // Flush the native status read when testing feedback.
    for (let i = 0; i < 8; i++) await Promise.resolve();
    assert.equal(typeof finish, 'function');
    finish(); await pending;
  }
});

test('optional dialog failure releases the action lock', async () => {
  let attempts = 0;
  const busy = [];
  const action = createLineFriendshipAction({ getSdk: () => undefined,
    onBusy: value => busy.push(value), fallback: async () => { attempts++; throw new Error('UI failed'); } });
  await assert.rejects(action(), /UI failed/u);
  await assert.rejects(action(), /UI failed/u);
  assert.equal(attempts, 2);
  assert.deepEqual(busy, [true, false, true, false]);
});

test('default SDK accessor works without a browser and reads the current SDK on each tap', async () => {
  const previous = globalThis.window;
  try {
    delete globalThis.window;
    const action = createLineFriendshipAction({ fallback: async () => {} });
    assert.deepEqual(await action(), { mode: 'fallback' });
    globalThis.window = { liff: fixture().sdk };
    assert.deepEqual(await action(), { mode: 'native', friendFlag: true });
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
});

test('the accessible header button preserves its look and only shows confirmed friendship', () => {
  const source = readFileSync(new URL('../src/shared/layout/TopBanner.jsx', import.meta.url), 'utf8');
  assert.match(source, /<button type="button" onClick=\{handleLineOAClick\}/u);
  assert.match(source, /aria-label="เพิ่มเพื่อน GunGong LINE OA" aria-busy=\{friendshipBusy\}/u);
  assert.match(source, /disabled=\{friendshipBusy \|\| \(lineLoading/u);
  assert.match(source, /if \(friendFlag === true && window.Swal\)/u);
  assert.match(source, /fallback: confirmLineOAFallback/u);
  assert.match(source, /preConfirm:.*window.open\(LINE_OA_URL, '_blank', 'noopener,noreferrer'\)/u);
  assert.match(source, /else if \(window.confirm\(text\)\)/u);
  assert.doesNotMatch(source, /requestFriendship\(\{\s*officialAccount|useEffect|localStorage|console\./u);
  assert.equal(LINE_OA_URL, 'https://line.me/R/ti/p/@357asclq');
});
