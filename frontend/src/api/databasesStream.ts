import { apiClient } from './client'
import { buildStreamUrl } from './sse'

export interface DatabaseStreamTicketResponse {
  ticket: string
  expires_in: number
  stream_url: string
}

export const getDatabaseStreamTicket = async (
  clusterId?: string | null
): Promise<DatabaseStreamTicketResponse> => {
  const payload = clusterId ? { cluster_id: clusterId } : {}
  const response = await apiClient.post<DatabaseStreamTicketResponse>(
    '/api/v2/databases/stream-ticket/',
    payload
  )
  return response.data
}

export const buildDatabaseStreamUrl = (streamUrl: string): string => {
  return buildStreamUrl(streamUrl)
}
