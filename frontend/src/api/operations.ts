/**
 * Operations API endpoints for RAS operations
 */

import { apiClient } from './client';

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
  onError?: (error: Event) => void
): Promise<() => void> => {
  // Get short-lived ticket first
  const { stream_url } = await getStreamTicket(operationId);

  // Connect to SSE using ticket
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const eventSource = new EventSource(`${baseUrl}${stream_url}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as OperationEvent;
      onEvent(data);
    } catch (e) {
      console.error('Failed to parse SSE event:', e);
    }
  };

  eventSource.onerror = (error) => {
    if (onError) {
      onError(error);
    }
    eventSource.close();
  };

  // Return cleanup function
  return () => eventSource.close();
};

export const operationsApi = {
  execute: executeOperation,
  getStreamTicket,
  subscribeToOperation,
};

export default operationsApi;
