import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { FALLBACK_APP_LOCALE } from './constants'
import { useLocaleState } from './I18nProvider'
import { ensureNamespaces } from './runtime'
import { defaultNamespace, type TranslationNamespace } from './resources'

const normalizeNamespace = (value?: TranslationNamespace) => value ?? defaultNamespace
type ResolvedNamespace<Namespace extends TranslationNamespace | undefined> = (
  Namespace extends TranslationNamespace ? Namespace : typeof defaultNamespace
)

const hasNamespaceResources = (
  i18n: ReturnType<typeof useTranslation>['i18n'],
  locale: string,
  namespace: TranslationNamespace,
) => (
  i18n.hasResourceBundle(locale, namespace) || i18n.hasResourceBundle(FALLBACK_APP_LOCALE, namespace)
)

const useNamespaceTranslation = <Namespace extends TranslationNamespace | undefined>(value?: Namespace) => {
  const namespace = useMemo(
    () => normalizeNamespace(value) as ResolvedNamespace<Namespace>,
    [value],
  )
  const { locale } = useLocaleState()
  const translation = useTranslation<ResolvedNamespace<Namespace>>(namespace, { useSuspense: false })
  const [namespacesReady, setNamespacesReady] = useState(() => (
    hasNamespaceResources(translation.i18n, locale, namespace)
  ))

  useEffect(() => {
    let cancelled = false
    setNamespacesReady(hasNamespaceResources(translation.i18n, locale, namespace))

    void ensureNamespaces(locale, namespace).then(() => {
      if (!cancelled) {
        setNamespacesReady(hasNamespaceResources(translation.i18n, locale, namespace))
      }
    })

    return () => {
      cancelled = true
    }
  }, [locale, namespace, translation.i18n])

  return {
    ...translation,
    locale,
    ready: namespacesReady,
  }
}

export const useAppTranslation = useNamespaceTranslation
export const useCommonTranslation = () => useNamespaceTranslation('common')
export const useShellTranslation = () => useNamespaceTranslation('shell')
export const usePlatformTranslation = () => useNamespaceTranslation('platform')
export const useErrorsTranslation = () => useNamespaceTranslation('errors')
export const useSystemStatusTranslation = () => useNamespaceTranslation('systemStatus')
export const useDashboardTranslation = () => useNamespaceTranslation('dashboard')
export const useClustersTranslation = () => useNamespaceTranslation('clusters')
export const useRbacTranslation = () => useNamespaceTranslation('rbac')
export const useAdminSupportTranslation = () => useNamespaceTranslation('adminSupport')
