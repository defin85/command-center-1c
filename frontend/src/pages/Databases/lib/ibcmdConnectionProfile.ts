import type { DatabaseIbcmdConnectionProfileUpdateRequest } from '../../../api/queries/databases'

export type IbcmdConnectionProfileFormValues = {
  mode?: unknown
  remote_url?: unknown
  offline?: unknown
}

export function buildIbcmdConnectionProfileUpdatePayload(
  databaseId: string,
  values: IbcmdConnectionProfileFormValues
): DatabaseIbcmdConnectionProfileUpdateRequest {
  const mode = String(values.mode || 'auto').trim()
  const remoteUrl = String(values.remote_url || '').trim()
  const offlineIn = values.offline && typeof values.offline === 'object' ? (values.offline as Record<string, unknown>) : {}

  const offline: Record<string, string> = {}
  for (const key of ['config', 'data', 'db_path', 'dbms', 'db_server', 'db_name']) {
    const raw = offlineIn[key]
    const v = typeof raw === 'string' ? raw.trim() : ''
    if (v) offline[key] = v
  }

  const payload: DatabaseIbcmdConnectionProfileUpdateRequest = {
    database_id: databaseId,
    mode: mode as DatabaseIbcmdConnectionProfileUpdateRequest['mode'],
  }
  if (remoteUrl) payload.remote_url = remoteUrl
  if (Object.keys(offline).length > 0) payload.offline = offline
  return payload
}

