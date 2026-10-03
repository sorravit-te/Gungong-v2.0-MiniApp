import { lazy, Suspense, useState } from 'react';
import App from './App.jsx';
import { getSharedToken } from './features/history/shareToken.js';

// Keep the normal app eager so refresh renders its existing shell directly.
const SharedHistoryPage = lazy(() => import('./features/history/SharedHistoryPage.jsx'));

export default function AppEntry() {
  const [token] = useState(() => getSharedToken(window.location.search, window.location.hash));
  if (!token) return <App />;
  return <Suspense fallback={<p role="status" style={{ padding: 24 }}>กำลังเปิด GunGong…</p>}>
    <SharedHistoryPage token={token} />
  </Suspense>;
}
