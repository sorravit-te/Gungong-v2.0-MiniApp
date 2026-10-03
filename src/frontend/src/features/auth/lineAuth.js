import { LIFF_ID } from './liff.js';

export const LINE_ENDPOINT_URL = import.meta.env?.VITE_LINE_ENDPOINT_URL || 'https://gungong-vercel-preview.vercel.app/';
const endpoint = new URL(LINE_ENDPOINT_URL);
if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
    throw new Error('INVALID_LINE_ENDPOINT');
}
export const APP_SECTIONS = new Set(['home', 'report',
    'scanner', 'check-link', 'check-sms', 'check-content', 'check-personal', 'scan-qr', 'social', 'history', 'scan-image']);
const initializations = new WeakMap();
const mobileAttempts = new WeakSet();
const MOBILE_HANDOFF_KEY = 'gungong_line_handoff';
const MOBILE_HANDOFF_COOLDOWN_MS = 30000;

export function getMobileLineTarget({ sdk, location, navigator, callback = false }) {
    if (!location || location.origin !== new URL(LINE_ENDPOINT_URL).origin || callback || sdk?.isInClient?.()) return null;
    // Without the SDK, don't risk bouncing an existing LINE WebView back into LINE.
    if (!sdk && /\bLine\/|\bLIFF/iu.test(navigator?.userAgent || '')) return null;
    const mobile = ['ios', 'android'].includes(sdk?.getOS?.()) ||
        /Android|iPhone|iPad|iPod/u.test(navigator?.userAgent || '') ||
        (navigator?.platform === 'MacIntel' && navigator?.maxTouchPoints > 1);
    if (!mobile) return null;
    const params = new URLSearchParams(location.search);
    const fragment = new URLSearchParams((location.hash || '').replace(/^#/u, ''));
    if ([...params.keys()].some(key => key.startsWith('liff.') || key === 'lineAppVersion') ||
        ['code', 'state', 'access_token', 'id_token', 'error'].some(key => params.has(key) || fragment.has(key))) return null;
    const approved = new URL(getLineLoginRedirect(params.get('section'), location.search));
    return `https://miniapp.line.me/${LIFF_ID}${approved.search}`;
}

function handoffMobile(sdk, callback) {
    const browser = globalThis.window;
    const target = getMobileLineTarget({ sdk, callback, location: browser?.location, navigator: globalThis.navigator });
    if (!target) return false;
    if (mobileAttempts.has(browser)) return true;
    // Brief cooldown prevents an immediate browser fallback loop, not all future visits.
    try {
        const attemptedAt = Number(browser.sessionStorage.getItem(MOBILE_HANDOFF_KEY));
        const age = Date.now() - attemptedAt;
        if (attemptedAt > 0 && age >= 0 && age < MOBILE_HANDOFF_COOLDOWN_MS) return false;
        browser.sessionStorage.setItem(MOBILE_HANDOFF_KEY, String(Date.now()));
    } catch { /* Storage can be disabled. The per-page guard still prevents StrictMode duplicates. */ }
    mobileAttempts.add(browser);
    browser.location.replace(target);
    return true;
}

function getSdk() {
    const sdk = globalThis.window?.liff;
    if (!sdk) throw new Error('LINE_SDK_UNAVAILABLE');
    return sdk;
}

async function withDeadline(operation, timeoutMs) {
    let timer;
    const controller = new AbortController();
    try {
        return await Promise.race([operation(controller.signal), new Promise((_, reject) => {
            timer = setTimeout(() => {
                controller.abort();
                reject(new Error('LINE_SESSION_TIMEOUT'));
            }, timeoutMs);
        })]);
    } finally { clearTimeout(timer); }
}

function assertActive(signal) {
    if (signal.aborted) throw new Error('LINE_SESSION_TIMEOUT');
}

async function initializeSdk() {
    const sdk = getSdk();
    // One initialization per page/SDK, including React StrictMode's effect replay.
    // Do not mutate the callback URL until LIFF has processed its auth parameters.
    if (!initializations.has(sdk)) {
        const initialization = Promise.resolve().then(() => sdk.init({ liffId: LIFF_ID }));
        initializations.set(sdk, initialization);
        initialization.catch(() => initializations.delete(sdk));
    }
    await initializations.get(sdk);
    return sdk;
}

// Shared snapshots need callback restoration, not a recipient profile or
// personal History. Reuse the same StrictMode-safe SDK initialization.
export function initializePublicLineSession() {
    return initializeSdk();
}

async function readProfile(sdk, signal, onSessionReady) {
    assertActive(signal);
    if (!sdk.isLoggedIn()) return null;
    if (!sdk.getAccessToken()) throw new Error('LINE_SESSION_INVALID');
    // The API verifies this token independently. Start reads while the display
    // profile loads; do not treat this callback as an authenticated identity.
    onSessionReady?.();
    const profile = await sdk.getProfile();
    assertActive(signal);
    if (!profile?.userId) throw new Error('LINE_SESSION_INVALID');
    return profile;
}

export function initializeLineSession({ timeoutMs = 8000, onSessionReady } = {}) {
    const parameters = new URLSearchParams(globalThis.window?.location?.search);
    const callback = ['code', 'state', 'liff.state', 'access_token', 'id_token', 'error'].some(key => parameters.has(key));
    // getOS/isInClient are documented pre-init APIs. A central-link handoff must
    // not depend on slow/failed SDK initialization; callback URLs remain untouched.
    if (handoffMobile(globalThis.window?.liff, callback)) return Promise.resolve(null);
    return withDeadline(async signal => {
        const sdk = await initializeSdk();
        assertActive(signal);
        return readProfile(sdk, signal, onSessionReady);
    }, timeoutMs);
}

// Read again after LIFF initialization, which restores deep-link parameters.
// Never mutate LIFF/OAuth parameters or accept an arbitrary navigation target.
export function getAppEntry(search = '') {
    const params = new URLSearchParams(search);
    const rawId = params.get('historyId');
    const historyId = rawId && /^[A-Za-z0-9_-]{1,128}$/u.test(rawId) ? rawId : null;
    const requested = params.get('section');
    return { section: historyId ? 'history' : APP_SECTIONS.has(requested) ? requested : 'home', historyId };
}

export function getLineLoginRedirect(section, search = '') {
    // Never accept a caller-supplied origin or forward OAuth credentials.
    const redirect = new URL(LINE_ENDPOINT_URL);
    if (APP_SECTIONS.has(section)) redirect.searchParams.set('section', section);
    const historyId = new URLSearchParams(search).get('historyId');
    if (historyId && /^[A-Za-z0-9_-]{1,128}$/u.test(historyId)) {
        redirect.searchParams.set('historyId', historyId);
    }
    const reportId = new URLSearchParams(search).get('reportId');
    if (section === 'report' && /^[a-f0-9]{64}$/u.test(reportId || '')) {
        redirect.searchParams.set('reportId', reportId);
    }
    return redirect.href;
}

export function loginWithLine({ section = 'home', timeoutMs = 8000 } = {}) {
    return withDeadline(async signal => {
        const sdk = await initializeSdk();
        assertActive(signal);
        if (sdk.isInClient() || sdk.isLoggedIn()) return readProfile(sdk, signal);
        sdk.login({ redirectUri: getLineLoginRedirect(section, globalThis.window?.location?.search) });
        return null; // Navigation, not a completed login. Read identity after returning.
    }, timeoutMs);
}

export function logoutFromLine() {
    const sdk = getSdk();
    // The LINE client automatically signs in; don't pretend it can stay logged out.
    if (sdk.isInClient()) throw new Error('LINE_CLIENT_LOGOUT_UNSUPPORTED');
    if (sdk.isLoggedIn()) sdk.logout();
}

export function getDisplayUser(lineProfile) {
    if (lineProfile) return { uid: lineProfile.userId, displayName: lineProfile.displayName,
        photoURL: lineProfile.pictureUrl, provider: 'line' };
    return null;
}

export function getLineAuthError(error) {
    if (error?.message === 'LINE_SESSION_TIMEOUT') return 'การเชื่อมต่อ LINE ใช้เวลานาน กรุณาลองเข้าสู่ระบบอีกครั้ง';
    if (error?.message === 'LINE_SDK_UNAVAILABLE') return 'โหลดระบบ LINE ไม่สำเร็จ กรุณารีเฟรชหน้าเว็บ';
    return 'เข้าสู่ระบบ LINE ไม่สำเร็จ กรุณาลองอีกครั้ง';
}
