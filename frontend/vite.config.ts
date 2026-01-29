import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: process.env.ANALYZE_BUNDLE === '1'
    ? [
      react(),
      visualizer({
        filename: 'dist/bundle-report.html',
        gzipSize: true,
        brotliSize: true,
      }),
    ]
    : [react()],
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
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (!id.includes('node_modules')) return undefined

          if (id.includes('/node_modules/monaco-editor/') || id.includes('/node_modules/@monaco-editor/')) {
            return 'monaco'
          }

          if (
            id.includes('/node_modules/react/') ||
            id.includes('/node_modules/react-dom/') ||
            id.includes('/node_modules/scheduler/') ||
            id.includes('/node_modules/react-router') ||
            id.includes('/node_modules/react-router-dom/')
          ) {
            return 'react'
          }

          if (id.includes('/node_modules/@tanstack/')) {
            return 'tanstack'
          }

          if (id.includes('/node_modules/antd/')) {
            const match = /\/node_modules\/antd\/(?:es|lib)\/([^/]+)\//.exec(id)
            const sub = match?.[1] ?? ''
            if (sub === 'table') return 'antd-table'
            if (sub === 'form') return 'antd-form'
            if (sub === 'date-picker' || sub === 'time-picker' || sub === 'calendar') return 'antd-date'
            if (sub === 'select' || sub === 'tree-select') return 'antd-select'
            if (sub === 'drawer' || sub === 'modal' || sub === 'tooltip' || sub === 'popover') return 'antd-overlay'
            return 'antd-core'
          }

          if (id.includes('/node_modules/@ant-design/')) {
            return 'ant-design'
          }

          if (id.includes('/node_modules/@rc-component/') || id.includes('/node_modules/rc-')) {
            return 'rc'
          }

          if (id.includes('/node_modules/socket.io-client/') || id.includes('/node_modules/engine.io-client/')) {
            return 'socket-io'
          }

          if (id.includes('/node_modules/recharts/') || id.includes('/node_modules/d3-')) {
            return 'charts'
          }

          if (id.includes('/node_modules/reactflow/')) {
            return 'reactflow'
          }

          if (id.includes('/node_modules/zustand/')) {
            return 'zustand'
          }

          if (id.includes('/node_modules/axios/')) {
            return 'axios'
          }

          return 'vendor'
        },
      },
    },
  }
})
