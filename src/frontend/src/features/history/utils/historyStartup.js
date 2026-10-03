// Prefetch with a verified API session while LINE's display profile is loading.
// Bind data to the resolved owner only; failures never become empty success.
export function createHistoryStartup({ cache, load, isCurrent = () => true }) {
    let pending;
    let disposed = false;
    return {
        start() {
            if (disposed || pending) return;
            pending = Promise.resolve().then(load).then(data => ({ data }), error => ({ error }));
        },
        bind(owner) {
            if (disposed || !owner || !pending || !isCurrent()) return Promise.resolve();
            return cache.read(owner, async () => {
                const result = await pending;
                if (disposed || !isCurrent()) throw new Error('CACHE_INVALIDATED');
                if (result.error) throw result.error;
                return result.data;
            });
        },
        dispose() { disposed = true; },
    };
}
