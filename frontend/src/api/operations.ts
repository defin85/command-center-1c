/**
 * Operations API endpoints for RAS operations
 */

import { apiClient } from './client';
import { buildStreamUrl, openSseStream } from './sse';

export type RASOperationType =
  | 'lock_scheduled_jobs'
  | 'unlock_scheduled_jobs'
  | 'block_sessions'
  | 'unblock_sessions'
  | 'terminate_sessions';
// health_check использует другой endpoint

export interface ExecuteOperationRequest {
  operation_type: RASOperationType;
  database_ids: string[];
  config?: {
    message?: string;
    permission_code?: string;
    denied_from?: string;
    denied_to?: string;
    parameter?: string;
  };
}

export interface ExecuteOperationResponse {
  operation_id: string;
  status: string;
  total_tasks: number;
  message: string;
}

export interface SSETicketResponse {
  ticket: string;
  expires_in: number;
  stream_url: string;
}

export interface OperationEvent {
  version?: string;
  operation_id: string;
  timestamp: string;
  state: string;
  microservice: string;
  message: string;
  metadata?: Record<string, unknown>;
  error?: string;
}

export interface StreamStatus {
  active_streams: number;
  max_streams: number;
}

export interface StreamMuxStatus {
  active_streams: number;
  max_streams: number;
  active_subscriptions: number;
  max_subscriptions: number;
}

export interface StreamMuxTicketResponse {
  ticket: string;
  expires_in: number;
  stream_url: string;
}

export interface StreamMuxSubscriptionResponse {
  subscribed?: string[];
  denied?: string[];
  missing?: string[];
  unsubscribed?: string[];
  active_subscriptions: number;
  max_subscriptions: number;
}

export interface OperationCatalogItem {
  id: string;
  kind: 'operation' | 'template';
  operation_type?: string | null;
  template_id?: string | null;
  label: string;
  description: string;
  driver: string;
  category: string;
  tags?: string[];
  requires_config: boolean;
  has_ui_form: boolean;
  icon?: string | null;
  deprecated: boolean;
  deprecated_message?: string | null;
}

export interface OperationCatalogResponse {
  items: OperationCatalogItem[];
  count: number;
}

/**
 * Execute RAS operation on selected databases
 */
export const executeOperation = async (
  request: ExecuteOperationRequest
): Promise<ExecuteOperationResponse> => {
  const response = await apiClient.post<ExecuteOperationResponse>(
    '/api/v2/operations/execute/',
    request
  );
  return response.data;
};

/**
 * Get short-lived ticket for SSE stream authentication
 *
 * The ticket is valid for 30 seconds and can only be used once.
 * This is more secure than passing JWT tokens in URLs.
 */
export const getStreamTicket = async (
  operationId: string,
  clientId?: string
): Promise<SSETicketResponse> => {
  const response = await apiClient.post<SSETicketResponse>(
    '/api/v2/operations/stream-ticket/',
    { operation_id: operationId, client_id: clientId },
    { skipGlobalError: true }
  );
  return response.data;
};

export const getStreamStatus = async (): Promise<StreamStatus> => {
  const response = await apiClient.get<StreamStatus>(
    '/api/v2/operations/stream-status/',
    { skipGlobalError: true }
  );
  return response.data;
};

export const getStreamMuxStatus = async (): Promise<StreamMuxStatus> => {
  const response = await apiClient.get<StreamMuxStatus>(
    '/api/v2/operations/stream-mux-status/',
    { skipGlobalError: true }
  );
  return response.data;
};

export const getStreamMuxTicket = async (
  clientId?: string
): Promise<StreamMuxTicketResponse> => {
  const response = await apiClient.post<StreamMuxTicketResponse>(
    '/api/v2/operations/stream-mux-ticket/',
    { client_id: clientId },
    { skipGlobalError: true }
  );
  return response.data;
};

export const getOperationCatalog = async (): Promise<OperationCatalogResponse> => {
  const response = await apiClient.get<OperationCatalogResponse>(
    '/api/v2/operations/catalog/',
    { skipGlobalError: true }
  );
  return response.data;
};

export const subscribeOperationStreams = async (
  operationIds: string[]
): Promise<StreamMuxSubscriptionResponse> => {
  const response = await apiClient.post<StreamMuxSubscriptionResponse>(
    '/api/v2/operations/stream-subscribe/',
    { operation_ids: operationIds },
    { skipGlobalError: true }
  );
  return response.data;
};

export const unsubscribeOperationStreams = async (
  operationIds: string[]
): Promise<StreamMuxSubscriptionResponse> => {
  const response = await apiClient.post<StreamMuxSubscriptionResponse>(
    '/api/v2/operations/stream-unsubscribe/',
    { operation_ids: operationIds },
    { skipGlobalError: true }
  );
  return response.data;
};

/**
 * Subscribe to operation events via SSE
 *
 * Uses ticket-based auth for security (token not exposed in URL).
 * Returns cleanup function to close connection.
 */
export const subscribeToOperation = async (
  operationId: string,
  onEvent: (event: OperationEvent) => void,
  onError?: (error: unknown) => void,
  clientId?: string
): Promise<() => void> => {
  // Get short-lived ticket first
  const { stream_url } = await getStreamTicket(operationId, clientId);

  const token = localStorage.getItem('auth_token');
  if (!token) {
    throw new Error('Authentication required');
  }

  const url = buildStreamUrl(stream_url);
  const closeStream = openSseStream(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    onMessage: (message) => {
      try {
        const data = JSON.parse(message.data) as OperationEvent;
        onEvent(data);
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    },
    onError: (error) => {
      if (onError) {
        onError(error);
      }
    },
  });

  return closeStream;
};

export const operationsApi = {
  execute: executeOperation,
  getStreamTicket,
  getStreamStatus,
  getStreamMuxStatus,
  getOperationCatalog,
  getStreamMuxTicket,
  subscribeOperationStreams,
  unsubscribeOperationStreams,
  subscribeToOperation,
};

export default operationsApi;
