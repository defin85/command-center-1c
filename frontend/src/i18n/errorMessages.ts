import { i18n } from './runtime'

const lookupKnownMessage = (keys: string[]): string | null => {
  for (const key of keys) {
    if (i18n.exists(key)) {
      return i18n.t(key)
    }
  }
  return null
}

export const resolveLocalizedApiErrorMessage = ({
  code,
  status,
  detail,
  fallbackMessage,
}: {
  code?: string
  status?: number
  detail?: string | null
  fallbackMessage?: string
}): string => {
  const normalizedDetail = detail?.trim() || null

  const knownMessage = lookupKnownMessage([
    ...(code ? [`errors:problem.${code}`] : []),
    ...(status ? [`errors:status.${status}`] : []),
  ])

  if (knownMessage) {
    if (code || status) {
      return knownMessage
    }
  }

  if (!status && !code) {
    return lookupKnownMessage(['errors:transport.network'])
      ?? normalizedDetail
      ?? fallbackMessage
      ?? 'Network error.'
  }

  const generic = lookupKnownMessage(['errors:problem.unspecific'])
    ?? fallbackMessage
    ?? 'Unexpected error.'

  return normalizedDetail ? `${generic} ${normalizedDetail}` : generic
}
