import React from 'react';

const ScanImage = ({ onNavigate }) => {
  return (
    <section id="scan-image-page">
      <div className="section-content">
        {/* Header */}
        <div className="scanner-subpage-header">
          <button className="back-btn-modern" onClick={() => onNavigate('scanner')}>
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
              <p className="subpage-subtitle">เลือกประเภทที่ต้องการสแกน</p>
            </div>
          </div>
        </div>

        <div className="scanner-form-card">
          {/* QR Code Scan Option */}
          <div
            className="scan-mode-card"
            onClick={() => onNavigate('scan-qr')}
            style={{
              padding: '20px',
              marginBottom: '15px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '12px',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
              boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-5px)';
              e.currentTarget.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.3)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{
                width: '60px',
                height: '60px',
                background: 'rgba(255, 255, 255, 0.2)',
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" style={{ width: '35px', height: '35px' }}>
                  <rect x="3" y="3" width="7" height="7"></rect>
                  <rect x="14" y="3" width="7" height="7"></rect>
                  <rect x="14" y="14" width="7" height="7"></rect>
                  <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: '0 0 5px 0', color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                  สแกน QR Code
                </h3>
                <p style={{ margin: 0, color: 'rgba(255, 255, 255, 0.9)', fontSize: '14px' }}>
                  สแกน QR Code, Payment QR และ URL
                </p>
              </div>
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" style={{ width: '24px', height: '24px' }}>
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>
          </div>

          {/* ID Card Scan Option */}
          <div
            className="scan-mode-card"
            onClick={() => onNavigate('id-card-scanner')}
            style={{
              padding: '20px',
              marginBottom: '15px',
              background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
              borderRadius: '12px',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
              boxShadow: '0 4px 15px rgba(240, 147, 251, 0.3)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-5px)';
              e.currentTarget.style.boxShadow = '0 8px 25px rgba(240, 147, 251, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 15px rgba(240, 147, 251, 0.3)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{
                width: '60px',
                height: '60px',
                background: 'rgba(255, 255, 255, 0.2)',
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" style={{ width: '35px', height: '35px' }}>
                  <rect x="3" y="4" width="18" height="16" rx="2" ry="2"></rect>
                  <line x1="7" y1="8" x2="7.01" y2="8"></line>
                  <line x1="7" y1="12" x2="17" y2="12"></line>
                  <line x1="7" y1="16" x2="17" y2="16"></line>
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: '0 0 5px 0', color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                  สแกนบัตรประชาชน
                </h3>
                <p style={{ margin: 0, color: 'rgba(255, 255, 255, 0.9)', fontSize: '14px' }}>
                  ตรวจสอบบัตรประชาชนจาก Blacklist
                </p>
              </div>
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" style={{ width: '24px', height: '24px' }}>
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>
          </div>

          {/* Info Box */}
          <div style={{
            padding: '15px',
            background: '#F0F8FF',
            borderRadius: '8px',
            marginTop: '20px'
          }}>
            <p style={{ margin: 0, fontSize: '14px', color: '#2196F3' }}>
              💡 <strong>คำแนะนำ:</strong> เลือกโหมดที่ต้องการก่อนเปิดกล้องสแกน
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ScanImage;
