import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import '../../styles/sidebar.css';

const Sidebar = ({ isCollapsed, onToggle, currentPage, onNavigate }) => {
  const { user, isAuthenticated, signInWithGoogle, signOut } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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

  // Handle switch account
  const handleSwitchAccount = () => {
    setShowUserMenu(false);
    signInWithGoogle(); // Re-trigger Google sign-in to select different account
  };

  // State for expanded menu items
  const [expandedMenus, setExpandedMenus] = useState({ scanner: false });

  const toggleSubmenu = (menuId) => {
    setExpandedMenus(prev => ({ ...prev, [menuId]: !prev[menuId] }));
  };

  // Auto-expand scanner submenu when navigating to a scanner sub-page
  useEffect(() => {
    const scannerSubPages = ['check-content', 'check-personal', 'scan-image', 'scan-qr', 'id-card-scanner'];
    if (scannerSubPages.includes(currentPage)) {
      setExpandedMenus(prev => ({ ...prev, scanner: true }));
    }
  }, [currentPage]);

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
          hasSubItems: true,
          subItems: [
            {
              id: 'check-content',
              label: 'Check Content',
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
              ),
            },
            {
              id: 'check-personal',
              label: 'Check Personal',
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                  <line x1="1" y1="10" x2="23" y2="10"></line>
                </svg>
              ),
            },
            {
              id: 'scan-image',
              label: 'Scan Image',
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                  <circle cx="12" cy="13" r="4"></circle>
                </svg>
              ),
            },
          ],
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
        {!isCollapsed && <span className="brand-text">GunGong</span>}

        {/* Toggle Button - inside brand for hover targeting */}
        <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle sidebar">
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
        {menuGroups.map((group, groupIndex) => (
          <div key={group.title} className="menu-group">
            {!isCollapsed && (
              <div className="menu-group-title">{group.title}</div>
            )}
            {isCollapsed && groupIndex > 0 && <div className="menu-divider"></div>}
            <div className="menu-group-items">
              {group.items.map((item) => (
                <div key={item.id} className="sidebar-item-wrapper">
                  {item.hasSubItems ? (
                    <>
                      <button
                        className={`sidebar-item has-submenu ${expandedMenus[item.id] ? 'expanded' : ''} ${
                          currentPage === item.id || item.subItems?.some(sub => currentPage === sub.id) ? 'active' : ''
                        }`}
                        onClick={() => {
                          if (isCollapsed) {
                            onNavigate(item.id);
                          } else {
                            toggleSubmenu(item.id);
                          }
                        }}
                        title={isCollapsed ? item.label : ''}
                      >
                        {(currentPage === item.id || item.subItems?.some(sub => currentPage === sub.id)) && (
                          <div className="active-indicator"></div>
                        )}
                        <div className="item-icon">{item.icon}</div>
                        {!isCollapsed && <span className="item-label">{item.label}</span>}
                        {!isCollapsed && (
                          <svg
                            className={`submenu-chevron ${expandedMenus[item.id] ? 'rotated' : ''}`}
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <polyline points="6 9 12 15 18 9"></polyline>
                          </svg>
                        )}
                      </button>
                      {!isCollapsed && expandedMenus[item.id] && (
                        <div className="submenu-items">
                          {item.subItems.map((subItem) => (
                            <button
                              key={subItem.id}
                              className={`sidebar-item submenu-item ${currentPage === subItem.id ? 'active' : ''}`}
                              onClick={() => onNavigate(subItem.id)}
                            >
                              {currentPage === subItem.id && <div className="active-indicator"></div>}
                              <div className="item-icon">{subItem.icon}</div>
                              <span className="item-label">{subItem.label}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <button
                      className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
                      onClick={() => onNavigate(item.id)}
                      title={isCollapsed ? item.label : ''}
                    >
                      {currentPage === item.id && <div className="active-indicator"></div>}
                      <div className="item-icon">{item.icon}</div>
                      {!isCollapsed && <span className="item-label">{item.label}</span>}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer - Settings & User */}
      <div className="sidebar-footer">
        {!isCollapsed && (
          <div className="menu-group-title">Settings</div>
        )}
        <button
          className="sidebar-item settings-btn"
          title={isCollapsed ? 'ตั้งค่า' : ''}
        >
          <div className="item-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </div>
          {!isCollapsed && <span className="item-label">ตั้งค่า</span>}
        </button>

        {/* User/Login Section */}
        {isAuthenticated && user ? (
          /* User profile with dropdown menu */
          <div className="sidebar-user-wrapper" ref={userMenuRef}>
            <button
              className={`sidebar-user ${showUserMenu ? 'active' : ''}`}
              onClick={() => setShowUserMenu(!showUserMenu)}
              title={isCollapsed ? user.displayName : ''}
            >
              <img
                src={user.photoURL || '/img/profile.png'}
                alt={user.displayName}
                className="sidebar-user-avatar"
              />
              {!isCollapsed && (
                <>
                  <div className="sidebar-user-info">
                    <span className="sidebar-user-name">{user.displayName}</span>
                    <span className="sidebar-user-email">{user.email}</span>
                  </div>
                  <svg className="sidebar-user-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </>
              )}
            </button>

            {/* Dropdown Menu */}
            {showUserMenu && (
              <div className={`user-dropdown-menu ${isCollapsed ? 'collapsed-position' : ''}`}>
                <div className="dropdown-header">
                  <img src={user.photoURL || '/img/profile.png'} alt="" />
                  <div>
                    <div className="dropdown-user-name">{user.displayName}</div>
                    <div className="dropdown-user-email">{user.email}</div>
                  </div>
                </div>
                <div className="dropdown-divider"></div>
                <button className="dropdown-item" onClick={handleSwitchAccount}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                    <circle cx="9" cy="7" r="4"></circle>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                  </svg>
                  <span>เปลี่ยนบัญชี</span>
                </button>
                <button className="dropdown-item logout" onClick={handleLogout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                  </svg>
                  <span>ออกจากระบบ</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Show login button when not logged in */
          <button
            className="sidebar-login-btn"
            onClick={signInWithGoogle}
            title={isCollapsed ? 'เข้าสู่ระบบด้วย Google' : ''}
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            {!isCollapsed && <span>เข้าสู่ระบบ</span>}
          </button>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;
