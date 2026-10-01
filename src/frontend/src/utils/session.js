// Tokens go only to our API, never localStorage or logs.
async function resolveSessionHeaders({ required = true } = {}) {
    const liff = globalThis.window?.liff;
    if (liff?.ready && !liff.isLoggedIn()) await liff.ready;
    if (liff?.isLoggedIn()) {
        const token = liff.getAccessToken();
        if (token) return { Authorization: `Bearer ${token}`, 'X-Auth-Provider': 'line' };
    }
    if (typeof navigator !== 'undefined' && typeof document !== 'undefined') {
        const { auth } = await import('./firebase.js');
        await auth.authStateReady();
        if (auth.currentUser) return {
            Authorization: `Bearer ${await auth.currentUser.getIdToken()}`,
            'X-Auth-Provider': 'firebase',
        };
    }
    if (required) throw new Error('LOGIN_REQUIRED');
    return {};
}

export async function getSessionHeaders(options = {}) {
    let timer;
    try {
        return await Promise.race([resolveSessionHeaders(options), new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('SESSION_TIMEOUT')), 6000);
        })]);
    } finally { clearTimeout(timer); }
}
