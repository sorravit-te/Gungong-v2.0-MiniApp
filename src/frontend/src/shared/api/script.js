// ==================== API CONFIGURATION ==================== //

// Auto-detect API URL based on environment
export function getApiBaseUrl() {
    if (typeof window === 'undefined') return 'http://localhost:8000';

    // Check if running in file:// protocol
    if (window.location.protocol === "file:") {
        return "http://localhost:8000";
    }

    // Check if running on localhost
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return "http://localhost:8000";
    }

    // Production: Use same origin
    return window.location.origin;
}

export const API_BASE_URL = getApiBaseUrl();

// ==================== API FUNCTIONS ==================== //

import { getUserId } from '../../features/auth/liff.js';
import { getSessionHeaders } from '../../features/auth/session.js';
import { invalidateHistoryCache } from '../cache/pageCache.js';

// Fraud Check API
export async function callFraudCheckApi(message, type, options = {}) {
    const apiUrl = `${API_BASE_URL}/check-fraud`;
    const timeoutMs = options.timeoutMs;
    const resolveUserId = options.getUserIdFn || getUserId;
    const controller = timeoutMs ? new AbortController() : null;
    let didTimeout = false;
    let timeoutId = null;

    const requestPromise = (async () => {
        const userId = await resolveUserId();
        const response = await fetch(apiUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "ngrok-skip-browser-warning": "true",
                ...await getSessionHeaders({ required: false }),
            },
            body: JSON.stringify({
                message: message,
                user_id: userId,
                message_type: type,
            }),
            signal: controller?.signal,
        });

        if (response.ok) {
            try {
                const result = await response.json();
                invalidateHistoryCache();
                return result;
            } catch {
                throw new Error("INVALID_RESPONSE");
            }
        }

        let errorMessage = `Server Error (${response.status})`;
        try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorMessage;
        } catch {
            errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
    })();

    const timeoutPromise = timeoutMs ? new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
            didTimeout = true;
            controller.abort();
            reject(new Error("REQUEST_TIMEOUT"));
        }, timeoutMs);
    }) : null;

    try {
        return await (timeoutPromise
            ? Promise.race([requestPromise, timeoutPromise])
            : requestPromise);
    } catch (error) {
        if (didTimeout || error?.name === "AbortError") {
            throw new Error("REQUEST_TIMEOUT");
        }
        throw error;
    } finally {
        if (timeoutId !== null) clearTimeout(timeoutId);
    }
}

// Check Link
export async function checkLink(url) {
    if (!url || !url.trim()) {
        throw new Error("EMPTY_INPUT");
    }
    return await callFraudCheckApi(url.trim(), "link", { timeoutMs: 12000 });
}

// Check SMS/Message
export async function checkSMS(text) {
    if (!text || !text.trim()) {
        throw new Error("EMPTY_INPUT");
    }
    return await callFraudCheckApi(text.trim(), "sms");
}

// ==================== HISTORY FUNCTIONS ==================== //

// Load History
export async function loadHistory(limit = 50) {
    // The backend derives the owner from the verified session, not a query ID.
    // The UI uses entries only: do not wait for a separate full-history count.
    const apiUrl = `${API_BASE_URL}/cache-entries?limit=${limit}&include_total=false`;
    const controller = new AbortController();
    let timer;
    const deadline = new Promise((_, reject) => {
        timer = setTimeout(() => { controller.abort(); reject(new Error('REQUEST_TIMEOUT')); }, 15000);
    });
    try {
        return await Promise.race([deadline, (async () => {
            const headers = { "ngrok-skip-browser-warning": "true", ...await getSessionHeaders() };
            for (let attempt = 0; attempt < 2; attempt += 1) {
                if (controller.signal.aborted) throw new Error('REQUEST_TIMEOUT');
                let response;
                try {
                    response = await fetch(apiUrl, { headers, cache: 'no-store', signal: controller.signal });
                } catch (error) {
                    if (attempt === 0 && !controller.signal.aborted) continue;
                    throw error;
                }
                if (response.status === 401) throw new Error('LOGIN_REQUIRED');
                if (!response.ok) {
                    if (attempt === 0 && [502, 503, 504].includes(response.status)) continue;
                    throw new Error('HISTORY_UNAVAILABLE');
                }
                const data = await response.json();
                if (!Array.isArray(data?.entries)) throw new Error('HISTORY_UNAVAILABLE');
                return data.entries;
            }
        })()]);
    } finally { clearTimeout(timer); }
}

