import { useState, useEffect, useCallback } from 'react';
import './styles/main.css';
import './styles/pdpa.css';
import './styles/home.css';
import './styles/verify.css';
import './styles/scanner.css';
import './styles/social.css';
import './styles/history.css';
import './styles/sidebar.css';
import './styles/auth.css';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import TopBanner from './components/shared/TopBanner';
import BottomNav from './components/shared/BottomNav';
import Sidebar from './components/shared/Sidebar';
import MobileLineEntry from './components/shared/MobileLineEntry';
import PDPAModal from './components/shared/PDPAModal';
import Home from './components/home';
import Verify from './components/verify';
import Scanner from './components/scanner';
import Social from './components/social';
import History from './components/history';
import IDCardScanner from './components/IDCardScanner';
import ScanImage from './components/ScanImage';
import { APP_SECTIONS } from './utils/lineAuth';

function App() {
  const [activeSection, setActiveSection] = useState(() => {
    const section = new URLSearchParams(window.location.search).get('section');
    return APP_SECTIONS.has(section) ? section : 'home';
  });
  const { user, lineProfile: userProfile } = useAuth();
  const [showPDPA, setShowPDPA] = useState(() => localStorage.getItem('gungong_pdpa_accepted') !== 'true');
  // Sidebar State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);

  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Load dark mode preference from localStorage
    const saved = localStorage.getItem('gungong_dark_mode');
    return saved === 'true';
  });

  // Apply dark mode class to document
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark-mode');
    } else {
      document.documentElement.classList.remove('dark-mode');
    }
    localStorage.setItem('gungong_dark_mode', isDarkMode.toString());
  }, [isDarkMode]);

  const toggleDarkMode = useCallback(() => {
    setIsDarkMode(prev => !prev);
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsSidebarCollapsed(prev => !prev);
  }, []);

  const handleNavigate = useCallback((section) => {
    setActiveSection(section);
    // Scroll to top when changing sections
    window.scrollTo(0, 0);
  }, []);

  const handlePDPAAccept = () => {
    setShowPDPA(false);
  };

  const renderPage = () => {
    // Handle ID card scanner route
    if (activeSection === 'id-card-scanner') {
      return <IDCardScanner onNavigate={handleNavigate} />;
    }

    // Handle scan image mode selection route
    if (activeSection === 'scan-image') {
      return <ScanImage onNavigate={handleNavigate} />;
    }

    // Get the main section from activeSection
    const mainSection = activeSection.startsWith('verify-') ? 'verify' :
                        activeSection.startsWith('check-') || activeSection === 'scan-qr' ? 'scanner' :
                        activeSection;

    switch (mainSection) {
      case 'home':
        return <Home key={user?.uid || 'anonymous'} onNavigate={handleNavigate} />;
      case 'verify':
        return <Verify userProfile={userProfile} onNavigate={handleNavigate} currentSubPage={activeSection} />;
      case 'scanner':
        return <Scanner onNavigate={handleNavigate} currentSubPage={activeSection} />;
      case 'social':
        return <Social key={user?.uid || 'anonymous'} userProfile={userProfile} />;
      case 'history':
        return <History key={user?.uid || 'anonymous'} />;
      default:
        return <Home key={user?.uid || 'anonymous'} onNavigate={handleNavigate} />;
    }
  };

  return (
    <div className={`app ${isDarkMode ? 'dark-mode' : ''}`}>
      <MobileLineEntry />
      <PDPAModal isOpen={showPDPA} onAccept={handlePDPAAccept} />

      {/* Sidebar for Desktop/Tablet */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggle={toggleSidebar}
        currentPage={activeSection}
        onNavigate={handleNavigate}
      />

      {/* Main Content Wrapper allowing space for Sidebar */}
      <div className={`app-container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''} has-sidebar`}>
        <TopBanner
          userProfile={userProfile}
          isDarkMode={isDarkMode}
          onToggleDarkMode={toggleDarkMode}
        />

        <main>
          {renderPage()}
        </main>

        {/* BottomNav hidden on desktop via CSS media queries usually, but let's keep it structurally here */}
        <BottomNav activeSection={activeSection} onNavigate={handleNavigate} />
        
      </div>
    </div>
  );
}

// Wrap App with AuthProvider
const AppWithAuth = () => (
  <AuthProvider>
    <App />
  </AuthProvider>
);

export default AppWithAuth;

