import { initializeApp } from 'firebase/app';
import { getAnalytics } from 'firebase/analytics';

const firebaseConfig = {
    apiKey: "AIzaSyBmtYwembGaFfwovG8bZQ-EEikc1EK_VfM",
    authDomain: "gungong-6502f.firebaseapp.com",
    projectId: "gungong-6502f",
    storageBucket: "gungong-6502f.firebasestorage.app",
    messagingSenderId: "904053267778",
    appId: "1:904053267778:web:1450339de4202808d67cdb",
    measurementId: "G-8R3F5JPBPB"
};

const app = initializeApp(firebaseConfig);

// Never send an OAuth/LIFF callback URL to Analytics before SDK initialization.
export let analytics = null;
export function initializeAnalytics() {
    if (analytics) return;
    const parameters = new URLSearchParams(window.location.search);
    if (['code', 'state', 'access_token', 'id_token', 'liff.state'].some(key => parameters.has(key))) return;
    try { analytics = getAnalytics(app); } catch { /* Analytics is optional. */ }
}
export default app;
