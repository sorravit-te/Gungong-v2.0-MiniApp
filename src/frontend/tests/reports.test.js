import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync } from 'node:fs';
import { PRIMARY_NAV_ITEMS } from '../src/shared/navigation/appNavigation.js';
import { APP_SECTIONS, getLineLoginRedirect } from '../src/features/auth/lineAuth.js';
import { getReportDetail, getReportEntryId, sendReportReceiptNotification,
    validateReport, submitContentReport, reportError } from '../src/features/report/reports.js';
import { getLineLoginRedirect as redirect } from '../src/features/auth/lineAuth.js';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const draft = { kind: 'link', content: 'https://example.com/suspicious', reason: 'phishing', details: '' };
const requestId = 'ad4b32bb-2fd1-4c3c-92d2-6a8b822bb15a';

test('Report type choices reuse Scanner stacked cards, mascots and native keyboard selection', () => {
    const source = read('../src/features/report/report.jsx');
    const css = read('../src/features/report/report.css');
    assert.match(source, /className="report-types scanner-feature-list"/u);
    assert.match(source, /scanner-feature-card report-type-card/u);
    for (const mascot of ['mascot_02.png', 'mascot_03.png']) assert.ok(source.includes(mascot));
    for (const className of ['scanner-feature-mascot', 'scanner-feature-copy',
        'scanner-feature-title', 'scanner-feature-description', 'scanner-feature-arrow']) {
        assert.ok(source.includes(className));
    }
    assert.match(source, /type="radio" name="report-kind" value=\{type.kind\} aria-label=\{type.title\}/u);
    assert.match(source, /checked=\{draft.kind === type.kind\} onChange=\{\(\) => change\('kind', type.kind\)\}/u);
    assert.match(css, /\.report-type-card:has\(input:focus-visible\)/u);
    assert.match(css, /\.report-form fieldset > label span/u);
    assert.doesNotMatch(css, /\.report-types[^}]*grid-template-columns/u);
    assert.doesNotMatch(css, /\.report-form label span/u);
});

test('Report type heading matches Scanner content heading typography in both themes', () => {
    const css = read('../src/features/report/report.css');
    const scannerCss = read('../src/features/scanner/scanner.css');
    const heading = scannerCss.match(/\.scanner-menu-heading h3 \{([^}]+)\}/u)[1];
    const legend = css.match(/\.report-form legend \{([^}]+)\}/u)[1];
    for (const property of ['color', 'font-size', 'font-weight']) {
        const declaration = new RegExp(property + ':\\s*([^;]+);', 'u');
        assert.equal(legend.match(declaration)[1], heading.match(declaration)[1]);
    }
    assert.match(css, /\.dark-mode \.report-form legend \{ color: #e2e8f0;/u);
});

