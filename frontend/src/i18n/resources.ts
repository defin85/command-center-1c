import commonEn from './locales/en/common'
import dashboardEn from './locales/en/dashboard'
import errorsEn from './locales/en/errors'
import clustersEn from './locales/en/clusters'
import platformEn from './locales/en/platform'
import rbacEn from './locales/en/rbac'
import shellEn from './locales/en/shell'
import commonRu from './locales/ru/common'
import dashboardRu from './locales/ru/dashboard'
import errorsRu from './locales/ru/errors'
import clustersRu from './locales/ru/clusters'
import platformRu from './locales/ru/platform'
import rbacRu from './locales/ru/rbac'
import shellRu from './locales/ru/shell'
import type systemStatusSchema from './locales/ru/systemStatus'
import type { AppLocale } from './constants'

export const eagerNamespaces = ['common', 'shell', 'platform', 'errors'] as const
export const lazyNamespaces = ['systemStatus', 'dashboard', 'clusters', 'rbac'] as const
export const allNamespaces = [...eagerNamespaces, ...lazyNamespaces] as const

export type TranslationNamespace = (typeof allNamespaces)[number]
type EagerTranslationNamespace = (typeof eagerNamespaces)[number]
type TranslationCatalog = Record<string, unknown>

export type AppCatalogSchema = {
  common: typeof commonRu
  shell: typeof shellRu
  platform: typeof platformRu
  errors: typeof errorsRu
  systemStatus: typeof systemStatusSchema
  dashboard: typeof dashboardRu
  clusters: typeof clustersRu
  rbac: typeof rbacRu
}

export const defaultNamespace = 'common'

export const eagerResources = {
  ru: {
    common: commonRu,
    shell: shellRu,
    platform: platformRu,
    errors: errorsRu,
  },
  en: {
    common: commonEn,
    shell: shellEn,
    platform: platformEn,
    errors: errorsEn,
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
