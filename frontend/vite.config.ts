import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { execSync } from 'child_process'
import { readFileSync } from 'fs'
import { visualizer } from 'rollup-plugin-visualizer'

const frontendPackage = JSON.parse(
  readFileSync(path.resolve(__dirname, 'package.json'), 'utf8'),
) as { version?: string }

const resolveFrontendBuildId = (): string => {
  const explicitBuildId = process.env.CC1C_FRONTEND_BUILD_ID?.trim()
  if (explicitBuildId) {
    return explicitBuildId
  }

  try {
    return execSync('git rev-parse --short=12 HEAD', {
      cwd: __dirname,
      stdio: ['ignore', 'pipe', 'ignore'],
    }).toString().trim()
  } catch {
    return 'unknown'
  }
}

const frontendVersion = frontendPackage.version?.trim() || '0.0.0'
const frontendBuildId = resolveFrontendBuildId()

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    'import.meta.env.VITE_CC1C_APP_VERSION': JSON.stringify(frontendVersion),
    'import.meta.env.VITE_CC1C_BUILD_ID': JSON.stringify(frontendBuildId),
  },
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
    // Default Vite dev port often falls into Windows excluded port ranges, which breaks WSL localhost forwarding.
    // Keep a stable, Windows-friendly default, but allow overriding via env.
    port: Number(process.env.FRONTEND_PORT ?? process.env.VITE_DEV_PORT ?? process.env.PORT ?? 15173),
    host: '0.0.0.0',  // Allow access from Windows host via WSL IP
    proxy: {
      '/api': {
        // Port 8180 - outside Windows reserved range (8013-8112)
        target: 'http://localhost:8180',
        changeOrigin: true,
        ws: false,
      },
      '/ws': {
        // WebSocket proxy to API Gateway
        target: 'ws://localhost:8180',
        changeOrigin: true,
        ws: true,
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
          return undefined
        },
      },
    },
  }
})
