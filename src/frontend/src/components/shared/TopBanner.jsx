import React from 'react';
import { useAuth } from '../../contexts/AuthContext';

const TopBanner = ({ userProfile, isDarkMode, onToggleDarkMode }) => {
  const { user } = useAuth();
  const handleLineOAClick = (e) => {
    e.preventDefault();
    if (window.Swal) {
      window.Swal.fire({
        title: 'เพิ่มเพื่อน LINE OA',
        text: 'คุณต้องการเพิ่มเพื่อน GunGong Official หรือไม่?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#3ACE00',
        confirmButtonText: 'ไปหน้า LINE OA',
        cancelButtonText: 'ยกเลิก',
        background: '#fff',
        borderRadius: '20px',
      }).then((result) => {
        if (result.isConfirmed) {
          window.open('https://line.me/R/ti/p/@357asclq', '_blank');
        }
      });
    } else {
      window.open('https://line.me/R/ti/p/@357asclq', '_blank');
    }
  };

  return (
    <div className="top-banner">
      <img src="/img/mountain.png" alt="ภาพแบนเนอร์" />
      <div className="miniapp-gungong">Gun Gong</div>

      <div className="user-info">
        <div className="avatar-container">
          {/* LINE profile with an anonymous avatar fallback. */}
          {(user?.photoURL || userProfile?.pictureUrl) ? (
            <img
              className="avatar"
              src={user?.photoURL || userProfile?.pictureUrl}
              alt="avatar"
            />
          ) : (
            <div className="avatar-svg">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
              </svg>
            </div>
          )}
        </div>
        <div className="text-group">
          <div className="user-name">{user?.displayName || userProfile?.displayName || '(Username)'}</div>
          <div className="username-id">
            {`User ID: ${userProfile?.userId?.slice(0, 10) || '...'}`}
          </div>
        </div>
      </div>

      <div className="header-actions">
        {/* Dark Mode Toggle */}
        <div className="theme-toggle" onClick={onToggleDarkMode}>
          <div className={`toggle-track ${isDarkMode ? 'dark' : 'light'}`}>
            <div className="toggle-icons">
              <svg className="sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
              </svg>
              <svg className="moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
            </div>
            <div className="toggle-thumb"></div>
          </div>
        </div>

        <a href="#" onClick={handleLineOAClick} className="action-btn line-oa-header-btn">
          <img src="/img/logo.png" alt="LINE" />
        </a>
      </div>
    </div>
  );
};

export default TopBanner;
