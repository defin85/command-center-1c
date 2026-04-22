type ProblemDetailsPayload = {
  error?: string
  title?: string
  detail?: string
  code?: string
  errors?: unknown
  request_id?: string
  rate_limit_class?: string
  retry_after_seconds?: number
  budget_scope?: string
}

export type ResolvedApiError = {
  message: string
  fieldErrors: Record<string, string[]>
  status?: number
  code?: string
  requestId?: string
  rateLimitClass?: string
  retryAfterSeconds?: number
  budgetScope?: string
}

const toMessageList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter((item) => item.length > 0)
  }
  if (value == null) {
    return []
  }
  const text = String(value).trim()
  return text ? [text] : []
}

const normalizeFieldErrors = (value: unknown): Record<string, string[]> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  const source = value as Record<string, unknown>
  const result: Record<string, string[]> = {}
  for (const [field, messages] of Object.entries(source)) {
    const normalized = toMessageList(messages)
    if (normalized.length > 0) {
      result[field] = normalized
    }
  }
  return result
}

export const resolveApiError = (error: unknown, fallbackMessage: string): ResolvedApiError => {
  const fallback: ResolvedApiError = {
    message: fallbackMessage,
    fieldErrors: {},
  }
  if (!error || typeof error !== 'object') {
    return fallback
  }

  const maybeResponse = (error as { response?: { status?: number; data?: unknown } }).response
  const payload = maybeResponse?.data
  if (!payload || typeof payload !== 'object') {
    return {
      ...fallback,
      status: maybeResponse?.status,
    }
  }

  const maybeProblem = payload as ProblemDetailsPayload
  const errorText = typeof maybeProblem.error === 'string' ? maybeProblem.error.trim() : ''
  const detail = typeof maybeProblem.detail === 'string' ? maybeProblem.detail.trim() : ''
  const title = typeof maybeProblem.title === 'string' ? maybeProblem.title.trim() : ''
  const message = detail || title || errorText || fallbackMessage
  const fieldErrors = normalizeFieldErrors(maybeProblem.errors)

  return {
    message,
    fieldErrors,
    status: maybeResponse?.status,
    code: typeof maybeProblem.code === 'string' ? maybeProblem.code : undefined,
    requestId: typeof maybeProblem.request_id === 'string' ? maybeProblem.request_id : undefined,
    rateLimitClass: typeof maybeProblem.rate_limit_class === 'string' ? maybeProblem.rate_limit_class : undefined,
    retryAfterSeconds: typeof maybeProblem.retry_after_seconds === 'number' ? maybeProblem.retry_after_seconds : undefined,
    budgetScope: typeof maybeProblem.budget_scope === 'string' ? maybeProblem.budget_scope : undefined,
  }
}
