import { describe, expect, it } from 'vitest'

import { createLocaleFormatters } from '../formatters'

const TIMESTAMP = '2026-03-10T12:00:00Z'

describe('locale formatters', () => {
  it('formats date, time, number, list, and relative time through Intl for the active locale', () => {
    const ru = createLocaleFormatters('ru')
    const en = createLocaleFormatters('en')

    expect(ru.dateTime(TIMESTAMP, { timeZone: 'UTC' })).toBe(
      new Intl.DateTimeFormat('ru', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(TIMESTAMP)),
    )
    expect(ru.time(TIMESTAMP, { timeZone: 'UTC' })).toBe(
      new Intl.DateTimeFormat('ru', { timeStyle: 'short', timeZone: 'UTC' }).format(new Date(TIMESTAMP)),
    )
    expect(en.number(12345.67)).toBe(new Intl.NumberFormat('en').format(12345.67))
    expect(ru.list(['alpha', 'beta', 'gamma'], { style: 'long', type: 'conjunction' })).toBe(
      new Intl.ListFormat('ru', { style: 'long', type: 'conjunction' }).format(['alpha', 'beta', 'gamma']),
    )
    expect(en.relativeTime(-5, 'minute')).toBe(new Intl.RelativeTimeFormat('en').format(-5, 'minute'))
  })

  it('returns stable fallbacks for missing values', () => {
    const formatters = createLocaleFormatters('ru')

    expect(formatters.dateTime(null)).toBe('—')
    expect(formatters.time(undefined, { fallback: 'n/a' })).toBe('n/a')
    expect(formatters.date(undefined, { fallback: 'n/a' })).toBe('n/a')
    expect(formatters.number(Number.NaN)).toBe('—')
    expect(formatters.list([], { fallback: 'empty' })).toBe('empty')
    expect(formatters.relativeTime(undefined, 'second')).toBe('—')
  })

  it('supports granular Intl date-time fields without mixing them with preset styles', () => {
    const formatters = createLocaleFormatters('en')

    expect(formatters.time(TIMESTAMP, {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
      fallback: 'n/a',
    })).toBe(
      new Intl.DateTimeFormat('en', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC',
      }).format(new Date(TIMESTAMP)),
    )
  })
})
