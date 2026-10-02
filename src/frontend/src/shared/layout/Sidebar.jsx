import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../../features/auth/AuthContext';
import LineLoginButton from '../../features/auth/components/LineLoginButton';
import { SCANNER_ROUTE_IDS } from '../../features/scanner/scannerNavigation';
import './sidebar.css';
import { PRIMARY_NAV_ITEMS } from '../navigation/appNavigation';
import NavigationIcon from './NavigationIcon';

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

  const menuGroups = [
    { title: 'Primary', items: PRIMARY_NAV_ITEMS },
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
                    type="button"
                    className={`sidebar-item ${isActive(item) ? 'active' : ''}`}
                    onClick={() => onNavigate(item.id)}
                    title={isCollapsed ? item.label : ''}
                    aria-label={item.label}
                    aria-current={isActive(item) ? 'page' : undefined}
                  >
                    {isActive(item) && <div className="active-indicator"></div>}
                    <div className="item-icon"><NavigationIcon id={item.id} /></div>
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
