import React from 'react';
import { callFraudCheckApi, getErrorMessage } from '../../shared/api/script';
import { scanCode as liffScanCode } from '../auth/liff';
import { getFraudResultPresentation } from '../../shared/results/fraudResultPresentation';

const GUNGONG_GREEN = '#3ACE00';

const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const renderResultRows = (rows, statusColor) => `
  <div style="text-align: left; font-size: 15px;">
    ${rows.map(([label, value], index) => `
      <p style="margin: 8px 0;${index === 0 ? ` color: ${statusColor}; font-weight: 700;` : ''}">
        <strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}
      </p>
    `).join('')}
  </div>
`;

const showLoadingDialog = () => {
  const swal = window.Swal;
  swal?.fire({
    title: 'กำลังวิเคราะห์ QR Code...',
    text: 'กรุณารอสักครู่',
    allowOutsideClick: false,
    allowEscapeKey: false,
    showConfirmButton: false,
    didOpen: () => swal.showLoading()
  });
};

const showFraudResult = (result) => {
  const presentation = getFraudResultPresentation(result);
  const { status, statusColor } = presentation;
  const rows = [['สถานะ', status]];

  if (result?.risk_level) rows.push(['ระดับความเสี่ยง', presentation.isIncomplete ? 'ยังประเมินไม่ได้' : result.risk_level]);
  if (result?.category) rows.push(['หมวดหมู่', result.category]);
  if (result?.reason_th && result.reason_th !== presentation.explanation) rows.push(['เหตุผล', result.reason_th]);
  if (presentation.explanation) rows.push([presentation.explanationLabel, presentation.explanation]);

  window.Swal?.fire({
    icon: presentation.icon,
    iconColor: statusColor,
    title: 'ผลการตรวจสอบ QR Code',
    html: renderResultRows(rows, statusColor),
    confirmButtonColor: statusColor,
    confirmButtonText: 'ตกลง'
  });
};

const isScanCancelled = (error) => {
  const errorText = `${error?.code || ''} ${error?.message || ''}`.toLowerCase();
  return errorText.includes('cancel');
};

const showScanError = (error) => {
  const errorDetails = error?.message === 'LIFF not available'
    ? {
        title: 'ไม่พบ LIFF',
        message: 'กรุณาเปิด GunGong ผ่านแอป LINE เพื่อใช้งานกล้องสแกน QR Code'
      }
    : getErrorMessage(error);

  window.Swal?.fire({
    icon: 'error',
    title: errorDetails.title,
    text: errorDetails.message || undefined,
    confirmButtonColor: GUNGONG_GREEN,
    confirmButtonText: 'ตกลง'
  });
};

const ScanImage = ({ onNavigate, backTarget = 'scanner' }) => {

  const handleQrScan = async () => {
    try {
      const scannedValue = (await liffScanCode())?.trim();
      if (!scannedValue) return;

      showLoadingDialog();
      const result = await callFraudCheckApi(scannedValue, 'qr');
      showFraudResult(result);
    } catch (error) {
      if (isScanCancelled(error)) return;
      showScanError(error);
    }
  };

  return (
    <section id="scan-image-page">
      <div className="section-content">
        <div className="scanner-subpage-header">
          <button className="back-btn-modern" onClick={() => onNavigate(backTarget)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
          <div className="subpage-title-block">
            <div className="subpage-icon icon-qrcode">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                <circle cx="12" cy="13" r="4"></circle>
              </svg>
            </div>
            <div>
              <h2>ตรวจสอบรูปภาพ</h2>
              <p className="subpage-subtitle">สแกน QR Code เพื่อตรวจสอบลิงก์</p>
            </div>
          </div>
        </div>

        <div className="scanner-form-card qr-card">
              <div className="qr-illustration">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="80" height="80">
                  <rect x="3" y="3" width="7" height="7"></rect>
                  <rect x="14" y="3" width="7" height="7"></rect>
                  <rect x="3" y="14" width="7" height="7"></rect>
                  <rect x="14" y="14" width="3" height="3"></rect>
                  <line x1="21" y1="14" x2="21" y2="21"></line>
                  <line x1="14" y1="21" x2="21" y2="21"></line>
                </svg>
              </div>
              <label className="form-label">สแกน QR Code</label>
              <p className="qr-description">สแกน QR Code, Payment QR และ URL เพื่อวิเคราะห์ความเสี่ยง</p>
              <p className="form-hint">เปิดผ่าน LINE เพื่อใช้งานกล้องสแกน QR Code</p>
              <button className="form-submit-btn" onClick={handleQrScan}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                  <circle cx="12" cy="13" r="4"></circle>
                </svg>
                เริ่มสแกน QR Code
              </button>
        </div>
      </div>
    </section>
  );
};

export default ScanImage;
