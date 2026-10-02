import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import { initializeLineSession, loginWithLine, logoutFromLine, getLineLoginRedirect,
  getDisplayUser, getLineAuthError, LINE_ENDPOINT_URL } from '../src/features/auth/lineAuth.js';
import { getSessionHeaders } from '../src/features/auth/session.js';

function fixture({ loggedIn = false, inClient = false } = {}) {
  const calls = { init: [], login: [], logout: 0, profile: 0 };
  const profile = { userId: 'same-line-user', displayName: 'สมาชิก LINE', pictureUrl: 'https://profile.test/avatar' };
  const sdk = {
    init: async config => { calls.init.push(config); },
    isLoggedIn: () => loggedIn,
    isInClient: () => inClient,
    getAccessToken: () => loggedIn ? 'test-only-token' : null,
    getProfile: async () => { calls.profile++; return profile; },
    login: config => calls.login.push(config),
    logout: () => { calls.logout++; },
  };
  globalThis.window = { liff: sdk, location: { search: '' } };
  return { sdk, calls, profile };
}

test('anonymous desktop initializes without forcing login or profile reads', async () => {
  const { calls } = fixture();
  assert.equal(await initializeLineSession(), null);
  assert.deepEqual(calls.init, [{ liffId: '2008548759-KkM4Noxa' }]);
  assert.equal(calls.login.length, 0);
  assert.equal(calls.profile, 0);
});

test('StrictMode/concurrent initialization uses one SDK init, not parallel auth redirects', async () => {
  const { calls } = fixture();
  await Promise.all([initializeLineSession(), initializeLineSession()]);
  assert.equal(calls.init.length, 1);
  assert.equal(calls.login.length, 0);
});

test('desktop button logs in once AFTER init, returning to the same approved app section', async () => {
  const { sdk, calls } = fixture();
  const order = [];
  sdk.init = async config => { order.push('init'); calls.init.push(config); };
  sdk.login = config => { order.push('login'); calls.login.push(config); };
  await loginWithLine({ section: 'history' });
  assert.deepEqual(order, ['init', 'login']);
  assert.deepEqual(calls.login, [{ redirectUri: LINE_ENDPOINT_URL + '?section=history' }]);
});

test('completed desktop callback reads the same LINE profile and session as mobile', async () => {
  const { calls, profile } = fixture({ loggedIn: true });
  assert.deepEqual(await initializeLineSession(), profile);
  assert.deepEqual(await getSessionHeaders(), { Authorization: 'Bearer test-only-token', 'X-Auth-Provider': 'line' });
  await loginWithLine();
  assert.equal(calls.init.length, 1);
  assert.equal(calls.login.length, 0);
});

test('LINE-client initialization preserves automatic login, never calling liff.login again', async () => {
  const { calls, profile } = fixture({ loggedIn: true, inClient: true });
  assert.deepEqual(await initializeLineSession(), profile);
  assert.deepEqual(await loginWithLine(), profile);
  assert.equal(calls.login.length, 0);
});

test('redirect target is fixed; credentials and arbitrary redirect/section values are not forwarded', () => {
  const redirect = new URL(getLineLoginRedirect('history',
    '?historyId=record_123&access_token=secret&code=secret&state=secret&redirect=https://evil.test'));
  assert.equal(redirect.origin, new URL(LINE_ENDPOINT_URL).origin);
  assert.deepEqual([...redirect.searchParams], [['section', 'history'], ['historyId', 'record_123']]);
  assert.equal(getLineLoginRedirect('https://evil.test', '?historyId=../../secret'), LINE_ENDPOINT_URL);
});

test('failed init may retry but never starts login after an init failure', async () => {
  const { sdk, calls } = fixture();
  let attempts = 0;
  sdk.init = async () => { if (++attempts === 1) throw new Error('INIT_FAILED'); };
  await assert.rejects(loginWithLine(), /INIT_FAILED/u);
  assert.equal(calls.login.length, 0);
  await loginWithLine();
  assert.equal(attempts, 2);
  assert.equal(calls.login.length, 1);
});

test('hung init is bounded and retry does not start a second overlapping SDK init', async () => {
  const { sdk, calls } = fixture();
  sdk.init = config => { calls.init.push(config); return new Promise(() => {}); };
  await assert.rejects(initializeLineSession({ timeoutMs: 5 }), /LINE_SESSION_TIMEOUT/u);
  await assert.rejects(loginWithLine({ timeoutMs: 5 }), /LINE_SESSION_TIMEOUT/u);
  assert.equal(calls.init.length, 1);
  assert.equal(calls.login.length, 0);
});

