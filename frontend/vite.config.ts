import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',  // Allow access from Windows host via WSL IP
    proxy: {
      '/api': {
        // Port 8180 - outside Windows reserved range (8013-8112)
        target: 'http://localhost:8180',
        changeOrigin: true,
      }
    },
    // Disable caching in development
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  },
  // Force dependency optimization on every start
  optimizeDeps: {
    force: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  }
})
