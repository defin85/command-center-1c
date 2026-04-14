import { afterEach, beforeAll, describe, expect, it } from 'vitest'

import { changeLanguage, ensureNamespaces, i18n } from '../runtime'

const cloneCatalog = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const translateSystemStatusFailureMessage = (options?: Record<string, unknown>) => (
  (i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string)(
    'systemStatus:messages.failedLoadSystemStatus',
    options,
  )
)
const translateAdminSupportUsersTitle = () => (
  (i18n.t as unknown as (key: string) => string)('adminSupport:users.page.title')
)
const translatePoolsExecutionPackTitle = () => (
  (i18n.t as unknown as (key: string) => string)('pools:executionPacks.page.title')
)
const translateWorkflowListTitle = () => (
  (i18n.t as unknown as (key: string) => string)('workflows:list.page.title')
)

describe('i18n runtime', () => {
  let originalEnglishSystemStatusCatalog: Record<string, unknown> = {}

  beforeAll(async () => {
    await ensureNamespaces('ru', 'systemStatus')
    await ensureNamespaces('en', 'systemStatus')
    await ensureNamespaces('ru', 'pools')
    await ensureNamespaces('en', 'pools')
    await ensureNamespaces('ru', 'workflows')
    await ensureNamespaces('en', 'workflows')
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

  it('keeps eager admin-support catalogs available in both locales', async () => {
    await changeLanguage('en')
    expect(translateAdminSupportUsersTitle()).toBe('Users')

    await changeLanguage('ru')
    expect(translateAdminSupportUsersTitle()).toBe('Пользователи')
  })

  it('loads lazy pools and workflows namespaces before route surfaces use them', async () => {
    await changeLanguage('en')

    expect(i18n.hasResourceBundle('en', 'pools')).toBe(true)
    expect(i18n.hasResourceBundle('en', 'workflows')).toBe(true)
    expect(translatePoolsExecutionPackTitle()).toBe('Execution Packs')
    expect(translateWorkflowListTitle()).toBe('Workflow Scheme Library')
  })
})