test('hung getProfile is bounded and cannot fabricate a signed-in identity', async () => {
  const { sdk } = fixture({ loggedIn: true });
  sdk.getProfile = () => new Promise(() => {});
  await assert.rejects(initializeLineSession({ timeoutMs: 5 }), /LINE_SESSION_TIMEOUT/u);
});

test('an init completing AFTER the UI deadline cannot trigger a surprise login redirect', async () => {
  const { sdk, calls } = fixture();
  let finish;
  sdk.init = () => new Promise(resolve => { finish = resolve; });
  await assert.rejects(loginWithLine({ timeoutMs: 5 }), /LINE_SESSION_TIMEOUT/u);
  finish(); await setImmediate();
  assert.equal(calls.login.length, 0);
  assert.equal(calls.profile, 0);
});

test('successful and rejected operations clear their timeout timers', async () => {
  const originalSet = globalThis.setTimeout;
  const originalClear = globalThis.clearTimeout;
  const timers = new Set();
  globalThis.setTimeout = (...args) => { const timer = originalSet(...args); timers.add(timer); return timer; };
  globalThis.clearTimeout = timer => { timers.delete(timer); return originalClear(timer); };
  try {
    fixture(); await initializeLineSession();
    assert.equal(timers.size, 0);
    const { sdk } = fixture(); sdk.init = async () => { throw new Error('failure'); };
    await assert.rejects(initializeLineSession(), /failure/u);
    assert.equal(timers.size, 0);
  } finally { globalThis.setTimeout = originalSet; globalThis.clearTimeout = originalClear; }
});

test('absent SDK and absent token fail explicitly without trusting a cached profile', async () => {
  globalThis.window = {};
  await assert.rejects(loginWithLine(), /LINE_SDK_UNAVAILABLE/u);
  const { sdk } = fixture({ loggedIn: true }); sdk.getAccessToken = () => null;
  await assert.rejects(initializeLineSession(), /LINE_SESSION_INVALID/u);
});

test('displayed account is LINE-only; an old Google account cannot become the active identity', () => {
  const { profile } = fixture();
  const google = { uid: 'different-google-user', displayName: 'Google' };
  assert.equal(getDisplayUser(profile, google).uid, profile.userId);
  assert.equal(getDisplayUser(profile, google).provider, 'line');
  assert.equal(getDisplayUser(null, google), null);
  assert.equal(getDisplayUser(null, null), null);
});

test('external logout invokes SDK; LINE-client logout is not misleadingly offered', () => {
  let sample = fixture({ loggedIn: true });
  logoutFromLine(); assert.equal(sample.calls.logout, 1);
  sample = fixture({ loggedIn: true, inClient: true });
  assert.throws(logoutFromLine, /LINE_CLIENT_LOGOUT_UNSUPPORTED/u);
  assert.equal(sample.calls.logout, 0);
});

test('auth errors are Thai and never display raw provider bodies or callback URLs', () => {
  assert.match(getLineAuthError(new Error('LINE_SESSION_TIMEOUT')), /ใช้เวลานาน/u);
  assert.doesNotMatch(getLineAuthError(new Error('access_token=secret')), /secret/u);
});

test('official SDK, LINE entry points, identity remount and delayed analytics are wired', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  assert.match(read('../index.html'), /https:\/\/static\.line-scdn\.net\/liff\/edge\/2\/sdk\.js/u);
  assert.doesNotMatch(read('../index.html'), /iamprompt/u);
  const app = read('../src/App.jsx');
  assert.doesNotMatch(app, /window\.liff\.init/u);
  assert.match(app, /<History key=\{user\?\.uid/u);
  assert.match(app, /<Social key=\{user\?\.uid/u);
  assert.match(read('../src/shared/layout/Sidebar.jsx'), /<LineLoginButton/u);
  assert.doesNotMatch(read('../src/shared/layout/TopBanner.jsx'), /LineLoginButton|onShare/u);
  assert.match(read('../src/features/auth/firebase.js'), /export let analytics = null/u);
  assert.doesNotMatch(read('../src/features/auth/AuthContext.jsx'), /signInWithGoogle|firebase\/auth/u);
  assert.match(read('../src/features/auth/AuthContext.jsx'), /historyCache\.invalidate\(\)/u);
  assert.doesNotMatch(read('../src/features/auth/session.js'), /firebase/u);
  assert.doesNotMatch(read('../src/features/auth/liff.js'), /import\('\.\/firebase/u);
});
