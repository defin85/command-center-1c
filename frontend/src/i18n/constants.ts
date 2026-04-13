export const supportedAppLocales = ['ru', 'en'] as const

export type AppLocale = (typeof supportedAppLocales)[number]

export const DEFAULT_APP_LOCALE: AppLocale = 'ru'
export const FALLBACK_APP_LOCALE: AppLocale = DEFAULT_APP_LOCALE
export const LOCALE_OVERRIDE_STORAGE_KEY = 'cc1c_locale_override'
export const LOCALE_REQUEST_HEADER = 'X-CC1C-Locale'
