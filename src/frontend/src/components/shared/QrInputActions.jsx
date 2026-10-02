import { useEffect, useRef, useState } from 'react';
import { scanCode } from '../../utils/liff';
import { getQrScanError, isQrScanCancelled, readQrUrl } from '../../utils/qrScan';
import { QR_IMAGE_TYPES, readQrImageUrl } from '../../utils/qrImage';
import '../../styles/qr-input.css';

export default function QrInputActions({ onRead, onBusyChange, disabled = false, resetKey }) {
  const [busy, setBusy] = useState(null);
  const [status, setStatus] = useState(null);
  const input = useRef(null);
  const activeRequest = useRef(null);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; activeRequest.current?.abort(); onBusyChange?.(false); };
  }, [onBusyChange]);
  // Input edits and route/type changes cancel stale reads instead of replacing newer text.
  useEffect(() => () => activeRequest.current?.abort(), [resetKey]);

  async function read(kind, file) {
    if (disabled || activeRequest.current) return;
    const request = new AbortController();
    activeRequest.current = request;
    setBusy(kind);
    setStatus(null);
    onBusyChange?.(true);
    try {
      const url = kind === 'image'
        ? await readQrImageUrl(file, { signal: request.signal })
        : await readQrUrl(scanCode, { signal: request.signal });
      if (!mounted.current || request.signal.aborted) return;
      onRead(url);
      setStatus({ error: false, message: 'อ่าน QR Code สำเร็จ เติมลิงก์ในช่องด้านบนแล้ว' });
    } catch (error) {
      if (!mounted.current || request.signal.aborted || isQrScanCancelled(error)) return;
      const details = getQrScanError(error);
      setStatus({ error: true, message: details.title + ' — ' + details.message });
    } finally {
      if (activeRequest.current === request) {
        activeRequest.current = null;
        if (mounted.current) { setBusy(null); onBusyChange?.(false); }
      }
    }
  }

  return <div className="qr-input-actions" aria-busy={!!busy}>
    <div className="qr-input-buttons">
      <button type="button" className="form-secondary-btn" disabled={disabled || !!busy}
        onClick={() => read('camera')}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" /><path d="M14 14h3v3h-3zM18 18h3v3h-3zM18 14h3M14 18v3" />
        </svg>
        {busy === 'camera' ? 'กำลังเปิดเครื่องสแกน…' : 'สแกน QR Code'}
      </button>
      <button type="button" className="form-secondary-btn" disabled={disabled || !!busy}
        onClick={() => input.current?.click()}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8" cy="8" r="1.5" />
          <path d="m21 15-5-5L5 21" />
        </svg>
        {busy === 'image' ? 'กำลังอ่านภาพ…' : 'แนบภาพ'}
      </button>
      <input ref={input} type="file" accept={QR_IMAGE_TYPES} hidden disabled={disabled || !!busy}
        aria-label="แนบภาพ QR Code" onChange={event => {
          const file = event.target.files?.[0];
          event.target.value = '';
          if (file) read('image', file);
        }} />
    </div>
    {status && <p className={status.error ? 'qr-input-error' : 'qr-input-success'}
      role={status.error ? 'alert' : 'status'}>{status.message}</p>}
  </div>;
}
