import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { HISTORY_TYPES, SUMMARY_OUTCOMES, selectHistoryItems, summarizeHistory, summarizeScannerHistory, parseHistoryDate } from '../src/features/history/utils/historyView.js';

test('History and Summary status messages match the empty Community message color', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    const color = read('../src/features/auth/auth.css').match(/\.page-loading \{[^}]*color: (#[a-f0-9]+);/u)[1];
    const history = read('../src/features/history/history.css');
    const summary = read('../src/features/home/dataVisualization.css');
    assert.ok(history.includes(`.history-load-message { color: ${color}; }`));
    assert.ok(summary.includes(`.summary-load-message { text-align: center; color: ${color};`));
    assert.doesNotMatch(history, /html\.dark-mode \.history-load-message/u);
    assert.doesNotMatch(summary, /html\.dark-mode \.summary-load-message/u);
});

const records = [
    { id: 'new', type: 'link', created_at: '2026-10-02T10:00:00Z', message_text: 'first...', full_message: 'Full EXAMPLE url', is_safe: true },
    { id: 'old', type: 'qr', created_at: '2026-10-01T10:00:00Z', message_text: 'example qr', is_fraud: true },
    { id: 'uncertain', type: 'link', created_at: '2026-10-02T09:00:00Z', message_text: 'example uncertain', is_safe: true,
        url_check_result: { verification_verdict: 'INCOMPLETE' } },
    { id: 'invalid', type: 'link', created_at: 'not-a-date', is_fraud: true, url_check_result: { verification_verdict: 'INVALID' } },
    { id: 'text', type: 'message', created_at: null, is_safe: true },
    { id: 'sms', type: 'sms', created_at: null },
    { id: 'other', type: 'unrecognized', created_at: null },
];

test('filters compose search, multiple types, outcome and calendar day using full text', () => {
    assert.deepEqual(selectHistoryItems(records, { search: ' full example ', types: ['link'], outcome: 'safe' }).map(item => item.id), ['new']);
    assert.deepEqual(selectHistoryItems(records, { types: ['link', 'qr'], outcome: 'risk' }).map(item => item.id), ['old']);
    assert.deepEqual(selectHistoryItems(records, { outcome: 'unknown', types: ['link'] }).map(item => item.id), ['uncertain']);
    assert.deepEqual(selectHistoryItems(records, { outcome: 'invalid' }).map(item => item.id), ['invalid']);
    assert.deepEqual(selectHistoryItems(records, { date: new Date('2026-10-02T09:00:00Z') }).map(item => item.id), ['new', 'uncertain']);
    assert.deepEqual(selectHistoryItems(records, { types: ['text'] }).map(item => item.id), ['text', 'sms']);
    assert.deepEqual(selectHistoryItems(records, { search: 'not present' }), []);
});

test('Summary is wider and History controls float without moving the list', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    assert.match(read('../src/features/home/home.css'), /#home-page \.summary-viz-card \{ width: 100%; max-width: 800px;/u);
    const history = read('../src/features/history/history.jsx');
    const css = read('../src/features/history/history.css');
    assert.match(history, /className="history-toolbar" ref=\{toolbar\}/u);
    assert.match(css, /\.history-options-panel \{\s*position: absolute;/u);
    assert.match(css, /width: min\(360px, 100%\)/u);
    assert.match(history, /role="dialog" aria-label="กรองประวัติ"/u);
    assert.match(history, /event\.key !== 'Escape'/u);
    assert.match(history, /!toolbar\.current\?\.contains\(event\.target\)/u);
    assert.match(history, /removeEventListener\('pointerdown', outside\)/u);
    assert.match(history, /removeEventListener\('keydown', escape\)/u);
});

test('newest and oldest sort before slicing and keep invalid dates last without mutating cache', () => {
    const before = records.map(item => item.id);
    assert.deepEqual(selectHistoryItems(records).slice(0, 3).map(item => item.id), ['new', 'uncertain', 'old']);
    assert.deepEqual(selectHistoryItems(records, { sort: 'oldest' }).slice(0, 3).map(item => item.id), ['old', 'uncertain', 'new']);
    assert.deepEqual(records.map(item => item.id), before);
    assert.equal(parseHistoryDate('invalid'), null);
    assert.equal(parseHistoryDate(null), null);
});

test('summary counts actual entries and types, not hits; incomplete and invalid cannot become safe/risk', () => {
    const summary = summarizeHistory(records);
    assert.equal(summary.total, 7);
    assert.deepEqual(summary.counts, { safe: 2, risk: 1, unknown: 3, invalid: 1 });
    assert.equal(summary.types.find(type => type.value === 'link').count, 4);
    assert.equal(summary.types.find(type => type.value === 'text').count, 2);
    assert.equal(summary.types.find(type => type.value === 'other').count, 1);
    assert.equal(summary.types.reduce((total, type) => total + type.count, 0), summary.total);
    assert.equal(summarizeHistory([]).total, 0);
    assert.equal(summarizeHistory([{ type: 'phone', hit_count: 500, is_safe: true }]).total, 1);
});

test('Summary and History filters combine links and QR codes without changing records or totals', () => {
    const entries = [{ type: 'qr', is_safe: true }, { type: 'link', is_fraud: true }];
    const summary = summarizeHistory(entries);
    assert.deepEqual(summary.types.map(type => type.value), ['link', 'text', 'bank', 'phone']);
    assert.equal(summary.types[0].label, 'ลิงก์ / QR Code');
    assert.equal(summary.types[0].count, 2);
    assert.equal(summary.total, 2);
    assert.deepEqual(summary.counts, { safe: 1, risk: 1, unknown: 0, invalid: 0 });
    assert.equal(HISTORY_TYPES[0].label, 'ลิงก์ / QR Code');
    assert.ok(!HISTORY_TYPES.some(type => type.value === 'qr'));
    assert.deepEqual(selectHistoryItems(entries, { types: ['link'] }).map(item => item.type), ['qr', 'link']);
    assert.deepEqual(entries.map(item => item.type), ['qr', 'link']);
    assert.equal(summarizeHistory([]).types[0].count, 0);
});

test('Scanner Summary only counts active link/QR and text scans, preserving old History records', () => {
    const entries = [
        { type: 'link' }, { type: 'qr' }, { type: 'text' }, { type: 'message' }, { type: 'sms' },
        { type: 'bank' }, { type: 'phone' }, { type: 'unknown' },
    ];
    const before = structuredClone(entries);
    const summary = summarizeScannerHistory(entries);
    assert.deepEqual(summary.types.map(type => [type.value, type.count]), [['link', 2], ['text', 3]]);
    assert.equal(summary.total, 5);
    assert.deepEqual(entries, before);
    assert.equal(summarizeHistory(entries).total, 8);
    for (const empty of [[], [{ type: 'bank' }, { type: 'phone' }]]) {
        assert.deepEqual(summarizeScannerHistory(empty).types.map(type => type.count), [0, 0]);
        assert.equal(summarizeScannerHistory(empty).total, 0);
    }
});

test('Summary always renders its graph without sample counts and retains mobile label styling', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    const summary = read('../src/features/home/components/DataVisualization.jsx');
    const css = read('../src/features/home/dataVisualization.css');
    assert.doesNotMatch(summary, /summary-total|summary-outcomes|stat-value|ตรวจแล้ว/u);
    assert.doesNotMatch(summary, /summary-stats-inline/u);
    assert.ok(summary.indexOf('className="chart-container"') < summary.indexOf('{loading ?'));
    assert.match(summary, /CartesianGrid vertical=\{false\}/u);
    assert.match(summary, /value: type\.count/u);
    assert.match(summary, /stackId="results"/u);
    assert.match(summary, /summary\.counts\[outcome\.key\]/u);
    assert.match(summary, /showCounts=\{summary\.total > 0 \|\| \(!loading && !error\)\}/u);
    assert.match(summary, /className="chart-axis-tick chart-category-axis"/u);
    assert.match(summary, /ยังไม่มีประวัติการตรวจสอบ/u);
    assert.match(css, /@media \(max-width: 767px\) \{\s*\.summary-viz-card \.chart-category-axis \.recharts-cartesian-axis-tick-value \{\s*font-size: 12px;\s*font-weight: 400;\s*fill: #6d6d6d;/u);
    assert.match(css, /html\.dark-mode \.summary-viz-card \.chart-category-axis \.recharts-cartesian-axis-tick-value \{\s*fill: #E2E8F0 !important;/u);
});

test('stacked Summary outcomes reconcile with feature and global totals without mutating history', () => {
    const entries = [...records, { type: 'bank', is_fraud: true }, { type: 'phone', is_safe: true }];
    const before = structuredClone(entries);
    const summary = summarizeScannerHistory(entries);
    assert.deepEqual(summary.counts, { safe: 2, risk: 1, unknown: 2, invalid: 1 });
    assert.deepEqual(summary.types[0].outcomes, { safe: 1, risk: 1, unknown: 1, invalid: 1 });
    assert.deepEqual(summary.types[1].outcomes, { safe: 1, risk: 0, unknown: 1, invalid: 0 });
    for (const type of summary.types) {
        assert.equal(Object.values(type.outcomes).reduce((sum, count) => sum + count, 0), type.count);
    }
    for (const { key } of SUMMARY_OUTCOMES) {
        assert.equal(summary.types.reduce((sum, type) => sum + type.outcomes[key], 0), summary.counts[key]);
    }
    assert.equal(summary.types.reduce((sum, type) => sum + type.count, 0), summary.total);
    assert.deepEqual(entries, before);
    assert.deepEqual(summarizeScannerHistory([]).types.map(type => type.outcomes), [
        { safe: 0, risk: 0, unknown: 0, invalid: 0 }, { safe: 0, risk: 0, unknown: 0, invalid: 0 },
    ]);
});

test('mobile History calendar, list and search use a shared full-width column', () => {
    const css = readFileSync(new URL('../src/features/history/history.css', import.meta.url), 'utf8');
    assert.match(css, /flex-direction: column;\s*align-items: stretch;/u);
    assert.match(css, /#history-page \.history-calendar,\s*\.history-main-content \{\s*width: 100%;\s*margin-inline: auto;/u);
    assert.match(css, /\.history-controls \.search-box \{ flex: 1; min-width: 0;/u);
});

test('Home uses private cached history, real summary and three-slot wraparound banner', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    const home = read('../src/features/home/home.jsx');
    const summary = read('../src/features/home/components/DataVisualization.jsx');
    const history = read('../src/features/history/history.jsx');
    const loader = read('../src/features/history/hooks/useHistoryEntries.js');
    assert.doesNotMatch(home, /className="status-bar/u);
    assert.match(home, /loop=\{true\}/u);
    assert.match(home, /slidesPerView=\{1\.2\}/u);
    assert.match(home, /breakpoints=\{\{ 768: \{ slidesPerView: 3, spaceBetween: 0 \} \}\}/u);
    assert.match(home, /const loopSlides = \[\.\.\.slides, \.\.\.slides, \.\.\.slides\]/u);
    assert.match(home, /centeredSlides=\{true\}/u);
    assert.match(summary, /summarizeScannerHistory\(entries\)/u);
    assert.match(summary, /useHistoryEntries\(\)/u);
    assert.match(summary, /onNavigate\?\.\('history'\)/u);
    assert.doesNotMatch(summary, /value: (43|36|12)|of this week/u);
    assert.match(loader, /historyCache\.read\(userId, loadHistory\)/u);
    assert.match(loader, /if \(!userId\) throw new Error\('LOGIN_REQUIRED'\)/u);
    assert.match(loader, /if \(active\)/u);
    assert.match(read('../src/App.jsx'), /Home key=\{user\?\.uid \|\| 'anonymous'\}/u);
    assert.match(history, /selectHistoryItems\(historyData/u);
    assert.doesNotMatch(history, /ฟังก์ชันกำลังพัฒนา/u);
    assert.match(history, /setSortOrder\(event\.target\.value\)/u);
    const css = read('../src/features/home/home.css');
    assert.match(css, /#home-page \.section-content \{ max-width: none;/u);
    assert.match(css, /overflow: visible !important/u);
    assert.match(css, /:not\(\.swiper-slide-active\):not\(\.swiper-slide-prev\):not\(\.swiper-slide-next\)/u);
});
