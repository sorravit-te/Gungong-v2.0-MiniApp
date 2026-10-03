import { LIFF_ID } from '../auth/liff.js';
import { LINE_ENDPOINT_URL } from '../auth/lineAuth.js';
import { getSessionHeaders } from '../auth/session.js';
import { getApiBaseUrl } from '../../shared/api/script.js';
import { getHistoryResultPresentation } from '../../shared/results/fraudResultPresentation.js';

import { SHARE_TOKEN_PATTERN as TOKEN } from './shareToken.js';
export { getSharedToken } from './shareToken.js';
export const SHARE_TYPES = Object.freeze({ link: 'ลิงก์', qr: 'QR Code', text: 'ข้อความ',
    sms: 'ข้อความ', message: 'ข้อความ', bank: 'บัญชีธนาคาร', phone: 'เบอร์โทรศัพท์', unknown: 'ข้อมูล' });

export function newShareToken() {
    const bytes = new Uint8Array(32);
    globalThis.crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes)).replace(/\+/gu, '-').replace(/\//gu, '_').replace(/=+$/u, '');
}

export function sharePresentation(snapshot) {
    return getHistoryResultPresentation({ type: snapshot.type, verification_verdict: snapshot.verdict });
}

export function validateShare(data) {
    const view = data?.snapshot;
    if (!view || !Object.hasOwn(SHARE_TYPES, view.type) ||
        !['NO_THREAT_FOUND', 'SUSPICIOUS', 'MALICIOUS', 'INCOMPLETE', 'INVALID'].includes(view.verdict) ||
        typeof view.content !== 'string' || Array.from(view.content).length > 241 ||
        (view.scanned_at !== null && !Number.isFinite(Date.parse(view.scanned_at))) ||
        !Number.isFinite(Date.parse(data.expires_at)) || Date.parse(data.expires_at) <= Date.now()) {
        throw new Error('SHARE_UNAVAILABLE');
    }
    return data;
}

async function requestShare(path, { method = 'GET', body, signal, authenticated = false } = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(abort, 12000);
    try {
        const headers = authenticated ? await getSessionHeaders() : {};
        if (signal?.aborted || controller.signal.aborted) throw new Error('SHARE_UNAVAILABLE');
        const response = await fetch(`${getApiBaseUrl()}/api/history-shares${path}`, {
            method, cache: 'no-store', referrerPolicy: 'no-referrer', signal: controller.signal,
            headers: body ? { ...headers, 'Content-Type': 'application/json' } : headers,
            ...(body ? { body: JSON.stringify(body) } : {}),
        });
        if (!response.ok) throw new Error(({ 401: 'LOGIN_REQUIRED', 404: 'SHARE_EXPIRED',
            409: 'SHARE_CONFLICT', 429: 'SHARE_RATE_LIMIT' })[response.status] || 'SHARE_UNAVAILABLE');
        return await response.json();
    } finally {
        clearTimeout(timer);
        signal?.removeEventListener('abort', abort);
    }
}

export async function createHistoryShare(entryId, token, includeContent, signal) {
    if (!/^[A-Za-z0-9_-]{1,128}$/u.test(entryId) || !TOKEN.test(token)) throw new Error('SHARE_UNAVAILABLE');
    const data = await requestShare('', { method: 'POST', authenticated: true, signal,
        body: { entry_id: entryId, token, include_content: includeContent, consent: true } });
    return { ...validateShare(data), token };
}

export async function readHistoryShare(token, signal) {
    if (!TOKEN.test(token)) throw new Error('SHARE_EXPIRED');
    return validateShare(await requestShare(`/${token}`, { signal }));
}

export async function revokeHistoryShare(token, signal) {
    if (!TOKEN.test(token)) throw new Error('SHARE_UNAVAILABLE');
    const result = await requestShare(`/${token}/revoke`, { method: 'POST', authenticated: true, signal });
    if (result?.revoked !== true) throw new Error('SHARE_UNAVAILABLE');
}

export function canShareHistory(sdk = globalThis.window?.liff) {
    return Boolean(sdk?.isLoggedIn?.() && sdk?.isApiAvailable?.('shareTargetPicker'));
}

export function shareLink(token) {
    if (!TOKEN.test(token)) throw new Error('SHARE_UNAVAILABLE');
    // Fragment stays out of page requests/referrers; never embed private History IDs.
    return `https://miniapp.line.me/${LIFF_ID}#share=${token}`;
}

