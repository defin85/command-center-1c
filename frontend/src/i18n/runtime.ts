import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'

import { DEFAULT_APP_LOCALE, FALLBACK_APP_LOCALE, type AppLocale, supportedAppLocales } from './constants'
import { getCurrentAppLocale, setCurrentAppLocale } from './localeStore'
import {
  defaultNamespace,
  eagerNamespaces,
  eagerResources,
  loadNamespaceCatalog,
  type TranslationNamespace,
} from './resources'

const namespaceLoadCache = new Map<string, Promise<void>>()

const ensureInitialized = () => {
  if (i18next.isInitialized) {
    return i18next
  }

  i18next.use(initReactI18next).init({
    resources: eagerResources,
    lng: getCurrentAppLocale(),
    fallbackLng: FALLBACK_APP_LOCALE,
    supportedLngs: [...supportedAppLocales],
    ns: [...eagerNamespaces],
    defaultNS: defaultNamespace,
    fallbackNS: defaultNamespace,
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
    returnNull: false,
  })

  return i18next
}

ensureInitialized()

const normalizeNamespaces = (value?: TranslationNamespace | TranslationNamespace[]) => {
  if (!value) {
    return [defaultNamespace] as TranslationNamespace[]
  }

  return Array.isArray(value) ? value : [value]
}

export const ensureNamespaces = async (
  locale: AppLocale,
  value?: TranslationNamespace | TranslationNamespace[],
): Promise<void> => {
  const namespaces = normalizeNamespaces(value)
  const targets = Array.from(new Set([locale, FALLBACK_APP_LOCALE] as AppLocale[]))

  await Promise.all(targets.flatMap((targetLocale) => (
    namespaces.map((namespace) => {
      const cacheKey = `${targetLocale}:${namespace}`
      const existing = namespaceLoadCache.get(cacheKey)
      if (existing) {
        return existing
      }

      if (i18next.hasResourceBundle(targetLocale, namespace)) {
        const resolved = Promise.resolve()
        namespaceLoadCache.set(cacheKey, resolved)
        return resolved
      }

      const pending = loadNamespaceCatalog(targetLocale, namespace).then((catalog) => {
        i18next.addResourceBundle(targetLocale, namespace, catalog, true, true)
      })
      namespaceLoadCache.set(cacheKey, pending)
      return pending
    })
  )))
}

export const changeLanguage = async (locale: AppLocale) => {
  await ensureNamespaces(locale, [...eagerNamespaces])
  setCurrentAppLocale(locale)
  if (i18next.language !== locale) {
    await i18next.changeLanguage(locale)
  }
}

export const getResolvedAppLocale = (): AppLocale => {
  const resolved = i18next.resolvedLanguage ?? i18next.language ?? DEFAULT_APP_LOCALE
  const normalized = supportedAppLocales.find((locale) => resolved === locale || resolved.startsWith(`${locale}-`))
  return normalized ?? DEFAULT_APP_LOCALE
}

export { i18next as i18n }
