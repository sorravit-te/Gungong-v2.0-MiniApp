export const SHARE_TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/u;

export function getSharedToken(search = '', hash = '') {
    const direct = new URLSearchParams(hash.replace(/^#/u, '')).get('share');
    if (SHARE_TOKEN_PATTERN.test(direct || '')) return direct;
    // LIFF can initially put a permanent link's suffix inside liff.state.
    // Extract only a bounded token; don't navigate to a nested URL.
    const state = new URLSearchParams(search).get('liff.state');
    if (state) {
        try {
            const fragment = new URL(state, 'https://local.invalid/').hash;
            const token = new URLSearchParams(fragment.slice(1)).get('share');
            if (SHARE_TOKEN_PATTERN.test(token || '')) return token;
        } catch { /* Not a share link. */ }
    }
    return null;
}
