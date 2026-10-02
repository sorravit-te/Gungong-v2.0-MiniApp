import { getHistoryResultPresentation } from './fraudResultPresentation.js';

export const HISTORY_TYPES = [
    { value: 'link', label: 'ลิงก์', color: '#86EFAC' },
    { value: 'qr', label: 'QR Code', color: '#93C5FD' },
    { value: 'text', label: 'ข้อความ', color: '#D8B4FE' },
    { value: 'bank', label: 'บัญชีธนาคาร', color: '#FDBA74' },
    { value: 'phone', label: 'เบอร์โทร', color: '#FCA5A5' },
];

export function parseHistoryDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

export function getHistoryOutcome(item) {
    const result = getHistoryResultPresentation(item);
    if (result.isInvalid) return 'invalid';
    if (result.isRisk) return 'risk';
    if (result.isSafe) return 'safe';
    return 'unknown';
}

export function getHistoryType(item) {
    return ['message', 'sms'].includes(item.type) ? 'text' : item.type;
}

export function selectHistoryItems(entries, { search = '', types = [], outcome = 'all', date = null, sort = 'newest' } = {}) {
    const query = search.trim().toLocaleLowerCase();
    return entries.filter(item => {
        const content = item.full_message || item.message_text || item.account_number || item.phone_number || '';
        if (!String(content).toLocaleLowerCase().includes(query)) return false;
        if (types.length && !types.includes(getHistoryType(item))) return false;
        if (outcome !== 'all' && getHistoryOutcome(item) !== outcome) return false;
        const created = parseHistoryDate(item.created_at);
        return !date || (created && created.getFullYear() === date.getFullYear()
            && created.getMonth() === date.getMonth() && created.getDate() === date.getDate());
    }).sort((left, right) => {
        const a = parseHistoryDate(left.created_at)?.getTime();
        const b = parseHistoryDate(right.created_at)?.getTime();
        // Undated records stay last in both directions. Never mutate the cached list.
        if (a === undefined) return b === undefined ? 0 : 1;
        if (b === undefined) return -1;
        return sort === 'oldest' ? a - b : b - a;
    });
}

export function summarizeHistory(entries) {
    const counts = { safe: 0, risk: 0, unknown: 0, invalid: 0 };
    const types = new Map(HISTORY_TYPES.map(type => [type.value, { ...type, count: 0 }]));
    for (const entry of entries) {
        counts[getHistoryOutcome(entry)] += 1;
        const type = getHistoryType(entry);
        if (!types.has(type)) types.set(type, { value: 'other', label: 'อื่น ๆ', color: '#94A3B8', count: 0 });
        types.get(type).count += 1;
    }
    const known = HISTORY_TYPES.map(type => types.get(type.value));
    const otherCount = [...types.entries()].filter(([key]) => !HISTORY_TYPES.some(type => type.value === key))
        .reduce((total, [, type]) => total + type.count, 0);
    return { total: entries.length, counts, types: otherCount
        ? [...known, { value: 'other', label: 'อื่น ๆ', color: '#94A3B8', count: otherCount }] : known };
}
