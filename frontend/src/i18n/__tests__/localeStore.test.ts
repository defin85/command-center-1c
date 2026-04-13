import { beforeEach, describe, expect, it } from 'vitest'

import { FALLBACK_APP_LOCALE, LOCALE_OVERRIDE_STORAGE_KEY } from '../constants'
import {
  getStoredLocaleOverride,
  normalizeAppLocale,
  resolveInitialAppLocale,
  setStoredLocaleOverride,
} from '../localeStore'

const setBrowserLocales = (language: string, languages: string[]) => {
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: language,
  })
  Object.defineProperty(window.navigator, 'languages', {
    configurable: true,
    value: languages,
  })
}

describe('localeStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setBrowserLocales('de-DE', ['de-DE'])
  })

  it('normalizes supported public locales and strips region variants', () => {
    expect(normalizeAppLocale('ru_RU')).toBe('ru')
    expect(normalizeAppLocale('en-US')).toBe('en')
    expect(normalizeAppLocale('de-DE')).toBeNull()
    expect(normalizeAppLocale('')).toBeNull()
  })

  it('persists and clears the explicit locale override in localStorage', () => {
    setStoredLocaleOverride('en')

    expect(localStorage.getItem(LOCALE_OVERRIDE_STORAGE_KEY)).toBe('en')
    expect(getStoredLocaleOverride()).toBe('en')

    setStoredLocaleOverride(null)

    expect(localStorage.getItem(LOCALE_OVERRIDE_STORAGE_KEY)).toBeNull()
    expect(getStoredLocaleOverride()).toBeNull()
  })

  it('prefers stored override over browser locale and fallback default', () => {
    setBrowserLocales('en-US', ['en-US', 'ru-RU'])
    expect(resolveInitialAppLocale()).toBe('en')

    setStoredLocaleOverride('ru')
    expect(resolveInitialAppLocale()).toBe('ru')

    localStorage.clear()
    setBrowserLocales('de-DE', ['de-DE'])
    expect(resolveInitialAppLocale()).toBe(FALLBACK_APP_LOCALE)
  })
})
