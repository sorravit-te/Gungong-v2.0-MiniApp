import React, { useState, useEffect, useRef } from 'react';
import {
  checkLink as apiCheckLink,
  checkSMS as apiCheckSMS,
  getErrorMessage
} from '../../shared/api/script';
import QrInputActions from '../../shared/qr/QrInputActions';
import { getFraudResultPresentation } from '../../shared/results/fraudResultPresentation';
import { resolveScannerSubPage } from './scannerNavigation';

const GUNGONG_GREEN = '#3ACE00';

const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const showLoadingDialog = (title, text) => {
  const swal = window.Swal;
  swal?.fire({
    title,
    text,
    allowOutsideClick: false,
    allowEscapeKey: false,
    showConfirmButton: false,
    didOpen: () => swal.showLoading()
  });
};

const showRequestError = (error) => {
  const { title, message } = getErrorMessage(error);
  window.Swal?.fire({
    icon: 'error',
    title,
    text: message || undefined,
    confirmButtonColor: GUNGONG_GREEN,
    confirmButtonText: 'ตกลง'
  });
};

const renderResultRows = (rows, statusColor) => `
  <div style="text-align: left; font-size: 15px;">
    ${rows.map(([label, value], index) => `
      <p style="margin: 8px 0;${index === 0 ? ` color: ${statusColor}; font-weight: 700;` : ''}">
        <strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}
      </p>
    `).join('')}
  </div>
`;

const showFraudResult = (result, subjectLabel) => {
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
    title: `ผลการตรวจสอบ${subjectLabel}`,
    html: renderResultRows(rows, statusColor),
    confirmButtonColor: statusColor,
    confirmButtonText: 'ตกลง'
  });
};

