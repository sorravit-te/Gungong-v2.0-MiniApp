import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../../contexts/AuthContext';
import LineLoginButton from './LineLoginButton';
import { SCANNER_ROUTE_IDS } from '../../utils/scannerNavigation';
import '../../styles/sidebar.css';

const Sidebar = ({ isCollapsed, onToggle, currentPage, onNavigate }) => {
  const { user, isAuthenticated, signOut, canSignOut } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);
  const userPopupRef = useRef(null);

  useLayoutEffect(() => {
    if (!showUserMenu) return;
    const menu = userPopupRef.current;
    const anchor = userMenuRef.current;
    const position = () => {
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(isCollapsed ? 220 : rect.width, window.innerWidth - 16);
      menu.style.width = `${width}px`;
      const height = menu.offsetHeight;
      const left = isCollapsed ? rect.right + 8 : rect.left;
      const top = isCollapsed ? rect.bottom - height : rect.top - height - 8;
      menu.style.left = `${Math.max(8, Math.min(left, window.innerWidth - width - 8))}px`;
      menu.style.top = `${Math.max(8, Math.min(top, window.innerHeight - height - 8))}px`;
    };
    position();
    (menu.querySelector('button') || menu).focus({ preventScroll: true });
    const observer = new ResizeObserver(position);
    observer.observe(anchor);
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, true);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', position, true);
    };
  }, [showUserMenu, isCollapsed]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target) &&
          !userPopupRef.current?.contains(event.target)) {
        setShowUserMenu(false);
      }
    };
    const handleEscape = event => {
      if (event.key === 'Escape' && userPopupRef.current) {
        setShowUserMenu(false);
        userMenuRef.current?.querySelector('.sidebar-user')?.focus({ preventScroll: true });
      }
    };
    document.addEventListener('pointerdown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('pointerdown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  // Handle logout with confirmation
  const handleLogout = () => {
    setShowUserMenu(false);
    if (window.Swal) {
      window.Swal.fire({
        title: 'ออกจากระบบ',
        text: 'คุณต้องการออกจากระบบหรือไม่?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'ออกจากระบบ',
        cancelButtonText: 'ยกเลิก',
      }).then((result) => {
        if (result.isConfirmed) {
          signOut();
        }
      });
    } else {
      if (confirm('คุณต้องการออกจากระบบหรือไม่?')) {
        signOut();
      }
    }
  };

  const isActive = item => currentPage === item.id ||
    (item.id === 'scanner' && SCANNER_ROUTE_IDS.includes(currentPage));

  // Menu groups following Modern SaaS pattern
  const menuGroups = [
    {
      title: 'Main',
      items: [
        {
          id: 'home',
          label: 'Home',
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
          ),
        },
        {
          id: 'verify',
          label: 'Verify',
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="8" r="7"></circle>
              <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"></polyline>
            </svg>
          ),
        },
        {
          id: 'social',
          label: 'Community',
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
              <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
            </svg>
          ),
        },
      ],
    },
    {
      title: 'Tools',
      items: [
        {
          id: 'scanner',
          label: 'Scanner',
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
          ),
        },
      ],
    },
    {
      title: 'Management',
      items: [
        {
          id: 'history',
          label: 'History',
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
          ),
        },
      ],
    },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : 'expanded'}`}>
      {/* Logo/Brand with Toggle Button */}
      <div className="sidebar-brand">
        <div className="brand-logo-wrapper">
          <img
            src="/img/logo.png"
            alt="GunGong"
            className="sidebar-logo-icon"
          />
        </div>
        <span className="brand-text" aria-hidden={isCollapsed}>GunGong</span>

        {/* Toggle Button - inside brand for hover targeting */}
        <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle sidebar" aria-expanded={!isCollapsed}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {isCollapsed ? (
              <polyline points="9 18 15 12 9 6"></polyline>
            ) : (
              <polyline points="15 18 9 12 15 6"></polyline>
            )}
          </svg>
        </button>
      </div>

      {/* Menu Groups */}
      <nav className="sidebar-nav">
        {menuGroups.map(group => (
          <div key={group.title} className="menu-group">
            <div className="menu-group-items">
              {group.items.map((item) => (
                <div key={item.id} className="sidebar-item-wrapper">
                  <button
                    className={`sidebar-item ${isActive(item) ? 'active' : ''}`}
                    onClick={() => onNavigate(item.id)}
                    title={isCollapsed ? item.label : ''}
                    aria-label={item.label}
                  >
                    {isActive(item) && <div className="active-indicator"></div>}
                    <div className="item-icon">{item.icon}</div>
                    <span className="item-label" aria-hidden={isCollapsed}>{item.label}</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer - User */}
      <div className="sidebar-footer">

        {/* User/Login Section */}
        {isAuthenticated && user ? (
          /* User profile with dropdown menu */
          <div className="sidebar-user-wrapper" ref={userMenuRef}>
            <button
              className={`sidebar-user ${showUserMenu ? 'active' : ''}`}
              onClick={() => setShowUserMenu(!showUserMenu)}
              title={isCollapsed ? user.displayName : ''}
              aria-label={user.displayName}
              aria-haspopup="dialog"
              aria-expanded={showUserMenu}
              aria-controls="sidebar-profile-menu"
            >
              <img
                src={user.photoURL || '/img/profile.png'}
                alt={user.displayName}
                className="sidebar-user-avatar"
              />
              <div className="sidebar-user-info" aria-hidden={isCollapsed}>
                <span className="sidebar-user-name">{user.displayName}</span>
                <span className="sidebar-user-email">บัญชี LINE</span>
              </div>
              <svg className="sidebar-user-chevron" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>

            {/* Dropdown Menu */}
            {showUserMenu && createPortal(
              <div className="user-dropdown-menu" ref={userPopupRef} id="sidebar-profile-menu"
                role="dialog" aria-label="บัญชี LINE" tabIndex={-1}>
                <div className="dropdown-header">
                  <img src={user.photoURL || '/img/profile.png'} alt="" />
                  <div>
                    <div className="dropdown-user-name">{user.displayName}</div>
                    <div className="dropdown-user-email">บัญชี LINE</div>
                  </div>
                </div>
                <div className="dropdown-divider"></div>
                {canSignOut && <button className="dropdown-item logout" onClick={handleLogout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                  </svg>
                  <span>ออกจากระบบ</span>
                </button>}
              </div>, document.body
            )}
          </div>
        ) : (
          <div className="sidebar-login-options">
          <LineLoginButton currentPage={currentPage} className="sidebar-login-btn" />
          </div>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;
