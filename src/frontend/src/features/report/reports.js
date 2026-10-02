import { getApiBaseUrl } from '../../shared/api/script.js';
import { getSessionHeaders } from '../auth/session.js';

export const REPORT_REASONS = Object.freeze([
    { value: 'phishing', label: 'แอบอ้าง / หลอกให้กรอกข้อมูล' },
    { value: 'scam', label: 'หลอกโอนเงิน / เสนอผลตอบแทน' },
    { value: 'spam', label: 'สแปม / ข้อความรบกวน' },
    { value: 'other', label: 'อื่น ๆ' },
]);

export function validateReport({ kind, content, reason, details }) {
    if (!['link', 'text'].includes(kind) || !REPORT_REASONS.some(item => item.value === reason)) {
        return 'กรุณาเลือกประเภทและเหตุผลที่รายงาน';
    }
    const value = content.trim();
    if (!value) return kind === 'link' ? 'กรุณาใส่ลิงก์ที่ต้องการรายงาน' : 'กรุณาใส่ข้อความที่ต้องการรายงาน';
    if (value.length > (kind === 'link' ? 2048 : 5000) || details.trim().length > 1000) {
        return 'ข้อมูลยาวเกินกำหนด กรุณาลดความยาว';
    }
    if (kind === 'link') {
        try {
            const url = new URL(value);
            if (!/^https?:$/u.test(url.protocol) || !url.hostname || url.username || url.password ||
                /\s/u.test(value) || Array.from(value).some(char => char.codePointAt(0) < 32) ||
                !/^https?:\/\//iu.test(value)) throw new Error('URL');
        } catch { return 'กรุณาใส่ลิงก์เต็มที่ขึ้นต้นด้วย https:// หรือ http://'; }
    }
    return '';
}

export async function submitContentReport(draft, requestId, signal) {
    const headers = await getSessionHeaders();
    if (signal?.aborted) throw new Error('REPORT_UNCONFIRMED');
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(abort, 12000);
    try {
        const response = await fetch(`${getApiBaseUrl()}/api/reports`, {
            method: 'POST', cache: 'no-store', signal: controller.signal,
            headers: { 'Content-Type': 'application/json', ...headers },
            body: JSON.stringify({ ...draft, request_id: requestId }),
        });
        if (!response.ok) throw new Error(({ 401: 'LOGIN_REQUIRED', 422: 'INVALID_REPORT',
            413: 'INVALID_REPORT', 409: 'REPORT_CHANGED', 429: 'REPORT_RATE_LIMIT' })[response.status] || 'REPORT_UNCONFIRMED');
        const data = await response.json();
        if (!/^[a-f0-9]{64}$/u.test(data?.id || '') || data.status !== 'pending') {
            throw new Error('REPORT_UNCONFIRMED');
        }
        return data;
    } finally {
        clearTimeout(timer);
        signal?.removeEventListener('abort', abort);
    }
}

export function reportError(error) {
    return ({
        LOGIN_REQUIRED: 'กรุณาเข้าสู่ระบบ LINE เพื่อส่งเบาะแส',
        SESSION_TIMEOUT: 'เชื่อมต่อ LINE ไม่สำเร็จ กรุณาลองอีกครั้ง',
        INVALID_REPORT: 'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบเบาะแสก่อนส่ง',
        REPORT_CHANGED: 'ข้อมูลไม่ตรงกับรายการที่ส่งก่อนหน้า กรุณาแก้ไขข้อมูลแล้วส่งใหม่',
        REPORT_RATE_LIMIT: 'ส่งเบาะแสถี่เกินไป กรุณารอสักครู่แล้วลองอีกครั้ง',
    })[error?.message] || 'ยังยืนยันการรับเบาะแสไม่ได้ กรุณาลองส่งอีกครั้ง ระบบจะใช้หมายเลขเดิมเพื่อไม่ให้ส่งซ้ำ';
}