// Get History by ID
export async function getHistoryById(id, { signal } = {}) {
    const response = await fetch(`${API_BASE_URL}/history/${encodeURIComponent(id)}`, {
        headers: { "ngrok-skip-browser-warning": "true", ...await getSessionHeaders() },
        cache: 'no-store',
        signal,
    });

    if (!response.ok) {
        const error = new Error(`Failed to fetch history entry: ${response.status}`);
        error.status = response.status;
        throw error;
    }

    return await response.json();
}

// ==================== UTILITY FUNCTIONS ==================== //

// Format Time (Thai locale)
export function formatTime(dateString) {
    if (!dateString) return '';
    const dateObj = new Date(dateString);
    return dateObj.toLocaleTimeString('th-TH', {
        hour: '2-digit',
        minute: '2-digit',
    });
}

// Get Type Name
export function getTypeName(type) {
    const names = {
        link: 'Link',
        message: 'Message',
        text: 'Text',
        sms: 'SMS',
        qr: 'QR Code',
        bank: 'Bank',
        phone: 'Phone',
    };
    return names[type] || 'Unknown';
}

// Get User-Friendly Error Message
export function getErrorMessage(error) {
    const errorString = error.message || error.toString();

    if (errorString === "REQUEST_TIMEOUT") {
        return {
            title: "การตรวจสอบลิงก์หมดเวลา",
            message: "การตรวจสอบลิงก์ใช้เวลานานเกินกำหนด กรุณาลองใหม่อีกครั้ง"
        };
    } else if (errorString === "INVALID_RESPONSE") {
        return {
            title: "ได้รับผลการตรวจสอบไม่สมบูรณ์",
            message: "กรุณาลองตรวจสอบอีกครั้ง"
        };
    } else if (errorString.includes("Failed to fetch") || errorString.includes("NetworkError")) {
        return {
            title: "ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์",
            message: "กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ตและลองใหม่อีกครั้ง"
        };
    } else if (errorString.includes("500")) {
        return {
            title: "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์",
            message: "กรุณาลองใหม่อีกครั้งในอีกสักครู่"
        };
    } else if (errorString.includes("503")) {
        return {
            title: "บริการไม่พร้อมใช้งานชั่วคราว",
            message: "เซิร์ฟเวอร์กำลังบำรุงรักษา กรุณาลองใหม่ในภายหลัง"
        };
    } else if (errorString.includes("timeout") || errorString.includes("408")) {
        return {
            title: "การเชื่อมต่อหมดเวลา",
            message: "ข้อความของคุณอาจยาวเกินไป กรุณาลองข้อความสั้นกว่านี้"
        };
    } else if (errorString === "EMPTY_INPUT") {
        return {
            title: "กรุณากรอกข้อมูล",
            message: "ช่องว่างห้ามเว้นว่าง"
        };
    } else if (errorString === "NOT_IN_LINE") {
        return {
            title: "แจ้งเตือน",
            message: "ฟีเจอร์นี้ใช้งานได้เฉพาะบนแอป LINE เท่านั้น"
        };
    } else if (errorString === "SCAN_NOT_SUPPORTED") {
        return {
            title: "ฟีเจอร์ไม่รองรับ",
            message: "กรุณาเปิดใน LINE Application เพื่อใช้งานสแกน QR"
        };
    }

    return {
        title: "เกิดข้อผิดพลาด",
        message: errorString
    };
}
