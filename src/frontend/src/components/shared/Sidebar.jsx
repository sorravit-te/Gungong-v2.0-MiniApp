import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import LineLoginButton from './LineLoginButton';
import { SCANNER_ROUTE_IDS, SCANNER_SUBMENU_ITEMS } from '../../utils/scannerNavigation';
import '../../styles/sidebar.css';

const Sidebar = ({ isCollapsed, onToggle, currentPage, onNavigate }) => {
  const { user, isAuthenticated, signOut, canSignOut } = useAuth();
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

  // State for expanded menu items
  const [expandedMenus, setExpandedMenus] = useState({ scanner: false });

  const toggleSubmenu = (menuId) => {
    setExpandedMenus(prev => ({ ...prev, [menuId]: !prev[menuId] }));
  };

  // Auto-expand scanner submenu when navigating to a scanner sub-page
  useEffect(() => {
    if (SCANNER_ROUTE_IDS.includes(currentPage)) {
      // Keep the existing auto-expand behavior when a scanner route is selected.
      // eslint-disable-next-line react-hooks/set-state-in-effect
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
              id: SCANNER_SUBMENU_ITEMS[0].id,
              label: SCANNER_SUBMENU_ITEMS[0].label,
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
              ),
            },
            {
              id: SCANNER_SUBMENU_ITEMS[1].id,
              label: SCANNER_SUBMENU_ITEMS[1].label,
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                  <line x1="1" y1="10" x2="23" y2="10"></line>
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
                    <span className="sidebar-user-email">บัญชี LINE</span>
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
              </div>
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
