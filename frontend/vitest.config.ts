import { defineConfig, configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'
import {
  FAST_DEFAULT_VITEST_PROJECT,
  HEAVY_ROUTE_PRIMARY_VITEST_PROJECT,
  HEAVY_ROUTE_PROJECT_FILES,
  HEAVY_ROUTE_SECONDARY_VITEST_PROJECT,
  HEAVY_ROUTE_TERTIARY_VITEST_PROJECT,
  HEAVY_ROUTE_TEST_FILES,
} from './src/test/runtimePerimeters'

const defaultExcludes = [...configDefaults.exclude, 'tests/**']

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Full validate:ui-platform runs many integration-heavy route suites in parallel.
    // Keep enough budget to avoid false negatives from worker contention.
    testTimeout: 120000,
    hookTimeout: 120000,
    maxWorkers: 2,
    minWorkers: 1,
    exclude: defaultExcludes,
    projects: [
      {
        extends: true,
        test: {
          name: FAST_DEFAULT_VITEST_PROJECT,
          exclude: [...defaultExcludes, ...HEAVY_ROUTE_TEST_FILES],
          sequence: {
            groupOrder: 0,
          },
        },
      },
      {
        extends: true,
        test: {
          name: HEAVY_ROUTE_PRIMARY_VITEST_PROJECT,
          include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_PRIMARY_VITEST_PROJECT]],
          fileParallelism: false,
          maxWorkers: 1,
          minWorkers: 1,
          sequence: {
            groupOrder: 1,
          },
        },
      },
      {
        extends: true,
        test: {
          name: HEAVY_ROUTE_SECONDARY_VITEST_PROJECT,
          include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_SECONDARY_VITEST_PROJECT]],
          fileParallelism: false,
          maxWorkers: 1,
          minWorkers: 1,
          sequence: {
            groupOrder: 2,
          },
        },
      },
      {
        extends: true,
        test: {
          name: HEAVY_ROUTE_TERTIARY_VITEST_PROJECT,
          include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_TERTIARY_VITEST_PROJECT]],
          fileParallelism: false,
          maxWorkers: 1,
          minWorkers: 1,
          sequence: {
            groupOrder: 3,
          },
        },
      },
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData',
        'dist/',
      ],
    },
  },
})
