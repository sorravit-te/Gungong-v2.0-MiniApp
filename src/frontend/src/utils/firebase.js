import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
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

// Firebase Authentication
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

googleProvider.setCustomParameters({
    prompt: 'select_account'
});

// Firebase Analytics
export const analytics = getAnalytics(app);
export default app;
