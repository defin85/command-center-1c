/**
 * Vitest Setup File
 * Configures testing environment and global utilities.
 */

import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock window.matchMedia (used by Ant Design components)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
})

// JSDOM does not implement pseudo-element styles. Some UI libs call getComputedStyle(el, '::before').
// Ignore pseudo-element argument to prevent noisy "Not implemented" warnings in tests.
{
  const originalGetComputedStyle = window.getComputedStyle.bind(window)
  Object.defineProperty(window, 'getComputedStyle', {
    writable: true,
    value: (elt: Element) => originalGetComputedStyle(elt),
  })
}

// Mock IntersectionObserver (used by some Ant Design components)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as unknown as typeof IntersectionObserver

// Ensure localStorage is available (some tests import API client at module init time)
if (!window.localStorage || typeof window.localStorage.getItem !== 'function') {
  const store = new Map<string, string>()

  Object.defineProperty(window, 'localStorage', {
    writable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, String(value))
      },
      removeItem: (key: string) => {
        store.delete(key)
      },
      clear: () => {
        store.clear()
      },
      key: (idx: number) => Array.from(store.keys())[idx] ?? null,
      get length() {
        return store.size
      },
    },
  })
}
