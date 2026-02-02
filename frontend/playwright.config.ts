import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/browser',
  timeout: 30_000,
  fullyParallel: true,
  use: {
    baseURL: 'http://127.0.0.1:15173',
    headless: true,
  },
  webServer: {
    command: 'npx vite --host 127.0.0.1 --port 15173 --strictPort',
    port: 15173,
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
