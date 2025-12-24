import { apiClient } from './client'
import { buildStreamUrl } from './sse'

export interface DatabaseStreamTicketResponse {
  ticket: string
  expires_in: number
  stream_url: string
}

export const getDatabaseStreamTicket = async (
  clusterId?: string | null,
  force?: boolean
): Promise<DatabaseStreamTicketResponse> => {
  const payload: { cluster_id?: string | null; force?: boolean } = {}
  if (clusterId) {
    payload.cluster_id = clusterId
  }
  if (force) {
    payload.force = true
  }
  const response = await apiClient.post<DatabaseStreamTicketResponse>(
    '/api/v2/databases/stream-ticket/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export const buildDatabaseStreamUrl = (streamUrl: string): string => {
  return buildStreamUrl(streamUrl)
}
