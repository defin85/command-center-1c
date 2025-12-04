/**
 * @deprecated This module is deprecated. Use '../adapters/operations' instead.
 * This file will be removed in a future version.
 *
 * Migration guide:
 * - Replace: import { operationsApi, BatchOperation, Task } from '../api/endpoints/operations'
 * - With:    import { operationsApi, BatchOperation, Task } from '../api/adapters/operations'
 *
 * Or use individual functions:
 * - import { listOperations, getOperation, cancelOperation } from '../api/adapters/operations'
 */
import { apiClient } from '../client'

/**
 * @deprecated Use Task from '../adapters/operations' instead.
 */
export interface Task {
  id: string
  database: string
  database_name: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'retry' | 'cancelled'
  result: any
  error_message: string
  error_code: string
  retry_count: number
  max_retries: number
  worker_id: string
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  created_at: string
  updated_at: string
}

/**
 * @deprecated Use BatchOperation from '../adapters/operations' instead.
 */
export interface BatchOperation {
  id: string
  name: string
  description: string
  operation_type: 'create' | 'update' | 'delete' | 'query' | 'install_extension'
  target_entity: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  payload: any
  config: any
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  success_rate: number | null
  created_by: string
  metadata: any
  created_at: string
  updated_at: string
  database_names: string[]
  tasks: Task[]
}

/**
 * @deprecated Use Operation from '../adapters/operations' instead.
 * Legacy interface for backward compatibility.
 */
export interface Operation {
  id: string
  type: string
  status: string
  database: string
  payload: Record<string, any>
  result?: Record<string, any>
  error?: string
  created_at: string
  updated_at: string
}

// API v2 response format
interface ListOperationsResponse {
  operations: BatchOperation[]
  count: number
  total: number
}

interface GetOperationResponse {
  operation: BatchOperation
  tasks?: Task[]
  progress: {
    total: number
    completed: number
    failed: number
    pending: number
    processing: number
    percent: number
  }
}

/**
 * @deprecated Use operationsApi from '../adapters/operations' instead,
 * or use individual functions: listOperations, getOperation, cancelOperation.
 */
export const operationsApi = {
  // API v2 action-based endpoints
  list: async (params?: Record<string, any>): Promise<BatchOperation[]> => {
    const response = await apiClient.get<ListOperationsResponse>('/operations/list-operations/', { params })
    return response.data.operations
  },

  get: async (id: string): Promise<BatchOperation> => {
    const response = await apiClient.get<GetOperationResponse>('/operations/get-operation/', { params: { operation_id: id } })
    return response.data.operation
  },

  cancel: async (id: string): Promise<{ cancelled: boolean; message: string }> => {
    const response = await apiClient.post<{ operation_id: string; cancelled: boolean; message: string }>(
      '/operations/cancel-operation/',
      { operation_id: id }
    )
    return response.data
  }
}
