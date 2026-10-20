import { initializeApp } from 'firebase/app';
import { getAnalytics } from 'firebase/analytics';

const firebaseConfig = {
    apiKey: import.meta.env?.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env?.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env?.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env?.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env?.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env?.VITE_FIREBASE_APP_ID,
    measurementId: import.meta.env?.VITE_FIREBASE_MEASUREMENT_ID
};

// Optional browser configuration, not a server credential. Unconfigured forks
// must not initialize the original owner's Firebase project or analytics.
const app = firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId
    ? initializeApp(firebaseConfig) : null;

// Never send an OAuth/LIFF callback URL to Analytics before SDK initialization.
export let analytics = null;
export function initializeAnalytics() {
    if (!app || !firebaseConfig.measurementId || analytics) return;
    const parameters = new URLSearchParams(window.location.search);
    if (['code', 'state', 'access_token', 'id_token', 'liff.state'].some(key => parameters.has(key))) return;
    try { analytics = getAnalytics(app); } catch { /* Analytics is optional. */ }
}
export default app;
