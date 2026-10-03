import React, { useRef, useState } from 'react';
import { useAuth } from '../../features/auth/AuthContext';
import { createLineFriendshipAction, LINE_OA_URL } from '../../features/auth/lineFriendship';

const lineOAPopup = {
  imageUrl: '/img/logo.png',
  imageWidth: 120,
  imageHeight: 120,
  imageAlt: 'GunGong',
  customClass: { popup: 'line-oa-popup' },
  confirmButtonColor: '#1de165',
  cancelButtonColor: '#e5e7eb',
  background: '#fff',
  borderRadius: '20px',
};

async function confirmLineOAFallback({ reason }) {
  const text = reason === 'failed'
    ? 'เปิดหน้าต่างเพิ่มเพื่อนใน LINE ไม่สำเร็จ ต้องการไปหน้า GunGong Official แทนหรือไม่?'
    : 'คุณต้องการเพิ่มเพื่อน GunGong Official หรือไม่?';
  if (window.Swal) {
    await window.Swal.fire({
      ...lineOAPopup,
      title: 'เพิ่มเพื่อน LINE OA',
      text,
      showCancelButton: true,
      confirmButtonText: 'ไปหน้า LINE OA',
      cancelButtonText: 'ยกเลิก',
      // Open on the confirm-button gesture, not after an awaited network call.
      preConfirm: () => { window.open(LINE_OA_URL, '_blank', 'noopener,noreferrer'); },
    });
  } else if (window.confirm(text)) {
    window.open(LINE_OA_URL, '_blank', 'noopener,noreferrer');
  }
}

const TopBanner = ({ userProfile, isDarkMode, onToggleDarkMode }) => {
  const { user, lineLoading } = useAuth();
  const [friendshipBusy, setFriendshipBusy] = useState(false);
  const friendshipAction = useRef(null);
  const handleLineOAClick = async (e) => {
    e.preventDefault();
    if (!friendshipAction.current) {
      friendshipAction.current = createLineFriendshipAction({
        fallback: confirmLineOAFallback,
        onBusy: setFriendshipBusy,
        onResult: async ({ friendFlag }) => {
          if (friendFlag === true && window.Swal) {
            await window.Swal.fire({
              ...lineOAPopup,
              title: 'GunGong Official',
              text: 'คุณเป็นเพื่อนกับ GunGong Official แล้ว',
              confirmButtonText: 'ตกลง',
            });
          }
        },
      });
    }
    try {
      await friendshipAction.current();
    } catch {
      // Keep optional OA UI failures out of the app's navigation/auth flow.
      if (window.Swal) {
        await window.Swal.fire({
          ...lineOAPopup,
          title: 'เพิ่มเพื่อน LINE OA',
          text: 'เปิดหน้าเพิ่มเพื่อนไม่สำเร็จ กรุณาลองอีกครั้ง',
          confirmButtonText: 'ตกลง',
        }).catch(() => {});
      }
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

        <button type="button" onClick={handleLineOAClick} className="action-btn line-oa-header-btn"
          aria-label="เพิ่มเพื่อน GunGong LINE OA" aria-busy={friendshipBusy}
          disabled={friendshipBusy || (lineLoading && window.liff?.isInClient?.())}>
          <img src="/img/logo.png" alt="" />
        </button>
      </div>
    </div>
  );
};

export default TopBanner;
