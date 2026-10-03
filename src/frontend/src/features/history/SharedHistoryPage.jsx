import { useEffect, useState } from 'react';
import { readHistoryShare } from './historyShare';
import SharedScanDetails from './SharedScanDetails';
import { LINE_ENDPOINT_URL, initializePublicLineSession } from '../auth/lineAuth';
import './historyShare.css';

export default function SharedHistoryPage({ token }) {
    const [result, setResult] = useState(null);
    const [failed, setFailed] = useState(false);
    const [retry, setRetry] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        let active = true;
        readHistoryShare(token, controller.signal).then(data => {
            if (active) { setResult(data); setFailed(false); }
        }).catch(() => { if (active) setFailed(true); });
        return () => { active = false; controller.abort(); };
    }, [token, retry]);
    useEffect(() => {
        // Process LIFF callback restoration without waiting for it, loading
        // private History, analytics or fetching a recipient profile.
        try { initializePublicLineSession().catch(() => {}); }
        catch { /* Public snapshot remains readable without the SDK. */ }
        const meta = document.createElement('meta');
        meta.name = 'robots'; meta.content = 'noindex, nofollow'; document.head.append(meta);
        return () => meta.remove();
    }, []);
    return <main className="shared-history-page">
        <article className="shared-history-card">
            <header><img src="/img/logo.png" alt="" /><span>GunGong (กันโกง)</span></header>
            <h1>ผลตรวจสอบที่แชร์</h1>
            {failed ? <div role="alert"><p>เปิดผลตรวจสอบไม่ได้ ลิงก์อาจหมดอายุ ถูกหยุดแชร์ หรือการเชื่อมต่อขัดข้อง</p>
                <button type="button" onClick={() => { setFailed(false); setRetry(value => value + 1); }}>ลองอีกครั้ง</button></div>
                : result ? <SharedScanDetails data={result} />
                    : <p role="status"><span className="history-share-spinner" aria-hidden="true" /> กำลังโหลดผลตรวจสอบ…</p>}
            <a className="history-share-primary" href={`${LINE_ENDPOINT_URL}?section=scanner`}>ตรวจสอบด้วยตัวเอง</a>
        </article>
    </main>;
}
