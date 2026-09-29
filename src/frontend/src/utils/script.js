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

// ==================== BANK DATA ==================== //

export const banks = [
    { code: "KBANK", name: "กสิกรไทย (KBANK)", color: "#138f2d" },
    { code: "SCB", name: "ไทยพาณิชย์ (SCB)", color: "#4e2e7f" },
    { code: "BBL", name: "กรุงเทพ (BBL)", color: "#1e4598" },
    { code: "KTB", name: "กรุงไทย (KTB)", color: "#1ba5e1" },
    { code: "BAY", name: "กรุงศรี (BAY)", color: "#fec43b" },
    { code: "TTB", name: "ทหารไทยธนชาต (TTB)", color: "#1279be" },
    { code: "BAAC", name: "ธ.ก.ส. (BAAC)", color: "#4b9b1d" },
    { code: "GSB", name: "ออมสิน (GSB)", color: "#eb198d" },
];

// ==================== API FUNCTIONS ==================== //

import { getUserId } from './liff';

// Fraud Check API
export async function callFraudCheckApi(message, type) {
    const apiUrl = `${API_BASE_URL}/check-fraud`;

    const userId = await getUserId();
    const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
        },
        body: JSON.stringify({ message: message, user_id: userId }),
    });

    if (!response.ok) {
        let errorMessage = `Server Error (${response.status})`;
        try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorMessage;
        } catch (e) {
            errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
    }

    return await response.json();
}

// Bank Blacklist Check API
export async function callBlacklistApi(endpoint, payload) {
    const apiUrl = `${API_BASE_URL}${endpoint}`;

    const userId = await getUserId();
    const payloadWithUser = { ...payload, user_id: userId };

    const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payloadWithUser),
    });

    if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    return await response.json();
}

// Check Link
export async function checkLink(url) {
    if (!url || !url.trim()) {
        throw new Error("EMPTY_INPUT");
    }
    return await callFraudCheckApi(url.trim(), "link");
}

// Check SMS/Message
export async function checkSMS(text) {
    if (!text || !text.trim()) {
        throw new Error("EMPTY_INPUT");
    }
    return await callFraudCheckApi(text.trim(), "sms");
}

// Check Bank Account
export async function checkBank(bankCode, accountNo) {
    if (!bankCode) {
        throw new Error("NO_BANK_SELECTED");
    }
    if (!accountNo || !accountNo.trim()) {
        throw new Error("EMPTY_ACCOUNT");
    }
    return await callBlacklistApi("/check-bank", {
        bank_code: bankCode,
        account_number: accountNo.trim()
    });
}

// Check Phone Number
export async function checkPhone(phoneNo) {
    if (!phoneNo || !phoneNo.trim()) {
        throw new Error("EMPTY_PHONE");
    }
    return await callBlacklistApi("/check-phone", {
        phone_number: phoneNo.trim()
    });
}

// ==================== HISTORY FUNCTIONS ==================== //

// Load History
export async function loadHistory(limit = 50) {
    const userId = await getUserId();
    let apiUrl = `${API_BASE_URL}/cache-entries?limit=${limit}`;
    if (userId) {
        apiUrl += `&user_id=${userId}`;
    }

    const response = await fetch(apiUrl, {
        headers: { "ngrok-skip-browser-warning": "true" },
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server Error (${response.status}): ${errorText || response.statusText}`);
    }

    const data = await response.json();
    return data.entries || [];
}

// Get History by ID
export async function getHistoryById(id) {
    const response = await fetch(`${API_BASE_URL}/history/${id}`, {
        headers: { "ngrok-skip-browser-warning": "true" },
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch history entry: ${response.statusText}`);
    }

    return await response.json();
}

// Submit Feedback
export async function submitFeedback(historyId, feedbackType, comment = null) {
    const apiUrl = `${API_BASE_URL}/feedback`;
    const userId = await getUserId();

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            history_id: historyId,
            user_id: userId,
            feedback_type: feedbackType,
            comment: comment
        })
    });

    if (!response.ok) {
        throw new Error('Failed to submit feedback');
    }

    return await response.json();
}

// ==================== FILTER FUNCTIONS ==================== //

// Filter History Entries
export function filterHistory(entries, filters) {
    const { types = ['all'], dateRange = 'all' } = filters;

    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    return entries.filter((entry) => {
        // Type filter
        let typeMatch = types.includes('all') || types.includes(entry.type);

        // Date filter
        let dateMatch = dateRange === 'all';
        if (!dateMatch && entry.created_at) {
            const entryDate = new Date(entry.created_at);
            if (dateRange === 'today') {
                dateMatch = entryDate >= startOfDay;
            } else if (dateRange === 'yesterday') {
                const yesterday = new Date(startOfDay);
                yesterday.setDate(yesterday.getDate() - 1);
                const endOfYesterday = new Date(startOfDay);
                dateMatch = entryDate >= yesterday && entryDate < endOfYesterday;
            } else if (dateRange === 'week') {
                const lastWeek = new Date(startOfDay);
                lastWeek.setDate(lastWeek.getDate() - 7);
                dateMatch = entryDate >= lastWeek;
            }
        }

        return typeMatch && dateMatch;
    });
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

// Format Date (Thai locale)
export function formatDate(dateString) {
    if (!dateString) return '';
    const dateObj = new Date(dateString);
    return dateObj.toLocaleDateString('th-TH', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    });
}

// Get Type Icon SVG
export function getTypeIcon(type) {
    const icons = {
        link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>',
        message: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
        text: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
        sms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
        qr: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>',
        bank: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>',
        phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>',
    };
    return icons[type] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>';
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

    if (errorString.includes("Failed to fetch") || errorString.includes("NetworkError")) {
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
    } else if (errorString === "NO_BANK_SELECTED") {
        return {
            title: "กรุณาเลือกธนาคาร",
            message: ""
        };
    } else if (errorString === "EMPTY_ACCOUNT") {
        return {
            title: "กรุณากรอกเลขบัญชี",
            message: ""
        };
    } else if (errorString === "EMPTY_PHONE") {
        return {
            title: "กรุณากรอกเบอร์โทรศัพท์",
            message: ""
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

// PDPA Functions
export function checkPDPAStatus() {
    return localStorage.getItem('gungong_pdpa_accepted') === 'true';
}

export function acceptPDPA() {
    localStorage.setItem('gungong_pdpa_accepted', 'true');
}

// Default export for convenience
export default {
    API_BASE_URL,
    banks,
    checkLink,
    checkSMS,
    checkBank,
    checkPhone,
    loadHistory,
    getHistoryById,
    submitFeedback,
    filterHistory,
    formatTime,
    formatDate,
    getTypeIcon,
    getTypeName,
    getErrorMessage,
    checkPDPAStatus,
    acceptPDPA,
};
