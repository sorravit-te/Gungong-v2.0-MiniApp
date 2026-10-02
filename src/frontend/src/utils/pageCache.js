// Short-lived, memory-only read cache. Never persist tokens or personal History.
export const PAGE_CACHE_TTL = 30000;

export function createPageCache({ ttl = PAGE_CACHE_TTL, now = Date.now } = {}) {
    const entries = new Map();
    return {
        peek(key) { return entries.get(key)?.data; },
        async read(key, loader) {
            let entry = entries.get(key);
            if (entry?.data !== undefined && now() - entry.updated < ttl) return entry.data;
            if (entry?.pending) return entry.pending;
            entry ??= {};
            entries.set(key, entry);
            entry.pending = Promise.resolve().then(loader).then(data => {
                // Invalidation/logout may happen while an old request is still resolving.
                if (entries.get(key) !== entry) throw new Error('CACHE_INVALIDATED');
                entry.data = data; entry.updated = now();
                return data;
            }).catch(error => {
                if (error.message === 'LOGIN_REQUIRED' && entries.get(key) === entry) entries.delete(key);
                throw error;
            }).finally(() => { entry.pending = null; });
            return entry.pending;
        },
        write(key, data) { entries.set(key, { data, updated: now() }); },
        invalidate(key) { if (key === undefined) entries.clear(); else entries.delete(key); },
    };
}

export const historyCache = createPageCache();
export const communityCache = createPageCache();

export function invalidateHistoryCache() {
    historyCache.invalidate();
    globalThis.window?.dispatchEvent?.(new Event('gungong:history-changed'));
}
