import type { TranslationNamespace } from './resources'
import { i18n } from './runtime'

export type AppStringTranslator = (key: string, options?: Record<string, unknown>) => string

const rawStringTranslate = i18n.t as unknown as AppStringTranslator

export const translateNamespace = (
  namespace: TranslationNamespace,
  key: string,
  options?: Record<string, unknown>,
): string => (
  rawStringTranslate(key, { ns: namespace, ...(options ?? {}) })
)
