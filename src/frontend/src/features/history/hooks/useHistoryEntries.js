import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { historyCache } from '../../../shared/cache/pageCache';
import { loadHistory } from '../../../shared/api/script';

// Home and History share the same owner-scoped cache and in-flight request.
// Mount consumers with the current uid as their React key to reset on account changes.
export function useHistoryEntries() {
    const { user, loading: authLoading } = useAuth();
    const userId = user?.uid;
    const cached = userId ? historyCache.peek(userId) : undefined;
    const [entries, setEntries] = useState(cached || []);
    const [loading, setLoading] = useState(cached === undefined);
    const [error, setError] = useState('');
    const loaded = useRef(cached !== undefined);

    useEffect(() => {
        if (authLoading) return;
        let active = true;
        let fetching = false;
        let refreshAgain = false;
        const refresh = async () => {
            if (fetching || document.hidden) return;
            fetching = true;
            if (!loaded.current) setLoading(true);
            setError('');
            try {
                if (!userId) throw new Error('LOGIN_REQUIRED');
                const data = await historyCache.read(userId, loadHistory);
                if (active) { loaded.current = true; setEntries(data); }
            } catch (failure) {
                if (failure.message === 'CACHE_INVALIDATED') { refreshAgain = true; return; }
                if (active) {
                    if (failure.message === 'LOGIN_REQUIRED') { loaded.current = false; setEntries([]); }
                    setError(failure.message === 'LOGIN_REQUIRED'
                        ? 'กรุณาเข้าสู่ระบบ LINE เพื่อดูประวัติของคุณ'
                        : 'ไม่สามารถโหลดประวัติการตรวจสอบได้ กรุณาลองใหม่อีกครั้ง');
                }
            } finally {
                fetching = false;
                if (active) {
                    setLoading(false);
                    if (refreshAgain) { refreshAgain = false; void refresh(); }
                }
            }
        };
        const changed = () => { if (fetching) refreshAgain = true; else void refresh(); };
        void refresh();
        const timer = setInterval(() => {
            if (!userId || document.hidden || fetching) return;
            historyCache.expire(userId); changed();
        }, 30000);
        window.addEventListener('focus', refresh);
        window.addEventListener('gungong:history-changed', changed);
        document.addEventListener('visibilitychange', refresh);
        return () => {
            active = false;
            clearInterval(timer);
            window.removeEventListener('focus', refresh);
            window.removeEventListener('gungong:history-changed', changed);
            document.removeEventListener('visibilitychange', refresh);
        };
    }, [userId, authLoading]);
    return { entries, loading, error };
}
