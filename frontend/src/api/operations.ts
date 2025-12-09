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
  };
}

export interface ExecuteOperationResponse {
  operation_id: string;
  status: string;
  total_tasks: number;
  message: string;
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

export const operationsApi = {
  execute: executeOperation,
};

export default operationsApi;