export function buildHistoryShareMessage(prepared) {
    validateShare(prepared);
    const view = prepared.snapshot;
    const status = sharePresentation(view).status;
    const title = text => ({ type: 'box', layout: 'vertical', spacing: 'none', contents: [text] });
    const body = [
        title({ type: 'text', text: 'ผลตรวจสอบ GunGong', size: 'lg', color: '#000000', weight: 'bold', wrap: true }),
        title({ type: 'text', text: status, size: 'sm', color: '#999999', wrap: true }),
        { type: 'box', layout: 'vertical', spacing: 'sm', margin: 'lg', flex: 1,
            contents: [['ประเภท', SHARE_TYPES[view.type]], ['ข้อมูล', view.content || 'ไม่ได้แนบเนื้อหา'],
                ['เวลาตรวจ', view.scanned_at ? new Date(view.scanned_at).toLocaleString('th-TH') : 'ไม่ระบุ']].map(([label, value]) => ({
                type: 'box', layout: 'horizontal', spacing: 'sm', flex: 1, contents: [
                    { type: 'text', text: label, size: 'sm', color: '#555555', wrap: false, flex: 20 },
                    { type: 'text', text: value, size: 'sm', color: '#111111', wrap: false, flex: 55 },
                ],
            })) },
        { type: 'box', layout: 'vertical', spacing: 'xs', margin: 'lg', contents: [
            { type: 'button', style: 'link', height: 'sm', color: '#16883c',
                action: { type: 'uri', label: 'ดูรายละเอียดผลตรวจสอบ', uri: shareLink(prepared.token) } },
        ] },
    ];
    return { type: 'flex', altText: `ผลตรวจสอบ GunGong: ${status}`, contents: {
        type: 'bubble', body: { type: 'box', layout: 'vertical', spacing: 'md', contents: body },
        footer: { type: 'box', layout: 'vertical', contents: [
            { type: 'separator', color: '#f0f0f0' },
            { type: 'box', layout: 'horizontal', flex: 1, spacing: 'md', margin: 'md', contents: [
                { type: 'image', url: new URL('img/logo.png', LINE_ENDPOINT_URL).href, flex: 1, gravity: 'center' },
                { type: 'text', text: 'Gungong (กันโกง)', flex: 19, size: 'xs', color: '#999999',
                    weight: 'bold', gravity: 'center', wrap: false },
                { type: 'image', url: 'https://vos.line-scdn.net/service-notifier/footer_go_btn.png',
                    flex: 1, gravity: 'center', size: 'xxs', action: {
                        type: 'uri', label: 'เปิด GunGong', uri: `https://miniapp.line.me/${LIFF_ID}`,
                    } },
            ] },
        ] },
    } };
}

export function sendHistoryShare(prepared, sdk = globalThis.window?.liff) {
    if (!canShareHistory(sdk)) throw new Error('SHARE_NOT_SUPPORTED');
    // Called directly from the user's click after preparation, preserving the
    // gesture for external-browser popups. No DB/auth await before the picker.
    return sdk.shareTargetPicker([buildHistoryShareMessage(prepared)]).then(result =>
        result?.status === 'success' ? 'shared' : 'cancelled');
}

export function historyShareError(error) {
    return ({ LOGIN_REQUIRED: 'กรุณาเข้าสู่ระบบ LINE ก่อนแชร์',
        SHARE_EXPIRED: 'ลิงก์นี้หมดอายุหรือหยุดแชร์แล้ว กรุณาสร้างลิงก์ใหม่',
        SHARE_NOT_SUPPORTED: 'ยังแชร์ผ่าน LINE ไม่ได้ กรุณาเปิด Mini App ใน LINE และตรวจการตั้งค่า shareTargetPicker',
        SHARE_RATE_LIMIT: 'สร้างลิงก์ถี่เกินไป กรุณารอสักครู่แล้วลองอีกครั้ง',
        SHARE_CONFLICT: 'ไม่สามารถใช้ลิงก์นี้ได้ กรุณาปิดแล้วเปิดหน้าต่างแชร์ใหม่',
    })[error?.message] || 'เตรียมการแชร์ไม่สำเร็จ กรุณาลองอีกครั้ง';
}
