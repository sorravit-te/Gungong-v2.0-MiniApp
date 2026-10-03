// Member-specific reactions stay in memory, never browser storage or the public feed.
export function createCommunityViewerCache({ ttl = 30000, now = Date.now } = {}) {
    const owners = new Map();
    const pending = new Map();
    const getOwner = owner => {
        if (!owners.has(owner)) owners.set(owner, { states: {}, updated: {}, versions: {} });
        return owners.get(owner);
    };
    return {
        peek(owner) { return owners.get(owner)?.states || {}; },
        async read(owner, ids, loader) {
            if (!owner || !ids.length) return {};
            const entry = getOwner(owner);
            const missing = [...new Set(ids)].filter(id => !entry.states[id] || now() - entry.updated[id] >= ttl).sort();
            if (!missing.length) return entry.states;
            const key = JSON.stringify([owner, missing]);
            if (!pending.has(key)) {
                const versions = { ...entry.versions };
                const work = Promise.resolve().then(async () => {
                    const batches = [];
                    for (let start = 0; start < missing.length; start += 50) batches.push(loader(missing.slice(start, start + 50)));
                    const results = Object.assign({}, ...await Promise.all(batches));
                    if (owners.get(owner) !== entry) throw new Error('CACHE_INVALIDATED');
                    for (const id of missing) {
                        // A confirmed like/unlike must win over an older viewer-state read.
                        if (versions[id] !== entry.versions[id]) continue;
                        const state = results[id];
                        if (state && typeof state.liked === 'boolean' && typeof state.can_edit === 'boolean') {
                            entry.states[id] = state; entry.updated[id] = now();
                        } else { delete entry.states[id]; delete entry.updated[id]; }
                    }
                    return { ...entry.states };
                }).catch(error => {
                    if (error.message === 'LOGIN_REQUIRED' && owners.get(owner) === entry) owners.delete(owner);
                    throw error;
                }).finally(() => { if (pending.get(key) === work) pending.delete(key); });
                pending.set(key, work);
            }
            return pending.get(key);
        },
        write(owner, id, change, expected) {
            if (!owner) return;
            if (expected && owners.get(owner)?.states !== expected) return;
            const entry = getOwner(owner);
            entry.states[id] = { ...entry.states[id], ...change };
            entry.updated[id] = now();
            entry.versions[id] = (entry.versions[id] || 0) + 1;
        },
        invalidate() { owners.clear(); pending.clear(); },
    };
}

export const communityViewerCache = createCommunityViewerCache();
