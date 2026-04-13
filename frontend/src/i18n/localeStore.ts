import {
  DEFAULT_APP_LOCALE,
  FALLBACK_APP_LOCALE,
  LOCALE_OVERRIDE_STORAGE_KEY,
  type AppLocale,
  supportedAppLocales,
} from './constants'

const supportedLocaleSet = new Set<AppLocale>(supportedAppLocales)

let currentAppLocale: AppLocale = DEFAULT_APP_LOCALE

const normalizeCandidate = (value: string | null | undefined): string | null => {
  if (!value) {
    return null
  }

  const trimmed = value.trim().toLowerCase().replace(/_/g, '-')
  if (!trimmed) {
    return null
  }

  return trimmed
}

export const isAppLocale = (value: string | null | undefined): value is AppLocale => {
  const normalized = normalizeCandidate(value)
  return Boolean(normalized && supportedLocaleSet.has(normalized as AppLocale))
}

export const normalizeAppLocale = (value: string | null | undefined): AppLocale | null => {
  const normalized = normalizeCandidate(value)
  if (!normalized) {
    return null
  }

  if (supportedLocaleSet.has(normalized as AppLocale)) {
    return normalized as AppLocale
  }

  const [language] = normalized.split('-')
  if (language && supportedLocaleSet.has(language as AppLocale)) {
    return language as AppLocale
  }

  return null
}

export const getStoredLocaleOverride = (): AppLocale | null => {
  if (typeof window === 'undefined') {
    return null
  }

  return normalizeAppLocale(window.localStorage.getItem(LOCALE_OVERRIDE_STORAGE_KEY))
}

export const setStoredLocaleOverride = (locale: AppLocale | null) => {
  if (typeof window === 'undefined') {
    return
  }

  if (locale) {
    window.localStorage.setItem(LOCALE_OVERRIDE_STORAGE_KEY, locale)
    return
  }

  window.localStorage.removeItem(LOCALE_OVERRIDE_STORAGE_KEY)
}

export const getBrowserPreferredLocale = (): AppLocale | null => {
  if (typeof navigator === 'undefined') {
    return null
  }

  const preferredLocales = Array.isArray(navigator.languages) && navigator.languages.length > 0
    ? navigator.languages
    : [navigator.language]

  for (const candidate of preferredLocales) {
    const normalized = normalizeAppLocale(candidate)
    if (normalized) {
      return normalized
    }
  }

  return null
}

export const resolveInitialAppLocale = (): AppLocale => (
  getStoredLocaleOverride()
  ?? getBrowserPreferredLocale()
  ?? FALLBACK_APP_LOCALE
)

export const setCurrentAppLocale = (locale: AppLocale) => {
  currentAppLocale = locale
}

export const getCurrentAppLocale = (): AppLocale => currentAppLocale

currentAppLocale = resolveInitialAppLocale()
