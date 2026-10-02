import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { selectHistoryItems, summarizeHistory, parseHistoryDate } from '../src/utils/historyView.js';

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
    assert.equal(summary.types.find(type => type.value === 'link').count, 3);
    assert.equal(summary.types.find(type => type.value === 'text').count, 2);
    assert.equal(summary.types.find(type => type.value === 'other').count, 1);
    assert.equal(summary.types.reduce((total, type) => total + type.count, 0), summary.total);
    assert.equal(summarizeHistory([]).total, 0);
    assert.equal(summarizeHistory([{ type: 'phone', hit_count: 500, is_safe: true }]).total, 1);
});

test('Home uses private cached history, real summary and three-slot wraparound banner', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    const home = read('../src/components/home.jsx');
    const summary = read('../src/components/DataVisualization.jsx');
    const history = read('../src/components/history.jsx');
    const loader = read('../src/hooks/useHistoryEntries.js');
    assert.doesNotMatch(home, /className="status-bar/u);
    assert.match(home, /loop=\{true\}/u);
    assert.match(home, /slidesPerView=\{3\}/u);
    assert.match(home, /const loopSlides = \[\.\.\.slides, \.\.\.slides, \.\.\.slides\]/u);
    assert.match(home, /centeredSlides=\{true\}/u);
    assert.match(summary, /summarizeHistory\(entries\)/u);
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
    const css = read('../src/styles/home.css');
    assert.match(css, /#home-page \.section-content \{ max-width: none;/u);
    assert.match(css, /overflow: visible !important/u);
    assert.match(css, /:not\(\.swiper-slide-active\):not\(\.swiper-slide-prev\):not\(\.swiper-slide-next\)/u);
});