test('Report heading uses mascot 04 on the same pale-green circle as Scanner', () => {
    const source = read('../src/features/report/report.jsx');
    const css = read('../src/features/report/report.css');
    const scannerCss = read('../src/features/scanner/scanner.css');
    assert.match(source, /src="\/img\/mascot_04.png" alt="" width="80" height="80"/u);
    assert.doesNotMatch(source, /NavigationIcon/u);
    assert.ok(existsSync(new URL('../public/img/mascot_04.png', import.meta.url)));
    assert.match(css, /\.report-icon \{[^}]*border-radius: 50%; background: #edfbe9;/u);
    assert.match(css, /\.report-icon \{[^}]*width: 80px; height: 80px;/u);
    assert.match(scannerCss, /\.scanner-feature-mascot \{[^}]*border-radius: 50%;\s*background: #edfbe9;/u);
    assert.match(css, /\.report-icon img \{[^}]*object-fit: contain;/u);
});

test('both navigations use Home, Community, Scanner, History, Report in that order', () => {
    assert.deepEqual(PRIMARY_NAV_ITEMS.map(item => item.label), ['Home', 'Community', 'Scanner', 'History', 'Report']);
    assert.equal(PRIMARY_NAV_ITEMS[2].isMain, true);
    for (const component of ['Sidebar', 'BottomNav']) {
        assert.match(read(`../src/shared/layout/${component}.jsx`), /PRIMARY_NAV_ITEMS/u);
    }
});

test('Verify is dormant, including direct links, but its source is preserved', () => {
    for (const route of ['verify', 'verify-phone', 'verify-bank', 'verify-id-card', 'id-card-scanner']) {
        assert.equal(APP_SECTIONS.has(route), false);
    }
    assert.ok(APP_SECTIONS.has('report'));
    assert.match(getLineLoginRedirect('report'), /\?section=report$/u);
    const app = read('../src/App.jsx');
    assert.doesNotMatch(app, /import Verify|import IDCardScanner|case 'verify'/u);
    assert.match(app, /case 'report'/u);
    assert.ok(existsSync(new URL('../src/legacy/verify/verify.jsx', import.meta.url)));
    assert.ok(existsSync(new URL('../src/legacy/verify/IDCardScanner.jsx', import.meta.url)));
});

test('link and text drafts reject invalid data without fetching reported URLs', () => {
    assert.equal(validateReport(draft), '');
    assert.equal(validateReport({ ...draft, kind: 'text', content: '<script>literal</script>' }), '');
    for (const content of ['', 'example.com', 'javascript:alert(1)', 'https://a:b@example.com',
        'https://example.com:bad', 'https://example.com/has space', 'https://example.com/' + 'a'.repeat(2048)]) {
        assert.ok(validateReport({ ...draft, content }));
    }
    assert.ok(validateReport({ ...draft, reason: 'approved' }));
    assert.ok(validateReport({ ...draft, details: 'a'.repeat(1001) }));
    assert.ok(validateReport({ ...draft, kind: 'text', content: 'a'.repeat(5001) }));
});

function authenticated() {
    globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' },
        liff: { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' } };
}

test('submission uses verified headers and one retry ID, never caller identity', async () => {
    authenticated();
    const original = globalThis.fetch;
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        return new Response(JSON.stringify({ id: 'a'.repeat(64), status: 'pending' }));
    };
    try {
        for (let i = 0; i < 2; i++) await submitContentReport(draft, requestId);
        assert.equal(calls[0].url, 'https://app.test/api/reports');
        assert.equal(calls[0].options.headers.Authorization, 'Bearer test-only-token');
        assert.equal(calls[0].options.headers['X-Auth-Provider'], 'line');
        assert.equal(calls[0].options.cache, 'no-store');
        assert.deepEqual(JSON.parse(calls[0].options.body), { ...draft, request_id: requestId });
        assert.equal(calls[0].options.body, calls[1].options.body);
    } finally { globalThis.fetch = original; }
});

test('anonymous submissions never make an API request', async () => {
    globalThis.window = { liff: { isLoggedIn: () => false } };
    const original = globalThis.fetch;
    globalThis.fetch = () => { throw new Error('Must not fetch'); };
    try { await assert.rejects(submitContentReport(draft, requestId), /LOGIN_REQUIRED/u); }
    finally { globalThis.fetch = original; }
});

test('failed or malformed receipts are not reported as success', async () => {
    authenticated();
    const original = globalThis.fetch;
    try {
        for (const status of [401, 409, 422, 429, 503]) {
            globalThis.fetch = async () => new Response('{}', { status });
            await assert.rejects(submitContentReport(draft, requestId));
        }
        for (const receipt of [{}, { id: 'fake', status: 'pending' }, { id: 'a'.repeat(64), status: 'approved' }]) {
            globalThis.fetch = async () => new Response(JSON.stringify(receipt));
            await assert.rejects(submitContentReport(draft, requestId), /REPORT_UNCONFIRMED/u);
        }
        const controller = new AbortController();
        controller.abort();
        globalThis.fetch = () => { throw new Error('Must not fetch'); };
        await assert.rejects(submitContentReport(draft, requestId, controller.signal), /REPORT_UNCONFIRMED/u);
        assert.match(reportError(new Error('REPORT_UNCONFIRMED')), /หมายเลขเดิม/u);
    } finally { globalThis.fetch = original; }
});

test('form prevents duplicate clicks, retains retry ID, and aborts on unmount', () => {
    const source = read('../src/features/report/report.jsx');
    assert.match(source, /if \(inFlight.current \|\| receipt \|\| isQrReading\) return/u);
    assert.match(source, /attempt.current \|\|= crypto.randomUUID\(\)/u);
    assert.match(source, /controller.current\?\.abort\(\)/u);
    assert.match(source, /role="alert"/u);
    assert.match(source, /role="status"/u);
    assert.match(source, /disabled=\{!user \|\| loading \|\| saving \|\| isQrReading\}/u);
    assert.match(source, /section-content report-content/u);
});

test('report deep links validate IDs and preserve only approved parameters during login', () => {
    const id = 'a'.repeat(64);
    assert.equal(getReportEntryId(`?section=report&reportId=${id}`), id);
    for (const value of ['../secret', 'https://evil.test', '<script>', 'A'.repeat(64), '']) {
        assert.equal(getReportEntryId(`?reportId=${encodeURIComponent(value)}`), null);
    }
    const url = new URL(redirect('report', `?reportId=${id}&access_token=secret&redirect=https://evil.test`));
    assert.deepEqual([...url.searchParams], [['section', 'report'], ['reportId', id]]);
    assert.equal(new URL(redirect('home', `?reportId=${id}`)).searchParams.has('reportId'), false);
});

test('immediate receipt notification is opt-in and separate from the confirmed receipt', async () => {
    authenticated();
    const original = globalThis.fetch;
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        return new Response(JSON.stringify({ notification: 'sent' }));
    };
    try {
        const id = 'a'.repeat(64);
        assert.equal(await sendReportReceiptNotification(id), 'disabled');
        assert.equal(calls.length, 0);
        assert.equal(await sendReportReceiptNotification(id, undefined, true), 'sent');
        assert.equal(calls[0].url, `https://app.test/api/reports/${id}/notification`);
        assert.equal(calls[0].options.method, 'POST');
        assert.equal(calls[0].options.headers.Authorization, 'Bearer test-only-token');
        assert.equal(calls[0].options.body, undefined);
        globalThis.fetch = async () => new Response('{}', { status: 503 });
        assert.equal(await sendReportReceiptNotification(id, undefined, true), 'unavailable');
        globalThis.fetch = async () => new Response(JSON.stringify({ notification: 'ready' }));
        assert.equal(await sendReportReceiptNotification(id, undefined, true), 'unavailable');
        globalThis.window.liff.isLoggedIn = () => false;
        globalThis.fetch = () => { throw new Error('No anonymous request'); };
        assert.equal(await sendReportReceiptNotification(id, undefined, true), 'unavailable');
    } finally { globalThis.fetch = original; }
});

test('report detail reads authenticated real data, rejects malformed and unavailable results', async () => {
    authenticated();
    const original = globalThis.fetch;
    const id = 'a'.repeat(64);
    const data = { id, kind: 'text', content: '<script>literal</script>', status: 'reviewed',
        review_result: 'risk', review_note: 'Reviewed explanation' };
    globalThis.fetch = async (url, options) => {
        assert.equal(url, `https://app.test/api/reports/${id}`);
        assert.equal(options.method, 'GET');
        assert.equal(options.cache, 'no-store');
        assert.equal(options.headers.Authorization, 'Bearer test-only-token');
        return new Response(JSON.stringify(data));
    };
    try {
        assert.deepEqual(await getReportDetail(id), data);
        for (const payload of [{}, { ...data, id: 'b'.repeat(64) }, { ...data, status: 'sent' },
            { ...data, review_result: 'unknown' }, { ...data, review_note: null }]) {
            globalThis.fetch = async () => new Response(JSON.stringify(payload));
            await assert.rejects(getReportDetail(id), /REPORT_UNCONFIRMED/u);
        }
        for (const status of [401, 404, 503]) {
            globalThis.fetch = async () => new Response('{}', { status });
            await assert.rejects(getReportDetail(id));
        }
        const controller = new AbortController();
        controller.abort();
        globalThis.fetch = () => { throw new Error('No aborted request'); };
        await assert.rejects(getReportDetail(id, controller.signal), /REPORT_UNCONFIRMED/u);
    } finally { globalThis.fetch = original; }
});

test('review detail is safely rendered and late reads do not cross accounts or navigation', () => {
    const source = read('../src/features/report/report.jsx');
    assert.match(source, /active = false; request.abort\(\)/u);
    assert.match(source, /detailState\?\.owner === user\?\.uid/u);
    assert.match(source, /visibleDetail.data.review_note/u);
    assert.match(source, /visibleDetail.data.content/u);
    assert.doesNotMatch(source, /dangerouslySetInnerHTML|localStorage/u);
    assert.ok(source.indexOf('setReceipt(result)') < source.indexOf('await sendReportReceiptNotification'));
    assert.ok(source.includes('ส่งข้อความขอบคุณผ่าน LINE MINI App Notice แล้ว'));
    assert.ok(source.includes('ยังยืนยันการส่งข้อความผ่าน LINE ไม่ได้'));
    assert.doesNotMatch(source, /เมื่อตรวจสอบเสร็จแล้ว|เตรียมการแจ้งผล/u);
    assert.match(source, /button type="button" disabled=\{saving\}/u);
});
