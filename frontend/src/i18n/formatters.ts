import { useMemo } from 'react'

import type { AppLocale } from './constants'
import { useLocaleState } from './I18nProvider'

type FormatterFallbackOptions = {
  fallback?: string
}

type RelativeTimeUnit = Intl.RelativeTimeFormatUnit

const formatterCache = new Map<string, Intl.DateTimeFormat | Intl.NumberFormat | Intl.ListFormat | Intl.RelativeTimeFormat>()

const getCachedFormatter = <T extends Intl.DateTimeFormat | Intl.NumberFormat | Intl.ListFormat | Intl.RelativeTimeFormat>(
  key: string,
  create: () => T,
): T => {
  const cached = formatterCache.get(key)
  if (cached) {
    return cached as T
  }

  const next = create()
  formatterCache.set(key, next)
  return next
}

export const createLocaleFormatters = (locale: AppLocale) => ({
  dateTime: (value: string | Date | null | undefined, options?: Intl.DateTimeFormatOptions & FormatterFallbackOptions) => {
    if (!value) {
      return options?.fallback ?? '—'
    }
    const date = value instanceof Date ? value : new Date(value)
    return getCachedFormatter(
      `datetime:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short',
        ...options,
      }),
    ).format(date)
  },
  date: (value: string | Date | null | undefined, options?: Intl.DateTimeFormatOptions & FormatterFallbackOptions) => {
    if (!value) {
      return options?.fallback ?? '—'
    }
    const date = value instanceof Date ? value : new Date(value)
    return getCachedFormatter(
      `date:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        ...options,
      }),
    ).format(date)
  },
  number: (value: number | null | undefined, options?: Intl.NumberFormatOptions & FormatterFallbackOptions) => {
    if (value == null || Number.isNaN(value)) {
      return options?.fallback ?? '—'
    }
    return getCachedFormatter(
      `number:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.NumberFormat(locale, options),
    ).format(value)
  },
  list: (value: string[], options?: Intl.ListFormatOptions & FormatterFallbackOptions) => {
    if (value.length === 0) {
      return options?.fallback ?? '—'
    }
    return getCachedFormatter(
      `list:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.ListFormat(locale, options),
    ).format(value)
  },
  relativeTime: (value: number | null | undefined, unit: RelativeTimeUnit, options?: Intl.RelativeTimeFormatOptions & FormatterFallbackOptions) => {
    if (value == null || Number.isNaN(value)) {
      return options?.fallback ?? '—'
    }
    return getCachedFormatter(
      `relative:${locale}:${unit}:${JSON.stringify(options ?? {})}`,
      () => new Intl.RelativeTimeFormat(locale, options),
    ).format(value, unit)
  },
})

export const useLocaleFormatters = () => {
  const { locale } = useLocaleState()
  return useMemo(() => createLocaleFormatters(locale), [locale])
}
