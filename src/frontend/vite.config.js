import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // อ่าน .env จากโฟลเดอร์ root (gungong-v2.0/)
  envDir: '../../',
  server: {
    host: true, // Allow external access
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
