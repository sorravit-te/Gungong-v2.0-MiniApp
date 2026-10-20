// LIFF Configuration
// A separate Developing build can use its own internal channel without changing
// the existing Published app. Never derive this ID from query parameters.
export const LIFF_ID = import.meta.env?.VITE_LIFF_ID || "2008548759-KkM4Noxa";
if (!/^[0-9]+-[A-Za-z0-9]+$/u.test(LIFF_ID)) throw new Error('INVALID_LIFF_ID');

// Get User ID (for API calls)
export async function getUserId() {
    if (typeof window !== 'undefined' && window.liff) {
        if (window.liff.isInClient() || window.liff.isLoggedIn()) {
            try {
                const profile = await window.liff.getProfile();
                return profile.userId;
            } catch (e) {
                console.warn("Error getting profile:", e);
            }
        }
    }
    // Anonymous browsers must not share a mock personal History identity.
    return null;
}

// Scan QR Code
export async function scanCode() {
    if (!window.liff) {
        throw new Error("LIFF not available");
    }

    // Check if LIFF is in client
    if (!window.liff.isInClient() && !window.liff.isLoggedIn()) {
        throw new Error("NOT_IN_LINE");
    }

    if (window.liff.scanCodeV2) {
        const result = await window.liff.scanCodeV2();
        return result.value;
    }

    throw new Error("SCAN_NOT_SUPPORTED");
}
