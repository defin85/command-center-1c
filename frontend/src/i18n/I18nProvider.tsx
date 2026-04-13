import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { SystemBootstrapI18nSummary } from '@/api/generated/model/systemBootstrapI18nSummary'
import { useShellBootstrap } from '@/api/queries/shellBootstrap'
import { queryKeys } from '@/api/queries/queryKeys'

import { antdLocaleByAppLocale } from './localeBridge'
import { changeLanguage } from './runtime'
import { DEFAULT_APP_LOCALE, type AppLocale, supportedAppLocales } from './constants'
import {
  getCurrentAppLocale,
  getStoredLocaleOverride,
  normalizeAppLocale,
  resolveInitialAppLocale,
  setStoredLocaleOverride,
} from './localeStore'

type LocaleState = {
  locale: AppLocale
  defaultLocale: AppLocale
  supportedLocales: readonly AppLocale[]
  requestedLocale: AppLocale | null
  antdLocale: typeof antdLocaleByAppLocale.en
  setLocale: (locale: AppLocale) => Promise<void>
  clearLocaleOverride: () => Promise<void>
}

const LocaleContext = createContext<LocaleState | null>(null)

const createFallbackLocaleState = (): LocaleState => {
  const locale = getCurrentAppLocale()
  return {
    locale,
    defaultLocale: DEFAULT_APP_LOCALE,
    supportedLocales: supportedAppLocales,
    requestedLocale: getStoredLocaleOverride(),
    antdLocale: antdLocaleByAppLocale[locale],
    setLocale: async () => undefined,
    clearLocaleOverride: async () => undefined,
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const hasToken = typeof window !== 'undefined' && Boolean(window.localStorage.getItem('auth_token'))
  const shellBootstrapQuery = useShellBootstrap({ enabled: hasToken })
  const shellBootstrapI18n: SystemBootstrapI18nSummary | undefined = shellBootstrapQuery.data?.i18n
  const [locale, setLocaleState] = useState<AppLocale>(() => resolveInitialAppLocale())
  const [defaultLocale, setDefaultLocale] = useState<AppLocale>(DEFAULT_APP_LOCALE)
  const [supportedLocales, setSupportedLocales] = useState<readonly AppLocale[]>(supportedAppLocales)
  const requestedLocale = normalizeAppLocale(shellBootstrapI18n?.requested_locale)

  const applyLocale = useCallback(async (nextLocale: AppLocale) => {
    setLocaleState(nextLocale)
    await changeLanguage(nextLocale)
  }, [])

  useEffect(() => {
    void applyLocale(locale)
  }, [applyLocale, locale])

  useEffect(() => {
    const supported = (shellBootstrapI18n?.supported_locales ?? supportedAppLocales)
      .map((entry) => normalizeAppLocale(entry))
      .filter((entry): entry is AppLocale => Boolean(entry))

    if (supported.length > 0) {
      setSupportedLocales(supported)
    }

    const nextDefaultLocale = normalizeAppLocale(shellBootstrapI18n?.default_locale) ?? DEFAULT_APP_LOCALE
    setDefaultLocale(nextDefaultLocale)

    const explicitOverride = getStoredLocaleOverride()
    const effectiveLocale = normalizeAppLocale(shellBootstrapI18n?.effective_locale)
      ?? explicitOverride
      ?? nextDefaultLocale

    if (!explicitOverride) {
      void applyLocale(effectiveLocale)
    }
  }, [applyLocale, shellBootstrapI18n?.default_locale, shellBootstrapI18n?.effective_locale, shellBootstrapI18n?.supported_locales])

  const setLocale = useCallback(async (nextLocale: AppLocale) => {
    setStoredLocaleOverride(nextLocale)
    await applyLocale(nextLocale)
    if (hasToken) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.shell.bootstrap() })
    }
  }, [applyLocale, hasToken, queryClient])

  const clearLocaleOverride = useCallback(async () => {
    setStoredLocaleOverride(null)
    const nextLocale = normalizeAppLocale(shellBootstrapI18n?.effective_locale)
      ?? normalizeAppLocale(shellBootstrapI18n?.default_locale)
      ?? DEFAULT_APP_LOCALE
    await applyLocale(nextLocale)
    if (hasToken) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.shell.bootstrap() })
    }
  }, [applyLocale, hasToken, queryClient, shellBootstrapI18n?.default_locale, shellBootstrapI18n?.effective_locale])

  const value = useMemo<LocaleState>(() => ({
    locale,
    defaultLocale,
    supportedLocales,
    requestedLocale,
    antdLocale: antdLocaleByAppLocale[locale],
    setLocale,
    clearLocaleOverride,
  }), [clearLocaleOverride, defaultLocale, locale, requestedLocale, setLocale, supportedLocales])

  return (
    <LocaleContext.Provider value={value}>
      {children}
    </LocaleContext.Provider>
  )
}

export const useLocaleState = () => {
  const value = useContext(LocaleContext)
  return value ?? createFallbackLocaleState()
}
