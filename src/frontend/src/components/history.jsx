import React, { useState, useEffect, useRef } from 'react';
import { getHistoryById, formatTime, getTypeName } from '../utils/script';
import HistoryCalendar from './shared/HistoryCalendar';
import { getHistoryResultPresentation } from '../utils/fraudResultPresentation';
import { createHistoryDetailController } from '../utils/historyDetail';
import { useHistoryEntries } from '../hooks/useHistoryEntries';
import { HISTORY_TYPES, parseHistoryDate, selectHistoryItems } from '../utils/historyView';

const History = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expanded, setExpanded] = useState(false);
  const { entries: historyData, loading, error: loadError } = useHistoryEntries();
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [selectedOutcome, setSelectedOutcome] = useState('all');
  const [sortOrder, setSortOrder] = useState('newest');
  const [controlPanel, setControlPanel] = useState(null);
  const toolbar = useRef(null);
  const optionsPanel = useRef(null);
  const detailController = useRef(null);

  const closePanel = () => {
    toolbar.current?.querySelector(`[aria-controls="history-${controlPanel}-panel"]`)?.focus({ preventScroll: true });
    setControlPanel(null);
  };

  useEffect(() => {
    if (!controlPanel) return;
    optionsPanel.current?.querySelector('input, select')?.focus({ preventScroll: true });
    const outside = event => {
      if (!toolbar.current?.contains(event.target)) setControlPanel(null);
    };
    const escape = event => {
      if (event.key !== 'Escape') return;
      toolbar.current?.querySelector(`[aria-controls="history-${controlPanel}-panel"]`)?.focus({ preventScroll: true });
      setControlPanel(null);
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [controlPanel]);

  useEffect(() => {
    return () => {
      detailController.current?.dispose();
      detailController.current = null;
    };
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
    return parseHistoryDate(dateString) ? formatTime(dateString) : '--:--';
  };

  const handleCardClick = (item) => {
    if (!window.Swal) return;
    detailController.current ??= createHistoryDetailController({
      getDetail: getHistoryById, swal: window.Swal, typeName: getTypeName,
    });
    void detailController.current.open(item);
  };

  const handleReport = (e) => {
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

  const filteredItems = selectHistoryItems(historyData, {
    search: searchQuery, types: selectedTypes, outcome: selectedOutcome,
    date: selectedDate, sort: sortOrder,
  });
  const hasFilters = selectedTypes.length > 0 || selectedOutcome !== 'all' || selectedDate !== null;
  const selectDate = date => { setSelectedDate(date); setExpanded(false); };

  const displayedItems = expanded ? filteredItems : filteredItems.slice(0, 3);
  const calendarHistoryItems = historyData.filter(item => parseHistoryDate(item.created_at));

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
              historyItems={calendarHistoryItems}
              selectedDate={selectedDate}
              onDateSelect={selectDate}
            />
          </div>

          {/* History Content */}
          <div className="history-main-content">

        <div className="history-toolbar" ref={toolbar}>
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
              onChange={(e) => { setSearchQuery(e.target.value); setExpanded(false); }}
            />
          </div>
          <button className="filter-btn" aria-label="กรองประวัติ" aria-haspopup="dialog" aria-expanded={controlPanel === 'filter'} aria-controls="history-filter-panel"
            onClick={() => setControlPanel(controlPanel === 'filter' ? null : 'filter')}>
            <div className="active-dot" style={{ display: hasFilters ? 'block' : 'none' }}></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
          </button>
          <button className="sort-btn" aria-label="เรียงตามวันที่" aria-haspopup="dialog" aria-expanded={controlPanel === 'sort'} aria-controls="history-sort-panel"
            onClick={() => setControlPanel(controlPanel === 'sort' ? null : 'sort')}>
            <div className="active-dot" style={{ display: sortOrder === 'oldest' ? 'block' : 'none' }}></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 3 21 3 21 8"></polyline>
              <line x1="4" y1="20" x2="21" y2="3"></line>
              <polyline points="21 16 21 21 16 21"></polyline>
              <line x1="15" y1="15" x2="21" y2="21"></line>
              <line x1="4" y1="4" x2="9" y2="9"></line>
            </svg>
          </button>
        </div>

        {controlPanel === 'filter' && <div id="history-filter-panel" className="history-options-panel" ref={optionsPanel}
          role="dialog" aria-label="กรองประวัติ">
          <div className="history-options-header"><strong>กรองประวัติ</strong>
            <button type="button" aria-label="ปิดตัวกรอง" onClick={closePanel}>×</button>
          </div>
          <fieldset>
            <legend>ประเภทการตรวจสอบ (ไม่เลือก = ทุกประเภท)</legend>
            <div className="history-type-options">
              {HISTORY_TYPES.map(type => <label key={type.value}>
                <input type="checkbox" checked={selectedTypes.includes(type.value)} onChange={() => {
                  setSelectedTypes(previous => previous.includes(type.value)
                    ? previous.filter(value => value !== type.value) : [...previous, type.value]);
                  setExpanded(false);
                }} />{type.label}
              </label>)}
            </div>
          </fieldset>
          <label className="history-option-label">ผลการตรวจสอบ
            <select value={selectedOutcome} onChange={event => { setSelectedOutcome(event.target.value); setExpanded(false); }}>
              <option value="all">ทุกผลการตรวจสอบ</option>
              <option value="safe">ไม่พบสัญญาณอันตราย</option>
              <option value="risk">พบความเสี่ยง</option>
              <option value="unknown">ยังสรุปไม่ได้</option>
              <option value="invalid">ข้อมูลไม่ถูกต้อง / ไม่อนุญาต</option>
            </select>
          </label>
          <button className="clear-date-btn" onClick={() => {
            setSelectedTypes([]); setSelectedOutcome('all'); setSelectedDate(null); setSearchQuery(''); setExpanded(false);
          }}>ล้างตัวกรองทั้งหมด</button>
        </div>}
        {controlPanel === 'sort' && <div id="history-sort-panel" className="history-options-panel" ref={optionsPanel}
          role="dialog" aria-label="เรียงตามวันที่">
          <div className="history-options-header"><strong>เรียงตามวันที่</strong>
            <button type="button" aria-label="ปิดการเรียงตามวันที่" onClick={closePanel}>×</button>
          </div>
          <label className="history-option-label">เรียงตามวันที่
            <select value={sortOrder} onChange={event => { setSortOrder(event.target.value); setExpanded(false); }}>
              <option value="newest">ใหม่ที่สุดก่อน</option>
              <option value="oldest">เก่าที่สุดก่อน</option>
            </select>
          </label>
        </div>}
        </div>
        {!loading && !loadError && <p className="history-result-count">
          {filteredItems.length} รายการ{hasFilters || searchQuery ? 'ที่ตรงกับตัวกรอง' : ''} · จากประวัติล่าสุดสูงสุด 50 รายการ · {sortOrder === 'newest' ? 'ใหม่ที่สุดก่อน' : 'เก่าที่สุดก่อน'}
        </p>}

        <div className="history-list">
          {loadError && <div role="alert" className="history-load-message" style={{ textAlign: 'center', padding: '20px' }}>
            {loadError}
          </div>}
          {loading ? (
            <div role="status" className="page-loading">
              กำลังโหลดข้อมูล...
            </div>
          ) : displayedItems.length === 0 ? (
            !loadError && <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
              ไม่พบประวัติการตรวจสอบ
            </div>
          ) : (
            displayedItems.map((item, index) => {
              const presentation = getHistoryResultPresentation(item);
              const isSafe = presentation.isSafe;
              const isFraud = presentation.isRisk;
              const statusClass = isSafe ? 'safe' : isFraud ? 'dangerous' : 'unknown';
              const iconClass = isFraud ? 'icon-dangerous' : (isSafe ? 'icon-safe' : 'icon-unknown');
              const itemDate = parseHistoryDate(item.created_at);
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
                    <span className="date-day">{itemDate ? itemDate.getDate() : '--'}</span>
                    <span className="date-month">{itemDate ? itemDate.toLocaleString('th-TH', { month: 'short' }) : 'ไม่ทราบ'}</span>
                    <span className="date-time">{timeStr}</span>
                  </div>
                  <div className="h-card-content">
                    <div className="h-card-top">
                      <span className="type-label">Type : {getTypeName(item.type)}</span>
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
                          {item.type === 'link' || item.type === 'qr' ? 'ไม่พบสัญญาณอันตราย' : 'SAFE'}
                        </div>
                      ) : (
                        <div className={`status-badge ${isFraud ? 'badge-dangerous' : 'badge-unknown'}`}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                          </svg>
                          {presentation.isInvalid ? 'ข้อมูลไม่ถูกต้อง / ไม่อนุญาต' : isFraud ? 'มีความเสี่ยง' : 'ยังสรุปไม่ได้'}
                        </div>
                      )}
                      <button className="feedback-btn" onClick={handleReport}>
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
