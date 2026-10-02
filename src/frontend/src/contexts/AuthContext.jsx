import { createContext, useContext, useState, useEffect } from 'react';
import { initializeAnalytics } from '../utils/firebase';
import { initializeLineSession, loginWithLine, logoutFromLine, getDisplayUser, getLineAuthError } from '../utils/lineAuth';
import { historyCache } from '../utils/pageCache';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [lineProfile, setLineProfile] = useState(null);
  const [lineLoading, setLineLoading] = useState(true);
  const [error, setError] = useState(null);
  const user = getDisplayUser(lineProfile);

  useEffect(() => {
    let active = true;
    initializeLineSession().then(profile => {
      if (active) {
        historyCache.invalidate();
        setLineProfile(profile);
        initializeAnalytics(); // Only after LIFF has consumed confidential callback parameters.
      }
    }).catch(() => {
      // Public browsing remains available if LINE initialization fails.
    }).finally(() => { if (active) setLineLoading(false); });
    return () => { active = false; historyCache.invalidate(); };
  }, []);

  const signInWithLine = async (options) => {
    setError(null);
    setLineLoading(true);
    try {
      const profile = await loginWithLine(options);
      if (profile) { historyCache.invalidate(); setLineProfile(profile); }
      return { success: true, redirecting: !profile };
    } catch (err) {
      const message = getLineAuthError(err);
      setError(message);
      return { success: false, error: message };
    } finally { setLineLoading(false); }
  };

  const signOut = async () => {
    setError(null);
    try {
      if (lineProfile) logoutFromLine();
      historyCache.invalidate();
      setLineProfile(null);
      return { success: true };
    } catch {
      const message = 'ออกจากระบบไม่สำเร็จ กรุณาลองอีกครั้ง';
      setError(message);
      return { success: false, error: message };
    }
  };

  return <AuthContext.Provider value={{ user, loading: lineLoading, lineLoading, lineProfile,
    canSignOut: !lineProfile || !window.liff?.isInClient(), error, signInWithLine, signOut,
    isAuthenticated: !!user }}>{children}</AuthContext.Provider>;
};

// Context and its hook are intentionally exported together.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

export default AuthContext;
