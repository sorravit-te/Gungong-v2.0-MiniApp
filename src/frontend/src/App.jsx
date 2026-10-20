import { Activity, useState, useEffect, useCallback, lazy, Suspense } from 'react';
import './shared/styles/main.css';
import './features/privacy/pdpa.css';
import './features/home/home.css';
import './features/scanner/scanner.css';
import './features/community/social.css';
import './features/history/history.css';
import './shared/layout/sidebar.css';
import './features/auth/auth.css';

import { AuthProvider, useAuth } from './features/auth/AuthContext';
import TopBanner from './shared/layout/TopBanner';
import BottomNav from './shared/layout/BottomNav';
import Sidebar from './shared/layout/Sidebar';
import MobileLineEntry from './features/auth/components/MobileLineEntry';
import PDPAModal from './features/privacy/PDPAModal';
import './features/report/report.css';
import { APP_SECTIONS, getAppEntry } from './features/auth/lineAuth';
import { communityCache } from './shared/cache/pageCache';
import { loadCommunity, loadCommunityViewer } from './features/community/utils/community';
import { communityViewerCache } from './features/community/utils/communityViewerCache';

// Lightweight page shells render immediately; only the heavy chart is deferred.
import Home from './features/home/home';
import Report from './features/report/report';
import Scanner from './features/scanner/scanner';
import Social from './features/community/social';
import History from './features/history/history';
const ScanImage = lazy(() => import('./features/scanner/ScanImage'));

function App() {
  const { user, lineProfile: userProfile, loading: authLoading } = useAuth();
  const [initialEntry] = useState(() => getAppEntry(window.location.search));
  const [manualSection, setManualSection] = useState(null);
  // Auth completion rerenders this component after LIFF restores its URL.
  // Derive the entry directly, avoiding an extra render/effect waterfall.
  const entry = authLoading ? initialEntry : getAppEntry(window.location.search);
  const activeSection = manualSection ?? entry.section;
  const historyEntryId = manualSection === null ? entry.historyId : null;
  const [communityVisited, setCommunityVisited] = useState(initialEntry.section === 'social');

  useEffect(() => {
    // Public feed can load independently of LINE login and the current page.
    void communityCache.read('feed', loadCommunity).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user?.uid) return;
    let active = true;
    const owner = user.uid;
    // Reuse the feed request and load member reactions before Community opens.
    void communityCache.read('feed', loadCommunity).then(feed => {
      if (active) return communityViewerCache.read(owner, feed.posts.map(post => post.id), loadCommunityViewer);
    }).catch(() => {});
    return () => { active = false; };
  }, [user?.uid]);

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
    if (activeSection === 'social' || section === 'social') setCommunityVisited(true);
    setManualSection(APP_SECTIONS.has(section) ? section : 'home');
    // Scroll to top when changing sections
    window.scrollTo(0, 0);
  }, [activeSection]);

  const handlePDPAAccept = () => {
    setShowPDPA(false);
  };

  const renderPage = () => {
    // Handle scan image mode selection route
    if (activeSection === 'scan-image') {
      return <ScanImage onNavigate={handleNavigate} />;
    }

    // Get the main section from activeSection
    const mainSection = activeSection.startsWith('check-') || activeSection === 'scan-qr' ? 'scanner' :
                        activeSection;

    switch (mainSection) {
      case 'home':
        return <Home key={user?.uid || 'anonymous'} onNavigate={handleNavigate} />;
      case 'report':
        return <Report key={user?.uid || 'anonymous'} />;
      case 'scanner':
        return <Scanner onNavigate={handleNavigate} currentSubPage={activeSection} />;
      case 'social':
        return null; // Kept below in Activity so post images/state survive navigation.
      case 'history':
        return <History key={user?.uid || 'anonymous'} entryId={historyEntryId} />;
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
          <Suspense fallback={<div className="route-skeleton" role="status" aria-label="กำลังเตรียมหน้าตรวจสอบ"><span /><span /></div>}>
            {renderPage()}
          </Suspense>
          {(communityVisited || activeSection === 'social') && <Activity key={user?.uid || 'anonymous'} mode={activeSection === 'social' ? 'visible' : 'hidden'}>
            <Social />
          </Activity>}
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

