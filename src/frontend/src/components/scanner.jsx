import React, { useState, useEffect, useRef } from 'react';
import { banks } from '../utils/script';

const Scanner = ({ onNavigate, currentSubPage: externalSubPage }) => {
  const [currentSubPage, setCurrentSubPage] = useState(null);
  const [isBankDropdownOpen, setIsBankDropdownOpen] = useState(false);
  const [selectedBank, setSelectedBank] = useState(null);
  const [contentTab, setContentTab] = useState('link'); // 'link' or 'sms'
  const [personalTab, setPersonalTab] = useState('bank'); // 'bank' or 'phone'
  const bankDropdownRef = useRef(null);
  const linkTextareaRef = useRef(null);
  const smsTextareaRef = useRef(null);

  // --- Point A Refactor: State สำหรับจัดการ Input ทั้งหมด ---
  const [inputs, setInputs] = useState({
    link: '',
    sms: '',
    bank: '',
    phone: ''
  });

  // State สำหรับแสดงข้อความเตือนเมื่อพิมพ์ตัวอักษรในช่องตัวเลข
  const [inputWarnings, setInputWarnings] = useState({
    bank: false,
    phone: false
  });

  // Sync external subpage prop with internal state
  useEffect(() => {
    if (externalSubPage && externalSubPage !== 'scanner') {
      setCurrentSubPage(externalSubPage);
    } else if (externalSubPage === 'scanner') {
      setCurrentSubPage(null);
    }
  }, [externalSubPage]);

  const handleInputChange = (field, value) => {
    setInputs(prev => ({ ...prev, [field]: value }));
  };

  // Handler สำหรับ input ตัวเลขเท่านั้น พร้อมแสดง warning และจัดรูปแบบเบอร์โทร
  const handleNumericInput = (field, value) => {
    // ตรวจสอบว่ามีตัวอักษรที่ไม่ใช่ตัวเลขและเครื่องหมายขีดหรือไม่
    const hasInvalidChar = /[^\d-]/.test(value);
    // ดึงเฉพาะตัวเลขออกมา
    const numericOnly = value.replace(/\D/g, '');

    if (hasInvalidChar) {
      setInputWarnings(prev => ({ ...prev, [field]: true }));
    } else if (numericOnly.length > 0) {
      setInputWarnings(prev => ({ ...prev, [field]: false }));
    }

    let finalValue = numericOnly;

    // จัดรูปแบบสำหรับเบอร์โทรศัพท์ (0xx-xxx-xxxx)
    if (field === 'phone') {
      const limitedNumber = numericOnly.slice(0, 10); // จำกัด 10 หลัก
      if (limitedNumber.length > 6) {
        finalValue = `${limitedNumber.slice(0, 3)}-${limitedNumber.slice(3, 6)}-${limitedNumber.slice(6)}`;
      } else if (limitedNumber.length > 3) {
        finalValue = `${limitedNumber.slice(0, 3)}-${limitedNumber.slice(3)}`;
      } else {
        finalValue = limitedNumber;
      }
    }

    setInputs(prev => ({ ...prev, [field]: finalValue }));
  };

  const clearInput = (field) => {
    setInputs(prev => ({ ...prev, [field]: '' }));
    setInputWarnings(prev => ({ ...prev, [field]: false }));
  };
  // -----------------------------------------------------

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (bankDropdownRef.current && !bankDropdownRef.current.contains(event.target)) {
        setIsBankDropdownOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

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
    // If coming from scan-qr, go back to scan-image (mode selection)
    if (currentSubPage === 'scan-qr' && onNavigate) {
      onNavigate('scan-image');
      return;
    }

    setCurrentSubPage(null);
    // Clear all inputs when exiting subpages
    setInputs({ link: '', sms: '', bank: '', phone: '' });
    setInputWarnings({ bank: false, phone: false });
    setSelectedBank(null);
    // Also notify parent to update activeSection if needed
    if (onNavigate) {
      onNavigate('scanner');
    }
  };

  const openFeature = (feature) => {
    setCurrentSubPage(feature);
    // Notify parent to update activeSection for sidebar highlighting
    if (onNavigate) {
      onNavigate(feature);
    }
  };

  const checkLink = async () => {
    const url = inputs.link.trim();
    if (!url) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่ลิงก์', confirmButtonColor: '#3ACE00' });
      return;
    }
    window.Swal?.fire({ icon: 'info', title: 'กำลังตรวจสอบ...', text: url, confirmButtonColor: '#3ACE00' });
  };

  const checkSMS = async () => {
    const text = inputs.sms.trim();
    if (!text) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่ข้อความ', confirmButtonColor: '#3ACE00' });
      return;
    }
    window.Swal?.fire({ icon: 'info', title: 'กำลังวิเคราะห์...', text: text, confirmButtonColor: '#3ACE00' });
  };

  const scanCode = () => {
    window.Swal?.fire({
      icon: 'info',
      title: 'สแกน QR Code',
      text: 'ฟังก์ชันนี้ต้องใช้ LIFF SDK กรุณาเปิดผ่าน LINE App',
      confirmButtonColor: '#3ACE00'
    });
  };

  const checkBank = async () => {
    const accountNumber = inputs.bank.trim();
    if (!selectedBank) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาเลือกธนาคาร', confirmButtonColor: '#3ACE00' });
      return;
    }
    if (!accountNumber) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่เลขบัญชี', confirmButtonColor: '#3ACE00' });
      return;
    }
    window.Swal?.fire({
      icon: 'info',
      title: 'กำลังตรวจสอบ...',
      text: `ธนาคาร: ${selectedBank.name}\nเลขบัญชี: ${accountNumber}`,
      confirmButtonColor: '#3ACE00'
    });
  };

  const checkPhone = async () => {
    const phone = inputs.phone.trim();
    if (!phone) {
      window.Swal?.fire({ icon: 'warning', title: 'กรุณาใส่เบอร์โทร', confirmButtonColor: '#3ACE00' });
      return;
    }
    window.Swal?.fire({ icon: 'info', title: 'กำลังตรวจสอบ...', text: phone, confirmButtonColor: '#3ACE00' });
  };



  const handleContentTabChange = (tab) => {
    setContentTab(tab);
    setInputs(prev => ({ ...prev, link: '', sms: '' }));
  };

  const handlePersonalTabChange = (tab) => {
    setPersonalTab(tab);
    setInputs(prev => ({ ...prev, bank: '', phone: '' }));
    setInputWarnings(prev => ({ ...prev, bank: false, phone: false }));
    setIsBankDropdownOpen(false); // Close dropdown if open
  };

  // Sub-pages Logic
  if (currentSubPage === 'check-content') {
    return (
      <section id="check-content-page">
        <div className="section-content">
          <div className="scanner-subpage-header">
            <button className="back-btn-modern" onClick={goBack}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <div className="subpage-title-block">
              <div className="subpage-icon icon-link">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
              </div>
              <div>
                <h2>ตรวจสอบเนื้อหา</h2>
                <p className="subpage-subtitle">วิเคราะห์ลิงก์และข้อความ</p>
              </div>
            </div>
          </div>

          <div className="scanner-tabs-modern">
            <button className={`tab-modern ${contentTab === 'link' ? 'active' : ''}`} onClick={() => handleContentTabChange('link')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
              ลิงก์
            </button>
            <button className={`tab-modern ${contentTab === 'sms' ? 'active' : ''}`} onClick={() => handleContentTabChange('sms')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              ข้อความ
            </button>
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
                <button className="form-submit-btn" onClick={checkLink}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                  ตรวจสอบลิงก์
                </button>
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

  if (currentSubPage === 'scan-qr') {
    return (
      <section id="scan-qr-page">
        <div className="section-content">
          <div className="scanner-subpage-header">
            <button className="back-btn-modern" onClick={goBack}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <div className="subpage-title-block">
              <div className="subpage-icon" style={{ background: 'linear-gradient(135deg, #FFA726 0%, #FB8C00 100%)' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                  <circle cx="12" cy="13" r="4"></circle>
                </svg>
              </div>
              <div>
                <h2>ตรวจสอบรูปภาพ</h2>
                <p className="subpage-subtitle">ตรวจสอบ QR</p>
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
            <p className="qr-description">กดปุ่มด้านล่างเพื่อเปิดกล้องและสแกนรูปภาพ</p>
            <button className="form-submit-btn" onClick={scanCode}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                <circle cx="12" cy="13" r="4"></circle>
              </svg>
              เริ่มสแกนรูปภาพ
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (currentSubPage === 'check-personal') {
    return (
      <section id="check-personal-page">
        <div className="section-content">
          <div className="scanner-subpage-header">
            <button className="back-btn-modern" onClick={goBack}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <div className="subpage-title-block">
              <div className="subpage-icon icon-bank">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                  <line x1="1" y1="10" x2="23" y2="10"></line>
                </svg>
              </div>
              <div>
                <h2>ตรวจสอบข้อมูลส่วนตัว</h2>
                <p className="subpage-subtitle">ค้นหาบัญชีและเบอร์ใน Blacklist</p>
              </div>
            </div>
          </div>

          <div className="scanner-tabs-modern">
            <button className={`tab-modern ${personalTab === 'bank' ? 'active' : ''}`} onClick={() => handlePersonalTabChange('bank')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                <line x1="1" y1="10" x2="23" y2="10"></line>
              </svg>
              บัญชี
            </button>
            <button className={`tab-modern ${personalTab === 'phone' ? 'active' : ''}`} onClick={() => handlePersonalTabChange('phone')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
              </svg>
              เบอร์โทร
            </button>
          </div>

          <div className="scanner-form-card">
            {personalTab === 'bank' ? (
              <>
                <label className="form-label">เลือกธนาคาร</label>
                <div
                  className={`bank-select-wrapper ${isBankDropdownOpen ? 'active' : ''}`}
                  ref={bankDropdownRef}
                >
                  <div
                    className="selected-bank-box"
                    onClick={() => setIsBankDropdownOpen(!isBankDropdownOpen)}
                  >
                    <div className="bank-info">
                      {selectedBank ? (
                        <>
                          <img src={`/img/banks/${selectedBank.code}.png`} alt={selectedBank.name} className="bank-logo" />
                          <span>{selectedBank.name}</span>
                        </>
                      ) : (
                        <span className="placeholder-text">เลือกธนาคาร</span>
                      )}
                    </div>
                    <svg className="dropdown-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>

                  <div className="bank-options-list">
                    {banks.map((bank) => (
                      <div
                        key={bank.code}
                        className="bank-option-item"
                        onClick={() => {
                          setSelectedBank(bank);
                          setIsBankDropdownOpen(false);
                        }}
                      >
                        <img src={`/img/banks/${bank.code}.png`} alt={bank.name} className="bank-logo" />
                        <span>{bank.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <label className="form-label" style={{ marginTop: '20px' }}>ระบุเลขบัญชี</label>
                <div className="form-input-group">
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    className={`form-input ${inputWarnings.bank ? 'input-error' : ''}`}
                    placeholder="เลขบัญชี 10-12 หลัก"
                    value={inputs.bank}
                    onChange={(e) => handleNumericInput('bank', e.target.value)}
                  />
                  <button className="form-clear-btn" onClick={() => clearInput('bank')}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  </button>
                </div>
                {inputWarnings.bank && (
                  <p className="input-warning-text">กรุณากรอกเฉพาะตัวเลขเท่านั้น</p>
                )}
                <p className="form-hint">ตรวจสอบว่าเลขบัญชีอยู่ในรายชื่อมิจฉาชีพหรือไม่</p>
                <button className="form-submit-btn" onClick={checkBank}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                  ตรวจสอบบัญชี
                </button>
              </>
            ) : (
              <>
                <label className="form-label">ระบุเบอร์โทรศัพท์</label>
                <div className="form-input-group">
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    className={`form-input ${inputWarnings.phone ? 'input-error' : ''}`}
                    placeholder="09x-xxx-xxxx"
                    value={inputs.phone}
                    onChange={(e) => handleNumericInput('phone', e.target.value)}
                  />
                  <button className="form-clear-btn" onClick={() => clearInput('phone')}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  </button>
                </div>
                {inputWarnings.phone && (
                  <p className="input-warning-text">กรุณากรอกเฉพาะตัวเลขเท่านั้น</p>
                )}
                <p className="form-hint">ตรวจสอบว่าเบอร์นี้เป็น Call Center หลอกลวงหรือไม่</p>
                <button className="form-submit-btn" onClick={checkPhone}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                  ตรวจสอบเบอร์โทร
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
    <section id="scanner-page">
      <div className="section-content scanner-wide">
        <div className="scanner-header"><h2>My Scanner</h2></div>
        <div className="scanner-card-grid">
          {/* Card 1: Check Content */}
          <div className="scanner-package-card animate-card" style={{ animationDelay: '0.05s' }} onClick={() => openFeature('check-content')}>
            <div className="package-icon icon-link">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
            </div>
            <h3 className="package-title">ตรวจสอบเนื้อหา</h3>
            <p className="package-desc">วิเคราะห์ลิงก์และข้อความ</p>
            <ul className="package-features">
              <li className="feature-yes"><span className="check-icon">✓</span> ตรวจสอบลิงก์อันตราย</li>
              <li className="feature-yes"><span className="check-icon">✓</span> วิเคราะห์ข้อความ SMS</li>
              <li className="feature-yes"><span className="check-icon">✓</span> ตรวจจับ Phishing URL</li>
            </ul>
            <button className="package-btn">เลือกใช้งาน</button>
          </div>

          {/* Card 2: Check Personal */}
          <div className="scanner-package-card animate-card" style={{ animationDelay: '0.15s' }} onClick={() => openFeature('check-personal')}>
            <div className="package-icon icon-bank">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                <line x1="1" y1="10" x2="23" y2="10"></line>
              </svg>
            </div>
            <h3 className="package-title">ตรวจสอบข้อมูลส่วนตัว</h3>
            <p className="package-desc">ค้นหาบัญชีและเบอร์โทร Blacklist</p>
            <ul className="package-features">
              <li className="feature-yes"><span className="check-icon">✓</span> ตรวจสอบเลขบัญชีธนาคาร</li>
              <li className="feature-yes"><span className="check-icon">✓</span> ตรวจสอบเบอร์โทรศัพท์</li>
              <li className="feature-yes"><span className="check-icon">✓</span> ค้นหาจากฐานข้อมูล Blacklist</li>
            </ul>
            <button className="package-btn">เลือกใช้งาน</button>
          </div>

          {/* Card 3: Scan Image */}
          <div className="scanner-package-card animate-card" style={{ animationDelay: '0.25s' }} onClick={() => onNavigate('scan-image')}>
            <div className="package-icon icon-qrcode">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                <circle cx="12" cy="13" r="4"></circle>
              </svg>
            </div>
            <h3 className="package-title">ตรวจสอบรูปภาพ</h3>
            <p className="package-desc">สแกน QR Code และบัตรประชาชน</p>
            <ul className="package-features">
              <li className="feature-yes"><span className="check-icon">✓</span> สแกน QR Code</li>
              <li className="feature-yes"><span className="check-icon">✓</span> สแกนบัตรประชาชน</li>
              <li className="feature-yes"><span className="check-icon">✓</span> ตรวจสอบ Payment QR</li>
            </ul>
            <button className="package-btn">เลือกใช้งาน</button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Scanner;