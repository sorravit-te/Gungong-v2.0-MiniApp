import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { initializeLineSession, getMobileLineTarget, LINE_ENDPOINT_URL } from '../src/utils/lineAuth.js';

const origin = new URL(LINE_ENDPOINT_URL).origin;
function mobile({ os = 'android', inClient = false, search = '', callback = false, host = origin } = {}) {
  return { sdk: { getOS: () => os, isInClient: () => inClient },
    location: { origin: host, search }, navigator: { userAgent: 'Test' }, callback };
}

test('Android and iOS central links target the Published HTTPS Mini App, not a deprecated scheme', () => {
  for (const os of ['android', 'ios']) {
    assert.equal(getMobileLineTarget(mobile({ os })), 'https://miniapp.line.me/2008548759-KkM4Noxa');
  }
});

test('desktop stays in the website; localhost and generated previews are not automatically redirected', () => {
  assert.equal(getMobileLineTarget(mobile({ os: 'web' })), null);
  for (const host of ['http://localhost:5173', 'https://generated.vercel.app', 'https://evil.test']) {
    assert.equal(getMobileLineTarget(mobile({ host })), null);
  }
});

test('in-client Mini App and OAuth/LIFF callbacks are never bounced back into LINE', () => {
  assert.equal(getMobileLineTarget(mobile({ inClient: true })), null);
  assert.equal(getMobileLineTarget(mobile({ callback: true })), null);
  for (const search of ['?code=secret', '?state=secret', '?liff.state=%2F', '?liff.referrer=secret',
    '?liff.newParameter=secret', '?lineAppVersion=16', '?access_token=secret', '?error=denied']) {
    assert.equal(getMobileLineTarget(mobile({ search })), null);
  }
  const options = mobile(); options.location.hash = '#access_token=secret';
  assert.equal(getMobileLineTarget(options), null);
});

test('mobile handoff forwards only approved navigation, never user-supplied origins or credentials', () => {
  const target = new URL(getMobileLineTarget(mobile({ search: '?section=history&historyId=entry_123&next=https://evil.test&secret=private' })));
  assert.equal(target.origin, 'https://miniapp.line.me');
  assert.deepEqual([...target.searchParams], [['section', 'history'], ['historyId', 'entry_123']]);
  assert.equal(getMobileLineTarget(mobile({ search: '?section=https://evil.test&historyId=../escape' })),
    'https://miniapp.line.me/2008548759-KkM4Noxa');
});

test('iPad desktop-style UA is recognized without treating a desktop Mac as mobile', () => {
  const options = mobile({ os: 'web' });
  options.navigator = { platform: 'MacIntel', maxTouchPoints: 5 };
  assert.ok(getMobileLineTarget(options));
  options.navigator.maxTouchPoints = 0; assert.equal(getMobileLineTarget(options), null);
});

function sessionFixture({ search = '', inClient = false, storageFails = false } = {}) {
  const order = []; const storage = new Map();
  const makeSdk = () => ({ init: async () => { order.push('init'); }, getOS: () => 'android',
    isInClient: () => inClient, isLoggedIn: () => false });
  globalThis.window = { liff: makeSdk(), location: { origin, search, replace: target => order.push(target) },
    sessionStorage: { getItem: key => { if (storageFails) throw new Error('blocked'); return storage.get(key); },
      setItem: (key, value) => storage.set(key, value) } };
  return { order, makeSdk, storage };
}

test('mobile navigation starts WITHOUT SDK init, once across StrictMode and immediate fallback reload', async () => {
  const { order, makeSdk } = sessionFixture();
  await Promise.all([initializeLineSession(), initializeLineSession()]);
  assert.deepEqual(order, ['https://miniapp.line.me/2008548759-KkM4Noxa']);
  globalThis.window = { ...window, liff: makeSdk() }; await initializeLineSession();
  assert.equal(order.filter(value => value.startsWith('https://')).length, 1);
  assert.equal(order.filter(value => value === 'init').length, 1);
});

test('disabled session storage still has a per-page duplicate redirect guard', async () => {
  const { order } = sessionFixture({ storageFails: true });
  await Promise.all([initializeLineSession(), initializeLineSession()]);
  assert.equal(order.filter(value => value.startsWith('https://')).length, 1);
});

test('callback captured before SDK removes it is still protected from redirect', async () => {
  const { order } = sessionFixture({ search: '?code=secret&state=secret' });
  window.liff.init = async () => { window.location.search = ''; };
  await initializeLineSession(); assert.deepEqual(order, []);
});

test('a hung or failed SDK init cannot prevent the mobile central-link handoff', async () => {
  for (const init of [() => new Promise(() => {}), async () => { throw new Error('INIT_FAILED'); }]) {
    const { order } = sessionFixture(); window.liff.init = init;
    assert.equal(await initializeLineSession({ timeoutMs: 5 }), null);
    assert.deepEqual(order, ['https://miniapp.line.me/2008548759-KkM4Noxa']);
  }
});

test('stale permanent guards from the old implementation do not suppress the next mobile visit', async () => {
  const { order, storage } = sessionFixture(); storage.set('gungong_line_handoff', 'attempted');
  await initializeLineSession();
  assert.equal(order.filter(value => value.startsWith('https://')).length, 1);
  assert.ok(Number(storage.get('gungong_line_handoff')) > 0);
});

test('the cooldown prevents immediate loops but expires for a later central-link visit', async t => {
  let now = 100000; t.mock.method(Date, 'now', () => now);
  const { order, makeSdk } = sessionFixture(); await initializeLineSession();
  globalThis.window = { ...window, liff: makeSdk() }; await initializeLineSession();
  assert.equal(order.filter(value => value.startsWith('https://')).length, 1);
  now += 30001;
  globalThis.window = { ...window, liff: makeSdk() }; await initializeLineSession();
  assert.equal(order.filter(value => value.startsWith('https://')).length, 2);
});

test('missing SDK still hands an external mobile browser off without inventing a LINE session', async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { userAgent: 'Mozilla/5.0 Android Chrome' } });
  try {
    const { order } = sessionFixture(); delete window.liff;
    assert.equal(await initializeLineSession(), null);
    assert.deepEqual(order, ['https://miniapp.line.me/2008548759-KkM4Noxa']);
    navigator.userAgent = 'Android Line/16 LIFF';
    assert.equal(getMobileLineTarget({ location: window.location, navigator }), null);
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'navigator', descriptor);
    else delete globalThis.navigator;
  }
});

test('fallback uses a real user-tappable HTTPS link and captures the pre-init callback state', () => {
  const component = readFileSync(new URL('../src/components/shared/MobileLineEntry.jsx', import.meta.url), 'utf8');
  assert.match(component, /useState\(\(\) => getMobileLineTarget/u);
  assert.match(component, /<a href=\{target\}>เปิดใน LINE<\/a>/u);
  assert.doesNotMatch(component, /window\.open|line:\/\/|access_token=/u);
});
