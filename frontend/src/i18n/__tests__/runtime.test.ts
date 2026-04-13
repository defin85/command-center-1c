import { afterEach, beforeAll, describe, expect, it } from 'vitest'

import { changeLanguage, ensureNamespaces, i18n } from '../runtime'

const cloneCatalog = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const translateSystemStatusFailureMessage = (options?: Record<string, unknown>) => (
  (i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string)(
    'systemStatus:messages.failedLoadSystemStatus',
    options,
  )
)

describe('i18n runtime', () => {
  let originalEnglishSystemStatusCatalog: Record<string, unknown> = {}

  beforeAll(async () => {
    await ensureNamespaces('ru', 'systemStatus')
    await ensureNamespaces('en', 'systemStatus')
    originalEnglishSystemStatusCatalog = cloneCatalog(
      i18n.getResourceBundle('en', 'systemStatus') ?? {},
    )
  })

  afterEach(async () => {
    i18n.removeResourceBundle('en', 'systemStatus')
    i18n.addResourceBundle('en', 'systemStatus', cloneCatalog(originalEnglishSystemStatusCatalog), true, true)
    await changeLanguage('ru')
  })

  it('loads lazy route namespaces before first use', async () => {
    await changeLanguage('en')

    expect(i18n.hasResourceBundle('en', 'systemStatus')).toBe(true)
    expect(translateSystemStatusFailureMessage()).toBe('Failed to load system status')
  })

  it('falls back to the fallback locale when the active locale misses a route key', async () => {
    i18n.removeResourceBundle('en', 'systemStatus')
    i18n.addResourceBundle('en', 'systemStatus', { messages: {} }, true, true)

    await changeLanguage('en')

    expect(translateSystemStatusFailureMessage()).toBe('Не удалось загрузить system status')
  })
})
