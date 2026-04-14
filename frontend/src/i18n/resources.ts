import adminSupportEn from './locales/en/adminSupport'
import artifactsEn from './locales/en/artifacts'
import commonEn from './locales/en/common'
import type databasesSchema from './locales/ru/databases'
import decisionsEn from './locales/en/decisions'
import errorsEn from './locales/en/errors'
import type operationsSchema from './locales/ru/operations'
import platformEn from './locales/en/platform'
import type poolFactualSchema from './locales/ru/poolFactual'
import type poolsSchema from './locales/ru/pools'
import serviceMeshEn from './locales/en/serviceMesh'
import shellEn from './locales/en/shell'
import type templatesSchema from './locales/ru/templates'
import type workflowsSchema from './locales/ru/workflows'
import adminSupportRu from './locales/ru/adminSupport'
import artifactsRu from './locales/ru/artifacts'
import commonRu from './locales/ru/common'
import dashboardRu from './locales/ru/dashboard'
import decisionsRu from './locales/ru/decisions'
import errorsRu from './locales/ru/errors'
import clustersRu from './locales/ru/clusters'
import platformRu from './locales/ru/platform'
import rbacRu from './locales/ru/rbac'
import serviceMeshRu from './locales/ru/serviceMesh'
import shellRu from './locales/ru/shell'
import type systemStatusSchema from './locales/ru/systemStatus'
import type { AppLocale } from './constants'

export const eagerNamespaces = [
  'common',
  'shell',
  'platform',
  'errors',
  'adminSupport',
  'artifacts',
  'serviceMesh',
  'decisions',
] as const
export const lazyNamespaces = [
  'systemStatus',
  'dashboard',
  'clusters',
  'rbac',
  'operations',
  'databases',
  'templates',
  'workflows',
  'pools',
  'poolFactual',
] as const
export const allNamespaces = [...eagerNamespaces, ...lazyNamespaces] as const

export type TranslationNamespace = (typeof allNamespaces)[number]
type EagerTranslationNamespace = (typeof eagerNamespaces)[number]
type TranslationCatalog = Record<string, unknown>

export type AppCatalogSchema = {
  common: typeof commonRu
  shell: typeof shellRu
  platform: typeof platformRu
  errors: typeof errorsRu
  artifacts: typeof artifactsRu
  decisions: typeof decisionsRu
  serviceMesh: typeof serviceMeshRu
  systemStatus: typeof systemStatusSchema
  dashboard: typeof dashboardRu
  clusters: typeof clustersRu
  rbac: typeof rbacRu
  adminSupport: typeof adminSupportRu
  operations: typeof operationsSchema
  databases: typeof databasesSchema
  templates: typeof templatesSchema
  workflows: typeof workflowsSchema
  pools: typeof poolsSchema
  poolFactual: typeof poolFactualSchema
}

export const defaultNamespace = 'common'

export const eagerResources = {
  ru: {
    common: commonRu,
    shell: shellRu,
    platform: platformRu,
    errors: errorsRu,
    adminSupport: adminSupportRu,
    artifacts: artifactsRu,
    serviceMesh: serviceMeshRu,
    decisions: decisionsRu,
  },
  en: {
    adminSupport: adminSupportEn,
    artifacts: artifactsEn,
    common: commonEn,
    decisions: decisionsEn,
    shell: shellEn,
    platform: platformEn,
    errors: errorsEn,
    serviceMesh: serviceMeshEn,
  },
} as const satisfies Record<AppLocale, Record<EagerTranslationNamespace, TranslationCatalog>>

const lazyResourceModules = import.meta.glob<{ default: unknown }>('./locales/*/*.ts')

export const loadNamespaceCatalog = async <Namespace extends TranslationNamespace>(
  locale: AppLocale,
  namespace: Namespace,
): Promise<AppCatalogSchema[Namespace]> => {
  const eagerValue = eagerResources[locale][namespace as keyof typeof eagerResources[AppLocale]]
  if (eagerValue) {
    return eagerValue as AppCatalogSchema[Namespace]
  }

  const moduleKey = `./locales/${locale}/${namespace}.ts`
  const loader = lazyResourceModules[moduleKey]
  if (!loader) {
    throw new Error(`Missing i18n catalog: ${moduleKey}`)
  }

  const module = await loader()
  return module.default as AppCatalogSchema[Namespace]
}