const Scanner = ({ onNavigate, currentSubPage: externalSubPage }) => {
  const [internalSubPage, setCurrentSubPage] = useState(null);
  const currentSubPage = externalSubPage === undefined
    ? internalSubPage : resolveScannerSubPage(externalSubPage);
  const contentTab = currentSubPage === 'check-sms' ? 'sms' : 'link';
  const [isQrScanning, setIsQrScanning] = useState(false);
  const linkTextareaRef = useRef(null);
  const smsTextareaRef = useRef(null);

  // --- Point A Refactor: State สำหรับจัดการ Input ทั้งหมด ---
  const [inputs, setInputs] = useState({
    link: '',
    sms: ''
  });

  const handleInputChange = (field, value) => {
    setInputs(prev => ({ ...prev, [field]: value }));
  };

  const clearInput = (field) => {
    setInputs(prev => ({ ...prev, [field]: '' }));
  };

  // Auto-resize textareas when values exist on mount
  useEffect(() => {
    const resizeTextarea = (ref) => {
      if (ref.current) {
        ref.current.style.height = 'auto';
        ref.current.style.height = Math.max(ref.current.scrollHeight, 100) + 'px';
      }
    };
    resizeTextarea(linkTextareaRef);
    resizeTextarea(smsTextareaRef);
  }, [inputs.link, inputs.sms, contentTab, currentSubPage]);

  const goBack = () => {
    setCurrentSubPage(null);
    // Clear all inputs when exiting subpages
    setInputs({ link: '', sms: '' });
    // Also notify parent to update activeSection if needed
    if (onNavigate) {
      onNavigate('scanner');
    }
  };

  const openFeature = (feature) => {
    const page = resolveScannerSubPage(feature);
    setCurrentSubPage(page);
    // Notify parent to update activeSection for sidebar highlighting
    if (onNavigate) {
      onNavigate(page || 'scanner');
    }
  };

  const checkLink = async () => {
    const url = inputs.link.trim();
    if (!url) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่ลิงก์', confirmButtonColor: GUNGONG_GREEN });
      return;
    }

    showLoadingDialog('กำลังตรวจสอบลิงก์...', url);
    try {
      const result = await apiCheckLink(url);
      showFraudResult(result, 'ลิงก์');
    } catch (error) {
      showRequestError(error);
    }
  };

  const checkSMS = async () => {
    const text = inputs.sms.trim();
    if (!text) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่ข้อความ', confirmButtonColor: GUNGONG_GREEN });
      return;
    }

    showLoadingDialog('กำลังวิเคราะห์ข้อความ...', text);
    try {
      const result = await apiCheckSMS(text);
      showFraudResult(result, 'ข้อความ');
    } catch (error) {
      showRequestError(error);
    }
  };

  // Sub-pages Logic
  if (currentSubPage === 'check-link' || currentSubPage === 'check-sms') {
    return (
      <section id="check-content-page" key={currentSubPage}>
        <div className="section-content">
          <div className="scanner-subpage-header">
            <button className="back-btn-modern" onClick={goBack}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <div className="subpage-title-block">
              <div className="scanner-feature-mascot scanner-subpage-mascot" aria-hidden="true">
                <img src={contentTab === 'link' ? '/img/mascot_02.png' : '/img/mascot_03.png'} alt="" width="48" height="48" />
              </div>
              <div>
                <h2>{contentTab === 'link' ? 'ตรวจสอบลิงก์ / QR Code' : 'ตรวจสอบข้อความ'}</h2>
                <p className="subpage-subtitle">{contentTab === 'link' ? 'วิเคราะห์ลิงก์และ URL จาก QR Code' : 'วิเคราะห์ข้อความที่น่าสงสัย'}</p>
              </div>
            </div>
          </div>

          <div className="scanner-form-card">
            {contentTab === 'link' ? (
              <>
                <label className="form-label">ใส่ลิงก์ที่ต้องการตรวจสอบ</label>
                <div className="form-input-group">
                  <textarea
                    ref={linkTextareaRef}
                    key={`link-textarea-${contentTab}`}
                    className="form-input form-textarea"
                    placeholder="https://bit.ly/example"
                    value={inputs.link}
                    onChange={(e) => handleInputChange('link', e.target.value)}
                    rows={4}
                    style={{ resize: 'none', overflow: 'hidden' }}
                    onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.max(e.target.scrollHeight, 100) + 'px'; }}
                  />
                  <button className="form-clear-btn" onClick={() => clearInput('link')}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  </button>
                </div>
                <p className="form-hint">ระบบจะวิเคราะห์ลิงก์ว่าเป็นอันตรายหรือไม่</p>
                <button className="form-submit-btn" onClick={checkLink} disabled={isQrScanning}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                  ตรวจสอบลิงก์
                </button>
                <div className="qr-option-divider" aria-hidden="true">
                  <span>หรือ</span>
                </div>
                <QrInputActions resetKey={currentSubPage + ':' + inputs.link}
                  onRead={url => handleInputChange('link', url)} onBusyChange={setIsQrScanning} />
                <p className="form-hint qr-option-hint">QR Code ต้องมี URL และจะยังไม่ถูกตรวจสอบจนกว่าคุณจะกดปุ่มด้านบน</p>
              </>
            ) : (
              <>
                <label className="form-label">ใส่ข้อความที่ต้องการตรวจสอบ</label>
                <div className="form-input-group">
                  <textarea
                    ref={smsTextareaRef}
                    key={`sms-textarea-${contentTab}`}
                    className="form-input form-textarea"
                    placeholder="วางข้อความที่ได้รับ..."
                    value={inputs.sms}
                    onChange={(e) => handleInputChange('sms', e.target.value)}
                    rows={4}
                    style={{ resize: 'none', overflow: 'hidden' }}
                    onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.max(e.target.scrollHeight, 100) + 'px'; }}
                  />
                  <button className="form-clear-btn" onClick={() => clearInput('sms')}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  </button>
                </div>
                <p className="form-hint">AI จะวิเคราะห์ว่าข้อความนี้เป็น Scam หรือไม่</p>
                <button className="form-submit-btn" onClick={checkSMS}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                  ตรวจสอบข้อความ
                </button>
              </>
            )}
          </div>
        </div>
      </section>
    );
  }

  // Main Menu
  return (
    <section id="scanner-page" key="scanner">
      <div className="section-content scanner-landing">
        <div className="scanner-intro-card">
          <div className="scanner-intro-copy">
            <span className="scanner-intro-label">GUNGONG SCANNER</span>
            <h3>เช็กลิงก์และข้อความ</h3>
            <p>เช็กลิงก์และข้อความที่น่าสงสัย<br />ก่อนคลิก แชร์ หรือให้ข้อมูลส่วนตัว</p>
          </div>
          <div className="scanner-intro-art" aria-hidden="true">
            <img className="scanner-intro-mascot" src="/img/mascot_01.png" alt="" width="128" height="128" />
          </div>
        </div>

        <div className="scanner-menu-heading">
          <h3>ตรวจสอบเนื้อหา</h3>
          <p>เลือกสิ่งที่คุณต้องการตรวจสอบ</p>
        </div>
        <div className="scanner-feature-list">
          <button type="button" className="scanner-feature-card animate-card" style={{ animationDelay: '0.05s' }} onClick={() => openFeature('check-link')}>
            <span className="scanner-feature-mascot" aria-hidden="true">
              <img src="/img/mascot_02.png" alt="" width="56" height="56" />
            </span>
            <span className="scanner-feature-copy">
              <span className="scanner-feature-title">ตรวจสอบลิงก์ / QR Code</span>
              <span className="scanner-feature-description">วิเคราะห์ลิงก์หรือ URL จาก QR Code</span>
            </span>
            <svg className="scanner-feature-arrow" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>

          <button type="button" className="scanner-feature-card animate-card" style={{ animationDelay: '0.15s' }} onClick={() => openFeature('check-sms')}>
            <span className="scanner-feature-mascot" aria-hidden="true">
              <img src="/img/mascot_03.png" alt="" width="56" height="56" />
            </span>
            <span className="scanner-feature-copy">
              <span className="scanner-feature-title">ตรวจสอบข้อความ</span>
              <span className="scanner-feature-description">วิเคราะห์ข้อความ SMS หรือแชตที่น่าสงสัย</span>
            </span>
            <svg className="scanner-feature-arrow" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
};

export default Scanner;
