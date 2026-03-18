export type ApiErrorPolicy = 'global' | 'background' | 'page' | 'silent'

export type ApiErrorContext = {
  errorPolicy?: ApiErrorPolicy
  skipGlobalError?: boolean
}

export type ApiErrorDetail = {
  message: string
  status?: number
  code?: string
  details?: unknown
  method?: string
  path?: string
  errorPolicy: ApiErrorPolicy
  dedupeKey: string
}

const normalizePath = (path?: string): string => {
  if (!path) {
    return 'unknown-path'
  }

  const [pathname] = path.split('?')
  return pathname || 'unknown-path'
}

export const resolveApiErrorPolicy = ({
  errorPolicy,
  skipGlobalError,
}: ApiErrorContext): ApiErrorPolicy => {
  if (skipGlobalError) {
    return 'silent'
  }
  return errorPolicy ?? 'global'
}

export const shouldDispatchGlobalApiError = (context: ApiErrorContext): boolean => {
  const policy = resolveApiErrorPolicy(context)
  return policy === 'global' || policy === 'background'
}

export const buildApiErrorNotificationKey = ({
  status,
  code,
  method,
  path,
  errorPolicy,
}: {
  status?: number
  code?: string
  method?: string
  path?: string
  errorPolicy: ApiErrorPolicy
}): string => {
  const normalizedMethod = method?.toUpperCase() || 'UNKNOWN'
  const normalizedCode = code || 'UNKNOWN_CODE'
  const normalizedPath = normalizePath(path)
  return ['api-error', errorPolicy, String(status ?? 'unknown-status'), normalizedCode, normalizedMethod, normalizedPath].join(':')
}

export const createApiErrorDetail = ({
  message,
  status,
  code,
  details,
  method,
  path,
  errorPolicy,
}: {
  message: string
  status?: number
  code?: string
  details?: unknown
  method?: string
  path?: string
  errorPolicy: ApiErrorPolicy
}): ApiErrorDetail => ({
  message,
  status,
  code,
  details,
  method,
  path: normalizePath(path),
  errorPolicy,
  dedupeKey: buildApiErrorNotificationKey({
    status,
    code,
    method,
    path,
    errorPolicy,
  }),
})
