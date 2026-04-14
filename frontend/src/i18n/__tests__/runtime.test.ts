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
const translatePoolFactualTitle = () => (
  (i18n.t as unknown as (key: string) => string)('poolFactual:page.title')
)
const translateWorkflowListTitle = () => (
  (i18n.t as unknown as (key: string) => string)('workflows:list.page.title')
)
const translateKey = (key: string) => (
  (i18n.t as unknown as (key: string) => string)(key)
)
const getShellNavigationCatalog = () => (
  (i18n.getResourceBundle('ru', 'shell') as { navigation: Record<string, string> }).navigation
)

describe('i18n runtime', () => {
  let originalEnglishSystemStatusCatalog: Record<string, unknown> = {}

  beforeAll(async () => {
    await ensureNamespaces('ru', 'systemStatus')
    await ensureNamespaces('en', 'systemStatus')
    await ensureNamespaces('ru', 'pools')
    await ensureNamespaces('en', 'pools')
    await ensureNamespaces('ru', 'poolFactual')
    await ensureNamespaces('en', 'poolFactual')
    await ensureNamespaces('ru', 'workflows')
    await ensureNamespaces('en', 'workflows')
    await ensureNamespaces('ru', 'dashboard')
    await ensureNamespaces('ru', 'clusters')
    await ensureNamespaces('ru', 'serviceMesh')
    await ensureNamespaces('ru', 'adminSupport')
    await ensureNamespaces('ru', 'decisions')
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

  it('keeps shell navigation labels localized in Russian', async () => {
    await changeLanguage('ru')

    expect(getShellNavigationCatalog()).toEqual({
      dashboard: 'Панель управления',
      systemStatus: 'Статус системы',
      clusters: 'Кластеры',
      databases: 'Базы',
      extensions: 'Расширения',
      operations: 'Операции',
      artifacts: 'Артефакты',
      workflows: 'Workflow-схемы',
      templates: 'Шаблоны операций',
      decisions: 'Политики решений',
      poolCatalog: 'Каталог пулов',
      poolTopologyTemplates: 'Шаблоны топологий пулов',
      poolExecutionPacks: 'Пакеты выполнения пулов',
      poolMasterData: 'Master Data пулов',
      poolRuns: 'Запуски пулов',
      poolFactual: 'Факты пулов',
      poolTemplates: 'Шаблоны схем пулов',
      serviceMesh: 'Сервисная шина',
      rbac: 'RBAC',
      users: 'Пользователи',
      dlq: 'DLQ',
      runtimeSettings: 'Настройки runtime',
      commandSchemas: 'Схемы команд',
      timelineSettings: 'Настройки timeline',
    })
  })

  it('keeps top-level route titles localized in Russian', async () => {
    await changeLanguage('ru')

    expect(translateKey('dashboard:page.title')).toBe('Панель управления')
    expect(translateKey('systemStatus:header.title')).toBe('Статус системы')
    expect(translateKey('clusters:page.title')).toBe('Кластеры')
    expect(translateKey('serviceMesh:page.title')).toBe('Сервисная шина')
    expect(translateKey('adminSupport:extensions.page.title')).toBe('Расширения')
    expect(translateKey('adminSupport:commandSchemas.page.title')).toBe('Схемы команд')
    expect(translateKey('decisions:page.title')).toBe('Политики решений')
    expect(translateKey('pools:schemaTemplates.page.title')).toBe('Шаблоны схем пулов')
    expect(translateKey('pools:topologyTemplates.page.title')).toBe('Шаблоны топологий пулов')
    expect(translateKey('pools:executionPacks.page.title')).toBe('Пакеты выполнения пулов')
    expect(translateKey('pools:masterData.page.title')).toBe('Master Data пулов')
    expect(translateKey('pools:runs.page.title')).toBe('Запуски пулов')
    expect(translatePoolFactualTitle()).toBe('Фактический мониторинг пулов')
  })

  it('loads lazy pools, factual, and workflows namespaces before route surfaces use them', async () => {
    await changeLanguage('en')

    expect(i18n.hasResourceBundle('en', 'pools')).toBe(true)
    expect(i18n.hasResourceBundle('en', 'poolFactual')).toBe(true)
    expect(i18n.hasResourceBundle('en', 'workflows')).toBe(true)
    expect(translatePoolsExecutionPackTitle()).toBe('Execution Packs')
    expect(translatePoolFactualTitle()).toBe('Pool Factual Monitoring')
    expect(translateWorkflowListTitle()).toBe('Workflow Scheme Library')
  })
})
