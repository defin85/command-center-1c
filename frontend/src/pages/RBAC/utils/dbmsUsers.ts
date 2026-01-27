export const DBMS_AUTH_TYPE_LABELS: Record<string, string> = {
  local: '\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f',
  service: '\u0421\u0435\u0440\u0432\u0438\u0441\u043d\u0430\u044f',
  other: '\u0414\u0440\u0443\u0433\u0430\u044f',
}

export function getDbmsAuthTypeLabel(authType: string | undefined): string {
  const key = authType ?? 'local'
  return DBMS_AUTH_TYPE_LABELS[key] || key
}

export function getDbmsPasswordConfiguredLabel(configured: boolean): string {
  return configured ? '\u0417\u0430\u0434\u0430\u043d' : '\u041d\u0435 \u0437\u0430\u0434\u0430\u043d'
}

export type DbmsUserIdValidation = 'ok' | 'required' | 'must_be_empty'

export function validateDbmsUserId(isService: boolean, userId: unknown): DbmsUserIdValidation {
  const hasUserId = typeof userId === 'number' && Number.isFinite(userId)
  if (isService) return hasUserId ? 'must_be_empty' : 'ok'
  return hasUserId ? 'ok' : 'required'
}

