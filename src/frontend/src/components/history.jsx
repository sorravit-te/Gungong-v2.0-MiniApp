import React, { useState, useEffect } from 'react';
import { loadHistory, formatTime, getTypeName } from '../utils/script';
import HistoryCalendar from './shared/HistoryCalendar';

const History = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);

  // Sample history data (will be replaced by API data)
  const sampleHistoryItems = [
    {
      id: '1',
      type: 'link',
      message_text: 'https://bit.ly/scam123',
      is_safe: false,
      is_fraud: true,
      created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: '2',
      type: 'phone',
      phone_number: '091-234-5678',
      message_text: '091-234-5678',
      is_safe: true,
      is_fraud: false,
      created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: '3',
      type: 'bank',
      account_number: 'xxx-x-xxxxx-x',
      message_text: 'xxx-x-xxxxx-x (KBANK)',
      is_safe: false,
      is_fraud: true,
      created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: '4',
      type: 'sms',
      message_text: 'คุณได้รับเงินคืนภาษี กรุณากดลิงก์...',
      is_safe: false,
      is_fraud: true,
      created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: '5',
      type: 'link',
      message_text: 'https://kbank.co.th',
      is_safe: true,
      is_fraud: false,
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ];

  useEffect(() => {
    // Use sample data for now
    setHistoryData(sampleHistoryItems);
  }, []);

  const getTypeIcon = (type) => {
    switch (type) {
      case 'link':
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
          </svg>
        );
      case 'phone':
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
          </svg>
        );
      case 'bank':
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
            <line x1="1" y1="10" x2="23" y2="10"></line>
          </svg>
        );
      case 'sms':
      case 'text':
      case 'message':
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        );
      case 'qr':
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
            <circle cx="12" cy="13" r="4"></circle>
          </svg>
        );
      default:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
          </svg>
        );
    }
  };

  const getTimeString = (dateString) => {
    if (!dateString) return '';
    const dateObj = new Date(dateString);
    return dateObj.toLocaleTimeString('th-TH', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getTypeLabelName = (type) => {
    const names = {
      link: 'Link',
      message: 'Message',
      text: 'Text',
      sms: 'SMS',
      qr: 'QrCode',
      bank: 'Bank',
      phone: 'Phone',
    };
    return names[type] || 'Unknown';
  };

  const handleCardClick = (item) => {
    const isSafe = item.is_safe;
    window.Swal?.fire({
      title: isSafe ? 'ปลอดภัย ✅' : 'อันตราย! ⚠️',
      html: `
        <div style="text-align: left; font-size: 14px;">
          <p><b>ข้อความ:</b> ${item.message_text || item.account_number || item.phone_number || 'No content'}</p>
          <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
          <p><b>ประเภท:</b> ${getTypeLabelName(item.type)}</p>
          ${item.confidence_score ? `<p><b>ความมั่นใจ:</b> ${item.confidence_score}%</p>` : ''}
          ${item.reason ? `<p><b>เหตุผล:</b> ${item.reason}</p>` : ''}
        </div>
      `,
      icon: isSafe ? 'success' : 'warning',
      confirmButtonColor: isSafe ? '#3ACE00' : '#FF5C5C',
      confirmButtonText: 'ปิด',
      showCloseButton: true,
    });
  };

  const handleReport = (e, item) => {
    e.stopPropagation();
    window.Swal?.fire({
      title: 'ต้องการรายงานผล?',
      text: 'หากผลการตรวจสอบไม่ถูกต้อง แจ้งเราได้เลย',
      icon: 'question',
      showDenyButton: true,
      showCancelButton: true,
      showConfirmButton: false,
      denyButtonText: 'รายงาน',
      cancelButtonText: 'ยกเลิก',
      denyButtonColor: '#FF453A',
    }).then((result) => {
      if (result.isDenied) {
        window.Swal?.fire({
          title: 'ขอทราบข้อมูลเพิ่มเติม',
          input: 'text',
          inputLabel: 'ทำไมถึงคิดว่าไม่ถูกต้อง?',
          inputPlaceholder: 'เช่น ข้อมูลนี้ถูกต้อง',
          showCancelButton: true,
          confirmButtonText: 'ยืนยัน',
          cancelButtonText: 'ยกเลิก',
          confirmButtonColor: '#3ACE00',
        }).then((inputResult) => {
          if (inputResult.isConfirmed) {
            window.Swal?.fire({
              icon: 'success',
              title: 'ขอบคุณสำหรับข้อมูล',
              text: 'เราได้รับรายงานของคุณแล้ว',
              timer: 1500,
              showConfirmButton: false,
            });
          }
        });
      }
    });
  };

  const openTypeFilterModal = () => {
    window.Swal?.fire({
      icon: 'info',
      title: 'ตัวกรองประเภท',
      text: 'ฟังก์ชันกำลังพัฒนา',
      confirmButtonColor: '#3ACE00',
    });
  };

  const openDateFilterModal = () => {
    window.Swal?.fire({
      icon: 'info',
      title: 'เรียงตามวันที่',
      text: 'ฟังก์ชันกำลังพัฒนา',
      confirmButtonColor: '#3ACE00',
    });
  };

  const filteredItems = historyData.filter(item => {
    const text = item.message_text || item.account_number || item.phone_number || '';
    const matchesSearch = text.toLowerCase().includes(searchQuery.toLowerCase());

    // Date filtering
    if (selectedDate) {
      const itemDate = new Date(item.created_at);
      const matchesDate = itemDate.getFullYear() === selectedDate.getFullYear() &&
                         itemDate.getMonth() === selectedDate.getMonth() &&
                         itemDate.getDate() === selectedDate.getDate();
      return matchesSearch && matchesDate;
    }
    return matchesSearch;
  });

  const displayedItems = expanded ? filteredItems : filteredItems.slice(0, 3);

  return (
    <section id="history-page">
      <div className="section-content">
        <div className="scanner-header">
          <h2>My History</h2>
        </div>

        <div className="history-layout">
          {/* Calendar Sidebar */}
          <div className="history-calendar-sidebar">
            <HistoryCalendar
              historyItems={historyData}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
            />
          </div>

          {/* History Content */}
          <div className="history-main-content">

        <div className="history-controls animate-card" style={{ animationDelay: '0.05s' }}>
          <div className="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="Search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button className="filter-btn" onClick={openTypeFilterModal}>
            <div id="filter-dot" className="active-dot"></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
          </button>
          <button className="sort-btn" onClick={openDateFilterModal}>
            <div id="sort-dot" className="active-dot"></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 3 21 3 21 8"></polyline>
              <line x1="4" y1="20" x2="21" y2="3"></line>
              <polyline points="21 16 21 21 16 21"></polyline>
              <line x1="15" y1="15" x2="21" y2="21"></line>
              <line x1="4" y1="4" x2="9" y2="9"></line>
            </svg>
          </button>
        </div>

        <div className="history-list">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#aaa' }}>
              กำลังโหลดข้อมูล...
            </div>
          ) : displayedItems.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
              ไม่พบประวัติการตรวจสอบ
            </div>
          ) : (
            displayedItems.map((item, index) => {
              const isSafe = item.is_safe;
              const isFraud = item.is_fraud;
              const statusClass = isSafe ? 'safe' : 'dangerous';
              const iconClass = isFraud ? 'icon-dangerous' : (isSafe ? 'icon-safe' : 'icon-unknown');
              const timeStr = getTimeString(item.created_at);
              const displayText = item.message_text || item.account_number || item.phone_number || 'No content';
              const animDelay = `${0.05 + index * 0.08}s`;

              return (
                <div
                  key={item.id}
                  className={`history-card ${statusClass} animate-card`}
                  style={{ animationDelay: animDelay }}
                  onClick={() => handleCardClick(item)}
                >
                  <div className="card-left-line"></div>
                  <div className="card-date-block">
                    <span className="date-day">{new Date(item.created_at).getDate()}</span>
                    <span className="date-month">{new Date(item.created_at).toLocaleString('th-TH', { month: 'short' })}</span>
                    <span className="date-time">{new Date(item.created_at).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <div className="h-card-content">
                    <div className="h-card-top">
                      <span className="type-label">Type : {getTypeLabelName(item.type)}</span>
                    </div>
                    <div className="h-card-main">
                      <div className={`h-icon ${iconClass}`}>
                        {getTypeIcon(item.type)}
                      </div>
                      <span className="main-text">{displayText}</span>
                    </div>
                    <div className="h-card-bottom">
                      {isSafe ? (
                        <div className="status-badge badge-safe">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                          SAFE
                        </div>
                      ) : (
                        <div className="status-badge badge-dangerous">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                          </svg>
                          DANGEROUS
                        </div>
                      )}
                      <button className="feedback-btn" onClick={(e) => handleReport(e, item)}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="8" x2="12" y2="12"></line>
                          <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        Report
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {filteredItems.length > 3 && !expanded && (
          <div className="see-more-container animate-card" style={{ animationDelay: '0.4s' }} id="history-see-more">
            <button className="see-more-btn" onClick={() => setExpanded(true)}>
              ดูทั้งหมด
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
          </div>
        )}
          </div>
          {/* End history-main-content */}
        </div>
        {/* End history-layout */}
      </div>
    </section>
  );
};

export default History;
