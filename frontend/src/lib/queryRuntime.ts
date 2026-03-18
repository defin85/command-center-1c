export type QueryPolicyName =
  | 'bootstrap'
  | 'interactive'
  | 'background'
  | 'realtime-backed'
  | 'capability'

type RetryableError = {
  code?: string
  name?: string
  response?: {
    status?: number
  }
}

type QueryPolicy = {
  gcTime: number
  staleTime: number
  refetchOnWindowFocus: false
  refetchOnReconnect: false
  retry: (failureCount: number, error: unknown) => boolean
  meta: {
    queryPolicy: QueryPolicyName
  }
}

const QUERY_GC_TIME_MS = 5 * 60_000
const STALE_BOOTSTRAP_MS = 5 * 60_000
const STALE_BACKGROUND_MS = 60_000
const STALE_INTERACTIVE_MS = 30_000

const RETRY_BUDGET = {
  bootstrap: 1,
  interactive: 1,
  background: 0,
  'realtime-backed': 0,
  capability: 0,
} as const

const isCanceledError = (error: RetryableError) => (
  error.code === 'ERR_CANCELED'
  || error.name === 'CanceledError'
  || error.name === 'AbortError'
)

export const shouldRetryQueryError = (
  failureCount: number,
  error: unknown,
  maxRetries = 1,
): boolean => {
  const candidate = (error ?? {}) as RetryableError
  if (isCanceledError(candidate)) {
    return false
  }

  const status = candidate.response?.status
  if (typeof status === 'number') {
    if (status >= 500) {
      return failureCount < maxRetries
    }
    return false
  }

  return failureCount < maxRetries
}

const createQueryPolicy = (
  queryPolicy: QueryPolicyName,
  staleTime: number,
): QueryPolicy => ({
  gcTime: QUERY_GC_TIME_MS,
  staleTime,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  retry: (failureCount, error) => shouldRetryQueryError(
    failureCount,
    error,
    RETRY_BUDGET[queryPolicy],
  ),
  meta: { queryPolicy },
})

const queryPolicies: Record<QueryPolicyName, QueryPolicy> = {
  bootstrap: createQueryPolicy('bootstrap', STALE_BOOTSTRAP_MS),
  interactive: createQueryPolicy('interactive', STALE_INTERACTIVE_MS),
  background: createQueryPolicy('background', STALE_BACKGROUND_MS),
  'realtime-backed': createQueryPolicy('realtime-backed', STALE_INTERACTIVE_MS),
  capability: createQueryPolicy('capability', STALE_BOOTSTRAP_MS),
}

export const getQueryPolicy = (queryPolicy: QueryPolicyName): QueryPolicy => queryPolicies[queryPolicy]

export const withQueryPolicy = <T extends Record<string, unknown>>(
  queryPolicy: QueryPolicyName,
  options: T,
): T & QueryPolicy => {
  const policy = getQueryPolicy(queryPolicy)
  const optionMeta = typeof options.meta === 'object' && options.meta !== null
    ? options.meta as Record<string, unknown>
    : {}

  return {
    ...policy,
    ...options,
    meta: {
      ...optionMeta,
      queryPolicy,
    },
  } as T & QueryPolicy
}
