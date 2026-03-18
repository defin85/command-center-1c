import { getV2, type DatabaseStreamTicketRequest, type DatabaseStreamTicketResponse } from './generated'
import { buildStreamUrl } from './sse'

const api = getV2()

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
  return api.postDatabasesStreamTicket(
    payload,
    { errorPolicy: 'silent' },
  )
}

export const buildDatabaseStreamUrl = (streamUrl: string): string => {
  return buildStreamUrl(streamUrl)
}
