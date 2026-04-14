import { useMemo } from 'react'

import type { AppLocale } from './constants'
import { useLocaleState } from './I18nProvider'

type FormatterFallbackOptions = {
  fallback?: string
}

type RelativeTimeUnit = Intl.RelativeTimeFormatUnit

const formatterCache = new Map<string, Intl.DateTimeFormat | Intl.NumberFormat | Intl.ListFormat | Intl.RelativeTimeFormat>()
const DATE_TIME_COMPONENT_OPTION_KEYS = [
  'weekday',
  'era',
  'year',
  'month',
  'day',
  'dayPeriod',
  'hour',
  'minute',
  'second',
  'fractionalSecondDigits',
  'timeZoneName',
] as const

const hasExplicitDateTimeComponents = (options: Intl.DateTimeFormatOptions) => (
  DATE_TIME_COMPONENT_OPTION_KEYS.some((key) => options[key] !== undefined)
)

const splitFormatterFallback = <T extends object>(options?: T & FormatterFallbackOptions) => {
  if (!options) {
    return {
      fallback: undefined,
      intlOptions: undefined,
    } as const
  }

  const { fallback, ...rest } = options
  return {
    fallback,
    intlOptions: rest as T,
  } as const
}

const buildDateTimeOptions = (
  kind: 'dateTime' | 'time' | 'date',
  options?: Intl.DateTimeFormatOptions & FormatterFallbackOptions,
) => {
  const { fallback, intlOptions } = splitFormatterFallback(options)
  const nextIntlOptions = intlOptions ?? {}

  if (hasExplicitDateTimeComponents(nextIntlOptions)) {
    return {
      fallback,
      intlOptions: nextIntlOptions,
    } as const
  }

  if (kind === 'dateTime') {
    return {
      fallback,
      intlOptions: {
        dateStyle: 'medium',
        timeStyle: 'short',
        ...nextIntlOptions,
      },
    } as const
  }

  if (kind === 'time') {
    return {
      fallback,
      intlOptions: {
        timeStyle: 'short',
        ...nextIntlOptions,
      },
    } as const
  }

  return {
    fallback,
    intlOptions: {
      dateStyle: 'medium',
      ...nextIntlOptions,
    },
  } as const
}

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
    const { fallback, intlOptions } = buildDateTimeOptions('dateTime', options)
    if (!value) {
      return fallback ?? '—'
    }
    const date = value instanceof Date ? value : new Date(value)
    return getCachedFormatter(
      `datetime:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.DateTimeFormat(locale, intlOptions),
    ).format(date)
  },
  time: (value: string | Date | null | undefined, options?: Intl.DateTimeFormatOptions & FormatterFallbackOptions) => {
    const { fallback, intlOptions } = buildDateTimeOptions('time', options)
    if (!value) {
      return fallback ?? '—'
    }
    const date = value instanceof Date ? value : new Date(value)
    return getCachedFormatter(
      `time:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.DateTimeFormat(locale, intlOptions),
    ).format(date)
  },
  date: (value: string | Date | null | undefined, options?: Intl.DateTimeFormatOptions & FormatterFallbackOptions) => {
    const { fallback, intlOptions } = buildDateTimeOptions('date', options)
    if (!value) {
      return fallback ?? '—'
    }
    const date = value instanceof Date ? value : new Date(value)
    return getCachedFormatter(
      `date:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.DateTimeFormat(locale, intlOptions),
    ).format(date)
  },
  number: (value: number | null | undefined, options?: Intl.NumberFormatOptions & FormatterFallbackOptions) => {
    const { fallback, intlOptions } = splitFormatterFallback(options)
    if (value == null || Number.isNaN(value)) {
      return fallback ?? '—'
    }
    return getCachedFormatter(
      `number:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.NumberFormat(locale, intlOptions),
    ).format(value)
  },
  list: (value: string[], options?: Intl.ListFormatOptions & FormatterFallbackOptions) => {
    const { fallback, intlOptions } = splitFormatterFallback(options)
    if (value.length === 0) {
      return fallback ?? '—'
    }
    return getCachedFormatter(
      `list:${locale}:${JSON.stringify(options ?? {})}`,
      () => new Intl.ListFormat(locale, intlOptions),
    ).format(value)
  },
  relativeTime: (value: number | null | undefined, unit: RelativeTimeUnit, options?: Intl.RelativeTimeFormatOptions & FormatterFallbackOptions) => {
    const { fallback, intlOptions } = splitFormatterFallback(options)
    if (value == null || Number.isNaN(value)) {
      return fallback ?? '—'
    }
    return getCachedFormatter(
      `relative:${locale}:${unit}:${JSON.stringify(options ?? {})}`,
      () => new Intl.RelativeTimeFormat(locale, intlOptions),
    ).format(value, unit)
  },
})

export const useLocaleFormatters = () => {
  const { locale } = useLocaleState()
  return useMemo(() => createLocaleFormatters(locale), [locale])
}
