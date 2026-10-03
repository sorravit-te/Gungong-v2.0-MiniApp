import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

globalThis.window = { location: { protocol: 'https:', hostname: 'example.test', origin: 'https://example.test' },
    liff: { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' } };
const share = await import('../src/features/history/historyShare.js');
const token = 'A'.repeat(43);
const record = (verdict = 'INCOMPLETE') => ({ token, snapshot: { type: 'link', verdict,
    content: '[โดเมน: sample.test]', scanned_at: '2026-01-01T00:00:00Z' },
    expires_at: new Date(Date.now() + 86400000).toISOString() });
const source = file => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');

test('random tokens are 256-bit bearer links with no private History ID', () => {
    const tokens = new Set(Array.from({ length: 100 }, () => share.newShareToken()));
    assert.equal(tokens.size, 100);
    for (const value of tokens) assert.match(value, /^[A-Za-z0-9_-]{43}$/u);
    const link = new URL(share.shareLink(token));
    assert.equal(link.origin, 'https://miniapp.line.me');
    assert.equal(link.pathname, '/2008548759-KkM4Noxa');
    assert.equal(link.search, '');
    assert.equal(link.hash, `#share=${token}`);
    assert.throws(() => share.shareLink('../../secret'));
});

test('direct and LIFF-restored fragments route to the shared page; unrelated links do not', () => {
    assert.equal(share.getSharedToken('', `#share=${token}`), token);
    assert.equal(share.getSharedToken(`?liff.state=${encodeURIComponent(`/#share=${token}`)}`), token);
    for (const value of ['', '#share=short', '#access_token=secret', '#share=../../private']) {
        assert.equal(share.getSharedToken('?historyId=private', value), null);
    }
});

test('create is one authenticated request with explicit consent and no forged snapshot', async () => {
    const calls = [];
    globalThis.fetch = async (url, options) => { calls.push({ url, ...options }); return { ok: true, json: async () => record() }; };
    assert.equal((await share.createHistoryShare('scan', token, false)).token, token);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'https://example.test/api/history-shares');
    assert.equal(calls[0].headers.Authorization, 'Bearer test-only-token');
    assert.deepEqual(JSON.parse(calls[0].body), { entry_id: 'scan', token, include_content: false, consent: true });
    assert.equal(calls[0].cache, 'no-store');
    assert.equal(calls[0].referrerPolicy, 'no-referrer');
});

test('recipient reads do not wait for LINE/session or send auth headers', async () => {
    const previous = window.liff;
    window.liff = { isLoggedIn: () => false, ready: new Promise(() => {}) };
    const calls = [];
    globalThis.fetch = async (url, options) => { calls.push({ url, ...options }); return { ok: true, json: async () => record() }; };
    try {
        await share.readHistoryShare(token);
        assert.deepEqual(calls[0].headers, {});
        assert.equal(calls.length, 1);
    } finally { window.liff = previous; }
});

test('abort prevents a request and malformed/expired replies never render as success', async () => {
    let calls = 0;
    globalThis.fetch = async () => { calls++; return { ok: true, json: async () => record() }; };
    const controller = new AbortController(); controller.abort();
    await assert.rejects(share.readHistoryShare(token, controller.signal));
    assert.equal(calls, 0);
    for (const data of [{}, { ...record(), expires_at: '2020-01-01' }, record('new-status'),
        { ...record(), snapshot: { ...record().snapshot, content: 'x'.repeat(242) } }]) {
        assert.throws(() => share.validateShare(data));
    }
    assert.doesNotThrow(() => share.validateShare({ ...record(), snapshot: { ...record().snapshot, content: '😀'.repeat(240) } }));
});

test('rate-limit and unknown error bodies are mapped without revealing provider data', async () => {
    for (const [status, expected] of [[404, 'SHARE_EXPIRED'], [429, 'SHARE_RATE_LIMIT'], [500, 'SHARE_UNAVAILABLE']]) {
        globalThis.fetch = async () => ({ ok: false, status, json: async () => ({ detail: 'private secret' }) });
        await assert.rejects(share.readHistoryShare(token), new RegExp(expected, 'u'));
    }
    assert.doesNotMatch(share.historyShareError(new Error('private secret')), /private|secret/u);
});

test('Flex follows the standard MINI App bubble and detail/footer permanent links', () => {
    const message = share.buildHistoryShareMessage(record());
    assert.equal(message.type, 'flex'); assert.equal(message.contents.type, 'bubble');
    assert.match(message.altText, /ตรวจสอบได้ไม่ครบ/u);
    const serialized = JSON.stringify(message);
    assert.match(serialized, /ดูรายละเอียดผลตรวจสอบ/u);
    assert.match(serialized, /footer_go_btn\.png/u);
    assert.match(serialized, /#share=/u);
    assert.doesNotMatch(serialized, /historyId|user_id|password|flaticon|carousel/u);
    for (const [verdict, wording] of [['NO_THREAT_FOUND', 'ไม่พบสัญญาณอันตราย'], ['SUSPICIOUS', 'มีความเสี่ยง'],
        ['MALICIOUS', 'มีความเสี่ยง'], ['INVALID', 'ไม่ถูกต้อง']]) {
        assert.match(share.buildHistoryShareMessage(record(verdict)).altText, new RegExp(wording, 'u'));
    }
});

test('picker opens synchronously in click with zero network/preparation awaits, and cancellation is not success', async () => {
    let opened = 0;
    const sdk = { isLoggedIn: () => true, isApiAvailable: name => name === 'shareTargetPicker',
        shareTargetPicker: messages => { opened++; assert.equal(messages.length, 1); return Promise.resolve(undefined); } };
    const promise = share.sendHistoryShare(record(), sdk);
    assert.equal(opened, 1);
    assert.equal(await promise, 'cancelled');
    sdk.shareTargetPicker = () => Promise.resolve({ status: 'success' });
    assert.equal(await share.sendHistoryShare(record(), sdk), 'shared');
    sdk.shareTargetPicker = () => Promise.reject(new Error('failed'));
    await assert.rejects(share.sendHistoryShare(record(), sdk), /failed/u);
    assert.throws(() => share.sendHistoryShare(record(), { isLoggedIn: () => false }), /SHARE_NOT_SUPPORTED/u);
});

test('revoke is authenticated and only confirms a verified server response', async () => {
    globalThis.fetch = async (url, options) => {
        assert.equal(url, `https://example.test/api/history-shares/${token}/revoke`);
        assert.equal(options.method, 'POST'); assert.equal(options.headers['X-Auth-Provider'], 'line');
        return { ok: true, json: async () => ({ revoked: true }) };
    };
    await share.revokeHistoryShare(token);
});

test('UI isolates private History, gates consent, uses native modal and literal rendering', () => {
    const history = source('features/history/history.jsx');
    assert.match(history, /event\.stopPropagation\(\)/u);
    assert.match(history, /handleShare\(event, item\)/u);
    const dialog = source('features/history/HistoryShareDialog.jsx');
    assert.match(dialog, /if \(!consent\) return/u);
    assert.match(dialog, /attempt\.token \|\|= newShareToken/u);
    assert.match(dialog, /element\.showModal\(\)/u);
    assert.match(dialog, /controller\.current\?\.abort\(\)/u);
    assert.match(dialog, /if \(busy\.current\) return/u);
    const entry = source('AppEntry.jsx');
    assert.match(entry, /import App from '\.\/App\.jsx'/u);
    assert.doesNotMatch(entry, /const App = lazy/u);
    assert.match(entry, /if \(!token\) return <App \/>;/u);
    assert.ok(entry.indexOf('if (!token) return <App />;') < entry.indexOf('return <Suspense'));
    assert.match(entry, /const SharedHistoryPage = lazy/u);
    assert.match(entry, /<SharedHistoryPage token=\{token\} \/>/u);
    assert.match(dialog, /import SharedScanDetails from '\.\/SharedScanDetails'/u);
    assert.doesNotMatch(dialog, /from '\.\/SharedHistoryPage'/u);
    assert.doesNotMatch(source('features/history/shareToken.js'), /import/u);
    const page = source('features/history/SharedHistoryPage.jsx');
    assert.doesNotMatch(page, /dangerouslySetInnerHTML|getHistoryById|initializeAnalytics|getProfile|AuthProvider/u);
    assert.match(page, /controller\.abort\(\)/u);
    assert.match(page, /meta\.content = 'noindex, nofollow'/u);
    assert.match(source('features/history/historyShare.css'), /prefers-reduced-motion/u);
});
