type ProblemDetailsPayload = {
  title?: string
  detail?: string
  code?: string
  errors?: unknown
}

export type ResolvedApiError = {
  message: string
  fieldErrors: Record<string, string[]>
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
  const fallback: ResolvedApiError = { message: fallbackMessage, fieldErrors: {} }
  if (!error || typeof error !== 'object') {
    return fallback
  }

  const maybeResponse = (error as { response?: { data?: unknown } }).response
  const payload = maybeResponse?.data
  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const maybeProblem = payload as ProblemDetailsPayload
  const detail = typeof maybeProblem.detail === 'string' ? maybeProblem.detail.trim() : ''
  const title = typeof maybeProblem.title === 'string' ? maybeProblem.title.trim() : ''
  const message = detail || title || fallbackMessage
  const fieldErrors = normalizeFieldErrors(maybeProblem.errors)

  return { message, fieldErrors }
}
