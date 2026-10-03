import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { createHistoryShare, newShareToken, revokeHistoryShare, sendHistoryShare, historyShareError } from './historyShare';
import SharedScanDetails from './SharedScanDetails';
import './historyShare.css';

export default function HistoryShareDialog({ entry, attempt, onClose }) {
    const dialog = useRef(null);
    const controller = useRef(null);
    const mounted = useRef(true);
    const busy = useRef(false);
    const [pending, setPending] = useState(false);
    const [consent, setConsent] = useState(false);
    const [includeContent, setIncludeContent] = useState(attempt.includeContent ?? true);
    const [prepared, setPrepared] = useState(attempt.data || null);
    const [notice, setNotice] = useState('');
    const [error, setError] = useState('');
    const close = () => { if (!busy.current) onClose(); };

    useLayoutEffect(() => {
        const element = dialog.current;
        const previousFocus = document.activeElement;
        const overflow = document.body.style.overflow;
        element.showModal();
        document.body.style.overflow = 'hidden';
        return () => {
            element.close(); document.body.style.overflow = overflow;
            previousFocus?.focus?.({ preventScroll: true });
        };
    }, []);
    useEffect(() => {
        mounted.current = true;
        return () => { mounted.current = false; controller.current?.abort(); };
    }, []);

    const operate = async action => {
        if (busy.current) return;
        busy.current = true; setPending(true); setError(''); setNotice('');
        controller.current = new AbortController();
        try { await action(controller.current.signal); }
        catch (failure) { if (mounted.current) setError(historyShareError(failure)); }
        finally { busy.current = false; if (mounted.current) setPending(false); }
    };
    const prepare = () => {
        if (!consent) return;
        void operate(async signal => {
            // Keep the same token after uncertain writes/retries; never generate
            // another public snapshot merely because the response was delayed.
            attempt.token ||= newShareToken();
            attempt.includeContent = includeContent;
            const data = await createHistoryShare(entry.id, attempt.token, includeContent, signal);
            attempt.data = data;
            if (mounted.current) setPrepared(data);
        });
    };
    const send = () => {
        void operate(async () => {
            const outcome = await sendHistoryShare(prepared);
            if (mounted.current) setNotice(outcome === 'shared' ? 'แชร์ผ่าน LINE สำเร็จแล้ว' : 'ยกเลิกการส่งแล้ว ยังไม่ได้ส่งข้อความ');
        });
    };
    const revoke = () => {
        void operate(async signal => {
            await revokeHistoryShare(attempt.token, signal);
            delete attempt.data; delete attempt.token; delete attempt.includeContent;
            if (mounted.current) { setPrepared(null); setConsent(false); setNotice('หยุดแชร์แล้ว ลิงก์เดิมเปิดไม่ได้อีก'); }
        });
    };

    return createPortal(<dialog ref={dialog} className="history-share-dialog" aria-labelledby="history-share-title"
        onCancel={event => { event.preventDefault(); close(); }}>
        <button type="button" className="history-share-close" aria-label="ปิดหน้าต่างแชร์" disabled={pending} onClick={close}>×</button>
        <h2 id="history-share-title">{prepared ? 'ตัวอย่างผลที่เพื่อนจะเห็น' : 'แชร์ผลตรวจสอบ'}</h2>
        {prepared ? <SharedScanDetails data={prepared} /> : <>
            <p>แชร์เฉพาะผลรายการนี้ ไม่เปิดเผย History ทั้งหมด ชื่อ หรือรูปโปรไฟล์ของคุณ</p>
            <p>ผู้ที่มีลิงก์สามารถเปิดและส่งต่อได้เป็นเวลา 7 วัน ระบบลดข้อมูลส่วนบุคคลบางส่วน แต่ไม่รับประกันว่าซ่อนได้ทั้งหมด กรุณาตรวจตัวอย่างก่อนส่ง</p>
            <label className="history-share-option"><input type="checkbox" checked={includeContent}
                disabled={pending || Boolean(attempt.token)} onChange={event => setIncludeContent(event.target.checked)} />แนบเนื้อหาแบบย่อ (ซ่อน URL path และหมายเลขบางส่วน)</label>
            <label className="history-share-option"><input type="checkbox" checked={consent} disabled={pending}
                onChange={event => setConsent(event.target.checked)} />ฉันยินยอมสร้างลิงก์ที่ผู้อื่นเปิดอ่านผลนี้ได้</label>
        </>}
        {pending && <p role="status"><span className="history-share-spinner" aria-hidden="true" /> {prepared ? 'กำลังดำเนินการ…' : 'กำลังเตรียมผลสำหรับแชร์…'}</p>}
        {error && <p role="alert" className="history-share-error">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        <div className="history-share-actions">
            <button type="button" className="history-share-primary" disabled={pending || (!prepared && !consent)} onClick={prepared ? send : prepare}>
                {prepared ? 'เลือกผู้รับใน LINE' : 'สร้างลิงก์และดูตัวอย่าง'}</button>
            {prepared && <button type="button" disabled={pending} onClick={revoke}>หยุดแชร์ลิงก์นี้</button>}
            <button type="button" disabled={pending} onClick={close}>ปิด</button>
        </div>
    </dialog>, document.body);
}
