import type { DatabaseIbcmdConnectionProfileUpdateRequest } from '../../../api/queries/databases'

export type IbcmdConnectionProfileFormValues = {
  remote?: unknown
  pid?: unknown
  offline_entries?: unknown
}

export function buildIbcmdConnectionProfileUpdatePayload(
  databaseId: string,
  values: IbcmdConnectionProfileFormValues
): DatabaseIbcmdConnectionProfileUpdateRequest {
  const payload: DatabaseIbcmdConnectionProfileUpdateRequest = {
    database_id: databaseId,
  }

  const remote = String(values.remote || '').trim()
  if (remote) payload.remote = remote

  const pidRaw = values.pid
  const pid = typeof pidRaw === 'number' ? pidRaw : typeof pidRaw === 'string' ? Number(pidRaw) : NaN
  if (Number.isFinite(pid) && pid > 0) payload.pid = pid

  const entries = Array.isArray(values.offline_entries) ? (values.offline_entries as unknown[]) : []
  const offline: Record<string, string> = {}
  for (const raw of entries) {
    if (!raw || typeof raw !== 'object') continue
    const rec = raw as Record<string, unknown>
    const key = typeof rec.key === 'string' ? rec.key.trim() : ''
    const value = typeof rec.value === 'string' ? rec.value.trim() : ''
    if (!key || !value) continue
    offline[key] = value
  }
  if (Object.keys(offline).length > 0) payload.offline = offline

  return payload
}
