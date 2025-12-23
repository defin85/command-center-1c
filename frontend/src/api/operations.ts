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
  operationId: string
): Promise<SSETicketResponse> => {
  const response = await apiClient.post<SSETicketResponse>(
    '/api/v2/operations/stream-ticket/',
    { operation_id: operationId }
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
  onError?: (error: unknown) => void
): Promise<() => void> => {
  // Get short-lived ticket first
  const { stream_url } = await getStreamTicket(operationId);

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
  subscribeToOperation,
};

export default operationsApi;
