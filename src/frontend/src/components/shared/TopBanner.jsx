import React from 'react';
import { useAuth } from '../../contexts/AuthContext';

const TopBanner = ({ userProfile, onShare, isDarkMode, onToggleDarkMode }) => {
  const { user, signInWithGoogle, signOut, isAuthenticated, loading } = useAuth();
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
          {/* ใช้รูปจาก Firebase (Google) ก่อน, ถ้าไม่มีใช้จาก LIFF, ถ้าไม่มีใช้ SVG */}
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
          {/* ใช้ชื่อจาก Firebase ก่อน, ถ้าไม่มีใช้จาก LIFF */}
          <div className="user-name">{user?.displayName || userProfile?.displayName || '(Username)'}</div>
          <div className="username-id">
            {user?.email ? user.email : `User ID: ${userProfile?.userId?.slice(0, 10) || '...'}`}
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

        <button className="action-btn" onClick={onShare}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
            <polyline points="16 6 12 2 8 6"></polyline>
            <line x1="12" y1="2" x2="12" y2="15"></line>
          </svg>
        </button>

        <a href="#" onClick={handleLineOAClick} className="action-btn line-oa-header-btn">
          <img src="/img/logo.png" alt="LINE" />
        </a>
      </div>
    </div>
  );
};

export default TopBanner;
