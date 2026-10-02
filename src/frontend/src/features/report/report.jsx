import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { REPORT_REASONS, reportError, submitContentReport, validateReport } from './reports';
import QrInputActions from '../../shared/qr/QrInputActions';

const EMPTY_DRAFT = { kind: 'link', content: '', reason: 'phishing', details: '' };
const REPORT_TYPES = [
  { kind: 'link', title: 'ลิงก์ / QR Code', mascot: '/img/mascot_02.png',
    description: 'รายงานลิงก์หรือ URL จาก QR Code' },
  { kind: 'text', title: 'ข้อความ', mascot: '/img/mascot_03.png',
    description: 'รายงานข้อความ SMS หรือแชตที่น่าสงสัย' },
];

export default function Report() {
  const { user, loading } = useAuth();
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [isQrReading, setIsQrReading] = useState(false);
  const attempt = useRef(null);
  const inFlight = useRef(false);
  const controller = useRef(null);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; controller.current?.abort(); };
  }, []);

  function change(field, value) {
    if (inFlight.current) return;
    setDraft(previous => ({ ...previous, [field]: value, ...(field === 'kind' ? { content: '' } : {}) }));
    attempt.current = null;
    setError('');
    setReceipt(null);
  }

  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || receipt || isQrReading) return;
    if (!user) { setError('กรุณาเข้าสู่ระบบ LINE เพื่อส่งเบาะแส'); return; }
    const invalid = validateReport(draft);
    if (invalid) { setError(invalid); return; }
    const payload = { ...draft, content: draft.content.trim(), details: draft.details.trim() };
    inFlight.current = true;
    setSaving(true);
    setError('');
    try {
      // Keep this ID after uncertain responses; the backend deduplicates retries.
      attempt.current ||= crypto.randomUUID();
      controller.current = new AbortController();
      const result = await submitContentReport(payload, attempt.current, controller.current.signal);
      if (mounted.current) setReceipt(result);
    } catch (cause) {
      if (mounted.current) setError(reportError(cause));
    } finally {
      inFlight.current = false;
      if (mounted.current) setSaving(false);
    }
  }

  return (
    <section id="report-page" aria-labelledby="report-title">
      <div className="section-content report-content">
        <header className="report-heading">
          <div className="report-icon" aria-hidden="true">
            <img src="/img/mascot_04.png" alt="" width="80" height="80" />
          </div>
          <div><h2 id="report-title">Report</h2><p>รายงาน / แจ้งเบาะแส</p></div>
        </header>
        <form className="report-form" onSubmit={submit} aria-busy={saving}>
          <fieldset disabled={saving || !!receipt}>
            <legend>ประเภทเบาะแส</legend>
            <div className="report-types scanner-feature-list">
              {REPORT_TYPES.map(type => (
                <label key={type.kind}
                  className={`scanner-feature-card report-type-card ${draft.kind === type.kind ? 'selected' : ''}`}>
                  <input type="radio" name="report-kind" value={type.kind} aria-label={type.title}
                    checked={draft.kind === type.kind} onChange={() => change('kind', type.kind)} />
                  <span className="scanner-feature-mascot" aria-hidden="true">
                    <img src={type.mascot} alt="" width="56" height="56" />
                  </span>
                  <span className="scanner-feature-copy">
                    <span className="scanner-feature-title">{type.title}</span>
                    <span className="scanner-feature-description">{type.description}</span>
                  </span>
                  <svg className="scanner-feature-arrow" aria-hidden="true" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    {draft.kind === type.kind
                      ? <><circle cx="12" cy="12" r="10" /><polyline points="7 12 10 15 17 8" /></>
                      : <polyline points="9 18 15 12 9 6" />}
                  </svg>
                </label>
              ))}
            </div>
            <label htmlFor="report-content">{draft.kind === 'link' ? 'ลิงก์ที่ต้องการรายงาน' : 'ข้อความที่ต้องการรายงาน'}</label>
            <textarea id="report-content" value={draft.content} required rows={draft.kind === 'link' ? 3 : 6}
              maxLength={draft.kind === 'link' ? 2048 : 5000}
              placeholder={draft.kind === 'link' ? 'https://example.com' : 'วางข้อความน่าสงสัยที่นี่'}
              onChange={event => change('content', event.target.value)} />
            {draft.kind === 'link' && <QrInputActions resetKey={draft.content}
              onRead={url => change('content', url)} onBusyChange={setIsQrReading}
              disabled={saving || !!receipt} />}
            <label htmlFor="report-reason">เหตุผลที่รายงาน</label>
            <select id="report-reason" value={draft.reason} onChange={event => change('reason', event.target.value)}>
              {REPORT_REASONS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <label htmlFor="report-details">รายละเอียดเพิ่มเติม <span>(ไม่บังคับ)</span></label>
            <textarea id="report-details" rows={3} maxLength={1000} value={draft.details}
              placeholder="พบจากที่ไหน หรือมีเหตุการณ์อะไรที่น่าสงสัย"
              onChange={event => change('details', event.target.value)} />
          </fieldset>
          {!user && <p className="report-login">{loading ? 'กำลังตรวจสอบการเข้าสู่ระบบ…' : 'กรุณาเข้าสู่ระบบ LINE เพื่อส่งเบาะแส'}</p>}
          {error && <p className="report-error" role="alert">{error}</p>}
          {receipt ? <div className="report-success" role="status">
            <strong>รับเบาะแสแล้ว</strong><p>สถานะ: รอตรวจสอบ</p>
            <p>หมายเลขอ้างอิง <span className="report-reference">{receipt.id}</span></p>
            <button type="button" onClick={() => {
              setDraft(EMPTY_DRAFT); setReceipt(null); attempt.current = null;
            }}>ส่งเบาะแสอื่น</button>
          </div> : <button className="report-submit" type="submit" disabled={!user || loading || saving || isQrReading}>
            {saving ? 'กำลังส่งเบาะแส…' : 'ส่งเบาะแส'}
          </button>}
        </form>
      </div>
    </section>
  );
}
