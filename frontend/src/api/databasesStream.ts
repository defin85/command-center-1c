import { apiClient } from './client'
import { getApiBaseUrl } from './baseUrl'

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
  if (streamUrl.startsWith('http://') || streamUrl.startsWith('https://')) {
    return streamUrl
  }
  const baseUrl = getApiBaseUrl()
  return `${baseUrl}${streamUrl}`
}
