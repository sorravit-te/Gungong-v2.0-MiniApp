import React, { useState } from 'react';

const HistoryCalendar = ({ historyItems, selectedDate, onDateSelect }) => {
  const [currentMonth, setCurrentMonth] = useState(new Date());

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay(); // 0 = Sunday

    return { daysInMonth, startingDay, year, month };
  };

  const getHistoryDates = () => {
    const dates = new Set();
    historyItems?.forEach(item => {
      if (item.created_at) {
        const date = new Date(item.created_at);
        dates.add(`${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`);
      }
    });
    return dates;
  };

  const { daysInMonth, startingDay, year, month } = getDaysInMonth(currentMonth);
  const historyDates = getHistoryDates();

  const monthNames = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
  ];

  const dayNames = ['อา', 'จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส'];

  const prevMonth = () => {
    setCurrentMonth(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentMonth(new Date(year, month + 1, 1));
  };

  const handleDateClick = (day) => {
    const clickedDate = new Date(year, month, day);
    if (selectedDate &&
        selectedDate.getFullYear() === year &&
        selectedDate.getMonth() === month &&
        selectedDate.getDate() === day) {
      onDateSelect(null); // Deselect
    } else {
      onDateSelect(clickedDate);
    }
  };

  const isToday = (day) => {
    const today = new Date();
    return today.getFullYear() === year &&
           today.getMonth() === month &&
           today.getDate() === day;
  };

  const isSelected = (day) => {
    return selectedDate &&
           selectedDate.getFullYear() === year &&
           selectedDate.getMonth() === month &&
           selectedDate.getDate() === day;
  };

  const hasHistory = (day) => {
    return historyDates.has(`${year}-${month}-${day}`);
  };

  const renderDays = () => {
    const days = [];

    // Empty cells for days before the first day of month
    for (let i = 0; i < startingDay; i++) {
      days.push(<div key={`empty-${i}`} className="calendar-day empty"></div>);
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const dayClasses = [
        'calendar-day',
        isToday(day) ? 'today' : '',
        isSelected(day) ? 'selected' : '',
        hasHistory(day) ? 'has-history' : ''
      ].filter(Boolean).join(' ');

      days.push(
        <div
          key={day}
          className={dayClasses}
          onClick={() => handleDateClick(day)}
        >
          <span className="day-number">{day}</span>
          {hasHistory(day) && <span className="history-dot"></span>}
        </div>
      );
    }

    return days;
  };

  return (
    <div className="history-calendar">
      <div className="calendar-header">
        <button className="calendar-nav-btn" onClick={prevMonth}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
        <span className="calendar-title">
          {monthNames[month]} {year + 543}
        </span>
        <button className="calendar-nav-btn" onClick={nextMonth}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <div className="calendar-weekdays">
        {dayNames.map((name, index) => (
          <div key={index} className="weekday-name">{name}</div>
        ))}
      </div>

      <div className="calendar-grid">
        {renderDays()}
      </div>

      {selectedDate && (
        <button className="clear-date-btn" onClick={() => onDateSelect(null)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
          ล้างการเลือก
        </button>
      )}
    </div>
  );
};

export default HistoryCalendar;
