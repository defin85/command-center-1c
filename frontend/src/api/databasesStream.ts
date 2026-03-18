import { apiClient } from './client'
import { buildStreamUrl } from './sse'
import type { DatabaseStreamTicketRequest } from './generated/model/databaseStreamTicketRequest'
import type { DatabaseStreamTicketResponse } from './generated/model/databaseStreamTicketResponse'

export const getDatabaseStreamTicket = async (
  options: {
    clusterId?: string | null
    clientInstanceId: string
    sessionId?: string | null
    recovery?: boolean
  }
): Promise<DatabaseStreamTicketResponse> => {
  const payload: DatabaseStreamTicketRequest = {
    client_instance_id: options.clientInstanceId,
  }
  if (options.clusterId) {
    payload.cluster_id = options.clusterId
  }
  if (options.sessionId) {
    payload.session_id = options.sessionId
  }
  if (options.recovery) {
    payload.recovery = true
  }
  const response = await apiClient.post<DatabaseStreamTicketResponse>(
    '/api/v2/databases/stream-ticket/',
    payload,
    { errorPolicy: 'silent' }
  )
  return response.data
}

export const buildDatabaseStreamUrl = (streamUrl: string): string => {
  return buildStreamUrl(streamUrl)
}
