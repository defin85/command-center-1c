/**
 * Operations API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/operations.ts
 * 3. Maps parameters to the v2 action-based endpoints
 * 4. Provides type transformations between generated and legacy types
 */

import { customInstance } from '../mutator'

// Import generated types for internal use
import type {
  BatchOperation as GeneratedBatchOperation,
  Task as GeneratedTask,
} from '../generated/model'

// Re-export generated types and enums for direct use
export type {
  BatchOperationStatusEnum,
  TaskStatusEnum,
  OperationTypeEnum,
} from '../generated/model'

// Re-export enums with aliases for convenience
export { BatchOperationStatusEnum as OperationStatus } from '../generated/model'
export { TaskStatusEnum as TaskStatus } from '../generated/model'
export { OperationTypeEnum as OperationType } from '../generated/model'

// ============================================================================
// Legacy Types (for backward compatibility with existing components)
// ============================================================================

/**
 * Task type for UI components.
 * Matches the legacy format expected by Operations.tsx
 */
export interface Task {
  id: string
  database: string
  database_name: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'retry' | 'cancelled'
  result: unknown
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
 * BatchOperation type for UI components.
 * Matches the legacy format expected by Operations.tsx
 */
export interface BatchOperation {
  id: string
  name: string
  description: string
  operation_type: 'create' | 'update' | 'delete' | 'query' | 'install_extension' | 'lock_scheduled_jobs' | 'unlock_scheduled_jobs' | 'terminate_sessions' | 'block_sessions' | 'unblock_sessions'
  target_entity: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  payload: unknown
  config: unknown
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  success_rate: number | null
  created_by: string
  metadata: unknown
  created_at: string
  updated_at: string
  database_names: string[]
  tasks: Task[]
}

/**
 * Legacy Operation interface for backward compatibility.
 * Used by useOperationStore.
 */
export interface Operation {
  id: string
  type: string
  status: string
  database: string
  payload: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  created_at: string
  updated_at: string
}

// ============================================================================
// Request/Response interfaces
// ============================================================================

export interface ListOperationsParams {
  status?: string
  operation_type?: string
  created_by?: string
  limit?: number
  offset?: number
  page?: number
  page_size?: number
}

export interface ListOperationsResponse {
  operations: BatchOperation[]
  count: number
  total: number
}

export interface GetOperationResponse {
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

export interface CancelOperationResponse {
  operation_id: string
  cancelled: boolean
  message: string
}

// ============================================================================
// Type Transformations (Generated <-> Legacy)
// ============================================================================

/**
 * Convert generated Task to legacy Task format.
 */
function convertTaskToLegacy(task: GeneratedTask): Task {
  return {
    id: task.id,
    database: task.database,
    database_name: task.database_name,
    status: task.status as Task['status'],
    result: task.result,
    error_message: task.error_message ?? '',
    error_code: task.error_code ?? '',
    retry_count: task.retry_count ?? 0,
    max_retries: task.max_retries ?? 3,
    worker_id: task.worker_id ?? '',
    started_at: task.started_at ?? null,
    completed_at: task.completed_at ?? null,
    duration_seconds: task.duration_seconds ?? null,
    created_at: task.created_at,
    updated_at: task.updated_at,
  }
}

/**
 * Convert generated BatchOperation to legacy BatchOperation format.
 */
function convertOperationToLegacy(op: GeneratedBatchOperation): BatchOperation {
  // Parse database_names (API returns it as string, we need array)
  let databaseNames: string[] = []
  if (typeof op.database_names === 'string') {
    try {
      databaseNames = JSON.parse(op.database_names)
    } catch {
      databaseNames = op.database_names ? [op.database_names] : []
    }
  } else if (Array.isArray(op.database_names)) {
    databaseNames = op.database_names
  }

  // Parse duration_seconds (API returns it as string)
  let durationSeconds: number | null = null
  if (op.duration_seconds) {
    const parsed = parseFloat(op.duration_seconds)
    durationSeconds = Number.isNaN(parsed) ? null : parsed
  }

  // Parse success_rate (API returns it as string)
  let successRate: number | null = null
  if (op.success_rate) {
    const parsed = parseFloat(op.success_rate)
    successRate = Number.isNaN(parsed) ? null : parsed
  }

  return {
    id: op.id,
    name: op.name,
    description: op.description ?? '',
    operation_type: op.operation_type as BatchOperation['operation_type'],
    target_entity: op.target_entity,
    status: op.status as BatchOperation['status'],
    progress: op.progress,
    total_tasks: op.total_tasks,
    completed_tasks: op.completed_tasks,
    failed_tasks: op.failed_tasks,
    payload: op.payload,
    config: op.config,
    celery_task_id: op.celery_task_id ?? null,
    started_at: op.started_at ?? null,
    completed_at: op.completed_at ?? null,
    duration_seconds: durationSeconds,
    success_rate: successRate,
    created_by: op.created_by ?? '',
    metadata: op.metadata,
    created_at: op.created_at,
    updated_at: op.updated_at,
    database_names: databaseNames,
    tasks: op.tasks ? op.tasks.map(convertTaskToLegacy) : [],
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all batch operations with optional filtering.
 */
export const listOperations = async (
  params?: ListOperationsParams
): Promise<BatchOperation[]> => {
  // Convert page/page_size to limit/offset for v2 API
  const limit = params?.limit ?? params?.page_size ?? 50
  const offset = params?.offset ?? (params?.page ? (params.page - 1) * limit : 0)

  interface ApiResponse {
    operations: GeneratedBatchOperation[]
    count: number
    total: number
  }

  const response = await customInstance<ApiResponse>({
    url: '/api/v2/operations/list-operations/',
    method: 'GET',
    params: {
      limit,
      offset,
      status: params?.status,
      operation_type: params?.operation_type,
      created_by: params?.created_by,
    },
  })

  return response.operations.map(convertOperationToLegacy)
}

/**
 * Get detailed information about a specific operation.
 */
export const getOperation = async (id: string): Promise<BatchOperation> => {
  interface ApiResponse {
    operation: GeneratedBatchOperation
    tasks?: GeneratedTask[]
    progress: {
      total: number
      completed: number
      failed: number
      pending: number
      processing: number
      percent: number
    }
  }

  const response = await customInstance<ApiResponse>({
    url: '/api/v2/operations/get-operation/',
    method: 'GET',
    params: { operation_id: id },
  })

  return convertOperationToLegacy(response.operation)
}

/**
 * Cancel a running or pending operation.
 */
export const cancelOperation = async (id: string): Promise<CancelOperationResponse> => {
  const response = await customInstance<CancelOperationResponse>({
    url: '/api/v2/operations/cancel-operation/',
    method: 'POST',
    data: { operation_id: id },
  })

  return response
}

// ============================================================================
// Legacy API Object (for backward compatibility with existing components)
// ============================================================================

/**
 * Operations API object matching the legacy endpoints/operations.ts interface.
 * @deprecated Use individual functions (listOperations, getOperation, cancelOperation) instead.
 */
export const operationsApi = {
  /**
   * List all batch operations.
   * @deprecated Use listOperations() instead.
   */
  list: async (params?: ListOperationsParams): Promise<BatchOperation[]> => {
    return listOperations(params)
  },

  /**
   * Get a specific operation by ID.
   * @deprecated Use getOperation() instead.
   */
  get: async (id: string): Promise<BatchOperation> => {
    return getOperation(id)
  },

  /**
   * Cancel a running operation.
   * @deprecated Use cancelOperation() instead.
   */
  cancel: async (id: string): Promise<{ cancelled: boolean; message: string }> => {
    const result = await cancelOperation(id)
    return {
      cancelled: result.cancelled,
      message: result.message,
    }
  },
}
